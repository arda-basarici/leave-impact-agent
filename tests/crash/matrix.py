"""The parent of the crash matrix: the world prepared once, the reference run, one row per
crossing, the boundary read between the kill and the recovery, and the reconciliation.

The reference child runs with no kill target; its record lists every crossing the run makes,
and its log and export are what a recovered run is compared with. One row per crossing, each
in a schema of its own, rows run a few at a time:

1. A child is started with the crossing as its kill target. The row goes on only if the
   child exited with the injector's code and its last recorded crossing is the target; any
   other ending fails the row as not reached.
2. *The boundary.* Once the dead child's database sessions have ended, the parent reads the
   log and every checkpoint of the dead generation's thread with its pending writes. The
   invariant: each result a checkpoint or a pending write represents, a position and a
   digest, is in the log with that digest. The log as it stands is kept as the snapshot the
   reconciliation reads the in-flight requests from.
3. A fresh child recovers and must complete; a recovery row kills it too, at a crossing of
   its own, and a third child completes.
4. *Reconciliation*, against the reference and the snapshots (the worker group's fifth
   fork): nothing of any prefix rewritten; every settled event equal to the reference's;
   exactly one more event per claim beyond the first and one per request left in flight;
   the requests in flight at the end exactly those the snapshots left in flight, none of
   them answered, so no send ever happens under a held intent number; every call with one
   outcome and that outcome for its last intent; sends equal to the reference's plus one per
   dispatch intent left in flight; each killed child's port reads at most one above the
   operations it logged and the completing child's equal to them, since a logged read is
   never repeated and an unlogged one may be, once (a saver seam fires on the framework's
   background thread, so its kill lands anywhere in the main thread's step, a read's append
   included); one approval, one closing event, one settled ledger entry; the export built
   from the log and round-tripped, its operations and claims the reference's.

The forecasts are in ``MANIFEST.md`` by family, written before the first run; a family the
reference crosses that the manifest does not name, or the reverse, fails the manifest test.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
import subprocess
import sys
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row

from leaveimpact.adapters.object_store.layout import (
    inventory_key,
    inventory_prefix,
    run_export_key,
    run_prefix,
)
from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.agent.ledger import EntryKind
from leaveimpact.agent.log_events import EventKind, LoggedEvent, event_digest, kind_of
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import AdmissionReceipt, AdmissionRequest, LogStore
from leaveimpact.agent.log_transition import calls_of
from leaveimpact.core import PublicationStatus, decode_export_bytes, export_bytes
from leaveimpact.core.inventory import decode_inventory_bytes
from leaveimpact.core.run_export import RunExport
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.crash import injector
from tests.crash.child import (
    ATTEMPT_ASKED,
    LEDGER,
    MODE,
    NONCE,
    OBJECTS,
    READER,
    REQUEST,
    RUN,
    SCHEMA,
    WORLD,
    application_of,
    connect_in,
)
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import loaded_world

REPOSITORY = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("MANIFEST.md")
ATTEMPT = 1
PLENTY = 10**15
CHILD_TIMEOUT_S = 240
SESSIONS_DEADLINE_S = 30.0
RECOVERY_EVERY = 16
"""Every sixteenth crossing of the reference gets the recovery rows: seven sampled kills, each
with one row per family the recovering child crosses, about 170 rows beside the 112; at
twelve the matrix took ten and a half minutes."""
COMMAND_MODES = ("admit", "admit-refused", "publish", "inventory")
"""The job seam's commands the matrix kills (the ruling on placement and acceptance, part 8):
admission on its receipt path and on its refusal path (a second attempt asked while the
first is open), publication of a completed attempt, and the inventory over a published
one. Each gets one row per crossing of its uninterrupted run; no recovery-process rows, a
command's recovery being one call, so a kill there is the first-process row again."""
COMMAND_ENDINGS = {
    "admit": "admitted",
    "admit-refused": "refused",
    "publish": PublicationStatus.PUBLISHED.value,
    "inventory": "written",
}
"""What each mode's child prints when it ran whole, killed or not before."""


# --- Preparation -----------------------------------------------------------------------------


@dataclass(frozen=True)
class Prepared:
    """What every child shares: the pickled context and systems, and the admitted inputs."""

    url: str
    world_file: Path
    inputs: Any
    directory: Path


def prepare(url: str, directory: Path) -> Prepared:
    """The golden world's first scenario, its systems pickled once for every child."""
    world: SealedWorld = loaded_world("golden")
    context = world.context_of(world.scenarios[0])
    systems = systems_holding(world)
    world_file = directory / "world.pickle"
    with world_file.open("wb") as held:
        pickle.dump((context, systems), held)
    return Prepared(url, world_file, support.admitted_inputs(context), directory)


def admin_connection(url: str) -> psycopg.Connection[Any]:
    return psycopg.connect(url, connect_timeout=10, autocommit=True)


def new_schema(url: str) -> str:
    schema = f"crash_{uuid4().hex[:12]}"
    with admin_connection(url) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    return schema


def drop_schema(url: str, schema: str) -> None:
    with admin_connection(url) as admin:
        admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def threshold_set(prepared: Prepared, schema: str) -> LogStore:
    """A store over ``schema`` with the tables ensured and the threshold set, nothing admitted."""
    store = LogStore(dsn=prepared.url, connect=connect_in(schema, "crash-parent"))
    store.ensure_schema()
    store.set_threshold(
        LEDGER,
        PLENTY,
        authority="operator:crash",
        registration_commit=cases.COMMIT,
        limit_pico_usd=PLENTY,
    )
    return store


def admitted(prepared: Prepared, schema: str) -> LogStore:
    """A store over ``schema`` with the tables ensured, the threshold set and the reference
    run admitted."""
    store = threshold_set(prepared, schema)
    receipt = store.admit(
        AdmissionRequest(
            f"req-{uuid4().hex[:12]}", prepared.inputs, support.ADMITTER, LEDGER, histories.RULES
        )
    )
    assert isinstance(receipt, AdmissionReceipt), receipt
    return store


# --- Children --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Ended:
    """How a child ended: its exit code, its one JSON line when it exited normally, its
    standard error, and the crossings its process recorded in order."""

    code: int
    ending: dict[str, Any] | None
    stderr: str
    crossings: tuple[str, ...]
    reads: int
    """The port reads this process witnessed."""

    @property
    def last_crossing(self) -> str | None:
        return self.crossings[-1] if self.crossings else None


RECOVERED_ENDINGS = frozenset({("closed", "completed"), ("closed_already", "completed")})
"""The endings a recovering child may report: it completed the attempt, or found it closed
(a kill after the closing event committed, the first run's finding against the manifest)."""


def start_child(
    prepared: Prepared,
    schema: str,
    record: Path,
    *,
    target: str | None,
    nonce: str,
    mode: str = "work",
    objects: Path | None = None,
    request: str | None = None,
    attempt: int | None = None,
) -> Ended:
    """One child in ``mode`` over ``schema``, killed at ``target`` or left to run; ``objects``
    is the local object store's root for the publish and inventory modes, ``request`` and
    ``attempt`` the admit mode's request identity and attempt number."""
    env = {
        **os.environ,
        "DATABASE_URL": prepared.url,
        SCHEMA: schema,
        WORLD: str(prepared.world_file),
        NONCE: nonce,
        MODE: mode,
        injector.RECORD: str(record),
    }
    env.pop(injector.TARGET, None)
    if target is not None:
        env[injector.TARGET] = target
    if objects is not None:
        env[OBJECTS] = str(objects)
    if request is not None:
        env[REQUEST] = request
    if attempt is not None:
        env[ATTEMPT_ASKED] = str(attempt)
    before = len(injector.read_record(record))
    completed = subprocess.run(
        [sys.executable, "-m", "tests.crash.child"],
        cwd=REPOSITORY,
        env=env,
        capture_output=True,
        text=True,
        timeout=CHILD_TIMEOUT_S,
        check=False,
    )
    lines = injector.read_record(record)[before:]
    ending = None
    for line in completed.stdout.splitlines():
        if line.startswith("{"):
            ending = json.loads(line)
    crossings = tuple(line["crossing"] for line in lines if "crossing" in line)
    reads = sum(line.get("witness") == "read" for line in lines)
    return Ended(completed.returncode, ending, completed.stderr[-2000:], crossings, reads)


def wait_sessions_ended(url: str, schema: str) -> None:
    """A killed process is gone at once; a statement it had in flight can still finish on
    the server, and a read before that would describe a state about to change."""
    deadline = time.monotonic() + SESSIONS_DEADLINE_S
    with admin_connection(url) as admin:
        while time.monotonic() < deadline:
            row = admin.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE application_name = %s",
                (application_of(schema),),
            ).fetchone()
            if row is not None and int(row[0]) == 0:
                return
            time.sleep(0.05)
    raise AssertionError(f"sessions of {application_of(schema)} never ended")


# --- The boundary ----------------------------------------------------------------------------


def checkpointed(
    url: str, schema: str, thread: str
) -> list[tuple[dict[str, str], list[dict[str, str]]]]:
    """Every checkpoint of ``thread``: its reached map and the reached maps of its pending
    writes, read through a plain saver of the pinned library."""
    connection = psycopg.Connection[DictRow].connect(
        make_conninfo(url, options=f"-c search_path={schema}"),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    try:
        saver = PostgresSaver(connection)
        held: list[tuple[dict[str, str], list[dict[str, str]]]] = []
        for checkpoint in saver.list({"configurable": {"thread_id": thread}}):
            values = checkpoint.checkpoint.get("channel_values", {})
            reached = dict(values.get("reached", {}) or {})
            pending: list[dict[str, str]] = []
            for _task, channel, value in checkpoint.pending_writes or ():
                if channel == "reached" and isinstance(value, dict):
                    pending.append(dict(value))  # type: ignore[arg-type]
            held.append((reached, pending))
        return held
    finally:
        connection.close()


def boundary_violations(
    events: Sequence[LoggedEvent],
    checkpoints: Sequence[tuple[dict[str, str], list[dict[str, str]]]],
) -> list[str]:
    """Each position and digest a checkpoint or a pending write represents, checked against
    the log on its own, nothing merged first."""
    digests = {str(e.position): event_digest(e.event) for e in events}
    found: list[str] = []
    for index, (reached, pending) in enumerate(checkpoints):
        for label, held in (
            ("checkpoint", reached),
            *((f"pending write {i}", p) for i, p in enumerate(pending)),
        ):
            for position, digest in held.items():
                if digests.get(position) != digest:
                    found.append(
                        f"{label} {index} represents position {position} with {digest[:12]}, "
                        f"the log holds {str(digests.get(position))[:12]}"
                    )
    return found


# --- Rows ------------------------------------------------------------------------------------


@dataclass
class Reference:
    """The uninterrupted run: its crossings in order, its log and its export, and what its
    record witnessed."""

    crossings: tuple[str, ...]
    events: tuple[LoggedEvent, ...]
    export: RunExport
    sends: int
    reads: int


@dataclass
class RowResult:
    kills: tuple[str, ...]
    findings: list[str] = field(default_factory=list[str])
    children: list[dict[str, Any] | None] = field(default_factory=list[dict[str, Any] | None])
    schema: str = ""

    @property
    def passed(self) -> bool:
        return not self.findings


def run_reference(prepared: Prepared) -> Reference:
    schema = new_schema(prepared.url)
    try:
        store = admitted(prepared, schema)
        record = prepared.directory / f"{schema}.jsonl"
        ended = start_child(prepared, schema, record, target=None, nonce="nonce-reference")
        assert ended.code == 0 and ended.ending is not None, (ended.code, ended.stderr)
        assert ended.ending["kind"] == "closed" and ended.ending["detail"] == "completed", (
            ended.ending
        )
        events = store.events(RUN, ATTEMPT)
        export = export_of(store.load(RUN, ATTEMPT, rules=histories.RULES))
        lines = injector.read_record(record)
        return Reference(
            ended.crossings,
            events,
            export,
            sum(line.get("witness") == "send" for line in lines),
            sum(line.get("witness") == "read" for line in lines),
        )
    finally:
        drop_schema(prepared.url, schema)


def rows_for(prepared: Prepared, reference: Reference) -> list[tuple[str, ...]]:
    """One row per crossing, and for every ``RECOVERY_EVERY``-th crossing one recovery row per
    family the recovering child crosses, read off a scout of that recovery (the worker
    group's review, sixth finding, and its second read's third: a lost outcome makes the
    recovery append an intent or a count start the reference's suffix no longer holds, so
    the targets come from the recovery's own path, never from the reference's)."""
    rows: list[tuple[str, ...]] = [(crossing,) for crossing in reference.crossings]
    for index, crossing in enumerate(reference.crossings):
        if index % RECOVERY_EVERY != RECOVERY_EVERY // 2:
            continue
        rows.extend((crossing, target) for target in scout_recovery(prepared, crossing))
    return rows


def scout_recovery(prepared: Prepared, first: str) -> tuple[str, ...]:
    """The families a recovering child crosses after a kill at ``first``, at occurrence one:
    the first child killed there, a second child left to run, its crossings read. The load's
    read and the saver's seams are left out, since a kill there is the first-process rows'
    already; a recovery that finds the attempt closed crosses nothing and gets no row."""
    schema = new_schema(prepared.url)
    record = prepared.directory / f"{schema}.jsonl"
    try:
        admitted(prepared, schema)
        killed = start_child(prepared, schema, record, target=first, nonce="nonce-scout-0")
        assert killed.code == injector.KILL_CODE and killed.last_crossing == first, (
            first,
            killed.code,
            killed.last_crossing,
            killed.stderr[-400:],
        )
        wait_sessions_ended(prepared.url, schema)
        recovered = start_child(prepared, schema, record, target=None, nonce="nonce-scout-1")
        # The exit code alone accepts a worker that ended ``left_open`` (the log unavailable,
        # a claim refused) and crossed nothing, which would scout no target and silently
        # drop the kill's recovery rows (the commands group's review, fourth finding); the
        # scout holds the recovery to the ending ``run_row`` holds the final child to.
        assert recovered.code == 0 and recovered.ending is not None, (
            first,
            recovered.code,
            recovered.stderr[-400:],
        )
        assert (recovered.ending["kind"], recovered.ending["detail"]) in RECOVERED_ENDINGS, (
            first,
            recovered.ending,
        )
        families: list[str] = []
        for crossing in recovered.crossings:
            family = injector.family(crossing)
            if family.split(":")[0] in ("load", "checkpoint", "writes"):
                continue
            if family not in families:
                families.append(family)
        return tuple(f"{family}#1" for family in families)
    finally:
        drop_schema(prepared.url, schema)


def run_row(
    prepared: Prepared, reference: Reference, kills: tuple[str, ...], *, keep: bool = False
) -> RowResult:
    result = RowResult(kills)
    schema = new_schema(prepared.url)
    result.schema = schema
    record = prepared.directory / f"{schema}.jsonl"
    try:
        store = admitted(prepared, schema)
        snapshots: list[tuple[LoggedEvent, ...]] = []
        accounted: list[tuple[int, int]] = []
        logged_before = 0
        for index, target in enumerate(kills):
            ended = start_child(prepared, schema, record, target=target, nonce=f"nonce-{index}")
            result.children.append(ended.ending)
            if ended.code != injector.KILL_CODE or ended.last_crossing != target:
                result.findings.append(
                    f"child {index} did not die at {target}: code {ended.code}, last crossing "
                    f"{ended.last_crossing}, ending {ended.ending}, stderr {ended.stderr[-400:]!r}"
                )
                return result
            wait_sessions_ended(prepared.url, schema)
            events = store.events(RUN, ATTEMPT)
            snapshots.append(events)
            accounted.append((ended.reads, _operations(events) - logged_before))
            logged_before = _operations(events)
            generation = sum(kind_of(e.event) is EventKind.SEGMENT_STARTED for e in events)
            if generation:
                thread = f"{RUN}/{ATTEMPT}/{generation}"
                result.findings.extend(
                    boundary_violations(events, checkpointed(prepared.url, schema, thread))
                )
        final = start_child(prepared, schema, record, target=None, nonce="nonce-final")
        result.children.append(final.ending)
        # A kill after the closing event committed (the terminal step's saver writes) leaves
        # a closed attempt, which the recovery finds at its load and leaves: the first run's
        # finding against the manifest's forecast, now part of it.
        if (
            final.code != 0
            or final.ending is None
            or (final.ending["kind"], final.ending["detail"]) not in RECOVERED_ENDINGS
        ):
            result.findings.append(
                f"recovery did not complete: code {final.code}, ending {final.ending}, "
                f"stderr {final.stderr[-400:]!r}"
            )
            return result
        events = store.events(RUN, ATTEMPT)
        accounted.append((final.reads, _operations(events) - logged_before))
        lines = injector.read_record(record)
        result.findings.extend(reconcile(reference, snapshots, events, lines, store, accounted))
        return result
    finally:
        if not keep:
            drop_schema(prepared.url, schema)


def reconcile(
    reference: Reference,
    snapshots: Sequence[tuple[LoggedEvent, ...]],
    final: tuple[LoggedEvent, ...],
    lines: Sequence[dict[str, Any]],
    store: LogStore,
    accounted: Sequence[tuple[int, int]],
) -> list[str]:
    """The findings against the reference and the snapshots; ``accounted`` holds, per child in
    order, the port reads it witnessed and the operations it logged, the last being the
    child that completed."""
    found: list[str] = []
    for index, snapshot in enumerate(snapshots):
        if final[: len(snapshot)] != snapshot:
            found.append(f"the prefix left by kill {index} was rewritten")
    if support.settled(final) != support.settled(reference.events):
        found.append("the settled events differ from the reference's")
    pending_each = [set(support.in_flight(snapshot)) for snapshot in snapshots]
    pending: set[tuple[object, ...]] = set()
    for each in pending_each:
        pending |= each
    final_pending = set(support.in_flight(final))
    if final_pending != pending:
        found.append(
            f"in flight at the end {sorted(map(str, final_pending))}, the kills left "
            f"{sorted(map(str, pending))}"
        )
    claims = sum(kind_of(e.event) is EventKind.SEGMENT_STARTED for e in final)
    expected_length = len(reference.events) + (claims - 1) + len(final_pending)
    if len(final) != expected_length:
        found.append(
            f"{len(final)} events, expected {expected_length} (reference "
            f"{len(reference.events)}, {claims} claims, {len(final_pending)} in flight)"
        )
    state = store.load(RUN, ATTEMPT, rules=histories.RULES)
    for call in calls_of(state):
        if set(call.outcomes) != {call.last_number}:
            found.append(
                f"call {call.ordinal} holds outcomes {sorted(call.outcomes)} for intents up to "
                f"{call.last_number}"
            )
    kinds = [kind_of(e.event) for e in final]
    for kind in (EventKind.APPROVED, EventKind.COMPLETED):
        if kinds.count(kind) != 1:
            found.append(f"{kind.value} appears {kinds.count(kind)} times")
    settled_entries = [e for e in store.ledger_view(LEDGER).entries if e.kind is EntryKind.SETTLED]
    if len(settled_entries) != 1:
        found.append(f"{len(settled_entries)} settled ledger entries")
    sends = sum(line.get("witness") == "send" for line in lines)
    dispatch_pending = sum(
        1 for key in final_pending if len(key) == 2 and all(isinstance(k, int) for k in key)
    )
    if sends != reference.sends + dispatch_pending:
        found.append(f"{sends} sends, expected {reference.sends} + {dispatch_pending} in flight")
    for key in final_pending:
        if len(key) == 2 and all(isinstance(k, int) for k in key):
            call, number = key
            held = [c for c in calls_of(state) if c.ordinal == call]
            if held and number in held[0].outcomes:
                found.append(f"a send was answered under the in-flight intent {key}")
    # A logged read is never repeated and an unlogged one may be, once: a killed child read
    # at most one more time than it logged (the read in flight when it died, wherever the
    # kill landed in its step), and the completing child read exactly what it logged.
    for index, (reads, logged) in enumerate(accounted[:-1]):
        if not 0 <= reads - logged <= 1:
            found.append(f"child {index} made {reads} port reads and logged {logged} operations")
    reads, logged = accounted[-1]
    if reads != logged:
        found.append(f"the completing child made {reads} port reads and logged {logged} operations")
    if sum(r for r, _ in accounted) < reference.reads:
        found.append(
            f"{sum(r for r, _ in accounted)} port reads in all, fewer than the reference's "
            f"{reference.reads}"
        )
    export = export_of(state)
    if decode_export_bytes(export_bytes(export)) != export:
        found.append("the export does not round-trip")
    if _positionless(export) != _positionless(reference.export):
        found.append("the export's operations differ from the reference's beyond their positions")
    if export.trace.claims != reference.export.trace.claims:
        found.append("the export's claims differ from the reference's")
    return found


def _operations(events: Sequence[LoggedEvent]) -> int:
    return sum(kind_of(e.event) is EventKind.OPERATION for e in events)


def _positionless(export: RunExport) -> list[tuple[object, ...]]:
    """The export's operations without their log positions, which a recovery's extra claim
    shifts; everything else about a read is the same whoever made it."""
    return [
        (o.id, o.origin, o.tool, o.source, o.arguments, o.outcome) for o in export.trace.operations
    ]


# --- The commands ----------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandState:
    """What a command's child runs over: the parent's store, the object store's root, the
    child's mode and the admit mode's request identity and attempt number."""

    store: LogStore
    objects: Path
    child_mode: str
    request: str | None
    attempt: int | None


def command_state(prepared: Prepared, schema: str, record: Path, mode: str) -> CommandState:
    """The store and object root a command in ``mode`` is run over, prepared by the parent:
    the threshold alone for an admission; the reference attempt admitted and open for the
    refused one; completed by an uninterrupted worker child for a publication; completed and
    published by an uninterrupted publish child for the inventory."""
    objects = prepared.directory / f"{schema}-objects"
    if mode == "admit":
        return CommandState(threshold_set(prepared, schema), objects, "admit", f"req-{schema}", 1)
    if mode == "admit-refused":
        return CommandState(admitted(prepared, schema), objects, "admit", f"req-{schema}-2", 2)
    store = admitted(prepared, schema)
    worked = start_child(prepared, schema, record, target=None, nonce="nonce-command-work")
    assert worked.code == 0 and worked.ending is not None, (mode, worked.code, worked.stderr[-400:])
    assert (worked.ending["kind"], worked.ending["detail"]) == ("closed", "completed"), (
        worked.ending
    )
    if mode == "publish":
        return CommandState(store, objects, "publish", None, None)
    assert mode == "inventory", mode
    published = start_child(
        prepared,
        schema,
        record,
        target=None,
        nonce="nonce-command-publish",
        mode="publish",
        objects=objects,
    )
    assert published.code == 0 and published.ending is not None, (
        published.code,
        published.stderr[-400:],
    )
    assert published.ending["kind"] == COMMAND_ENDINGS["publish"], published.ending
    return CommandState(store, objects, "inventory", None, None)


def start_command(
    prepared: Prepared,
    schema: str,
    record: Path,
    state: CommandState,
    *,
    target: str | None,
    nonce: str,
) -> Ended:
    return start_child(
        prepared,
        schema,
        record,
        target=target,
        nonce=nonce,
        mode=state.child_mode,
        objects=state.objects,
        request=state.request,
        attempt=state.attempt,
    )


@dataclass
class CommandReference:
    """A command's uninterrupted run: its mode and its crossings in order, one row each."""

    mode: str
    crossings: tuple[str, ...]

    @property
    def families(self) -> set[str]:
        return {f"{self.mode}/{injector.family(c)}" for c in self.crossings}


def run_command_reference(prepared: Prepared, mode: str) -> CommandReference:
    schema = new_schema(prepared.url)
    record = prepared.directory / f"{schema}.jsonl"
    try:
        state = command_state(prepared, schema, record, mode)
        ended = start_command(prepared, schema, record, state, target=None, nonce="nonce-command")
        assert ended.code == 0 and ended.ending is not None, (mode, ended.code, ended.stderr[-400:])
        findings = reconcile_command(mode, prepared, state, ended, killed_at=None)
        assert not findings, (mode, findings)
        return CommandReference(mode, ended.crossings)
    finally:
        drop_schema(prepared.url, schema)


def command_rows(references: Sequence[CommandReference]) -> list[tuple[str, str]]:
    """One row per crossing of each command's reference: the mode and the kill point."""
    return [
        (reference.mode, crossing) for reference in references for crossing in reference.crossings
    ]


def run_command_row(prepared: Prepared, mode: str, kill: str, *, keep: bool = False) -> RowResult:
    result = RowResult((f"{mode}/{kill}",))
    schema = new_schema(prepared.url)
    result.schema = schema
    record = prepared.directory / f"{schema}.jsonl"
    try:
        state = command_state(prepared, schema, record, mode)
        killed = start_command(
            prepared, schema, record, state, target=kill, nonce="nonce-command-0"
        )
        result.children.append(killed.ending)
        if killed.code != injector.KILL_CODE or killed.last_crossing != kill:
            result.findings.append(
                f"the child did not die at {kill}: code {killed.code}, last crossing "
                f"{killed.last_crossing}, ending {killed.ending}, stderr {killed.stderr[-400:]!r}"
            )
            return result
        wait_sessions_ended(prepared.url, schema)
        again = start_command(prepared, schema, record, state, target=None, nonce="nonce-command-1")
        result.children.append(again.ending)
        if again.code != 0 or again.ending is None:
            result.findings.append(
                f"the command run again did not complete: code {again.code}, stderr "
                f"{again.stderr[-400:]!r}"
            )
            return result
        result.findings.extend(reconcile_command(mode, prepared, state, again, killed_at=kill))
        return result
    finally:
        if not keep:
            drop_schema(prepared.url, schema)


def reconcile_command(
    mode: str, prepared: Prepared, state: CommandState, ended: Ended, *, killed_at: str | None
) -> list[str]:
    """The findings against the command's forecast once its last child ran whole: the
    ending it printed, and the store and the object store as the manifest says they stand."""
    found: list[str] = []
    assert ended.ending is not None
    if ended.ending["kind"] != COMMAND_ENDINGS[mode]:
        found.append(f"the command ended {ended.ending}, expected {COMMAND_ENDINGS[mode]}")
    store = state.store
    version = prepared.inputs.context.world_version
    snapshot = store.snapshot(LEDGER)
    attempts = [each.attempt for each in snapshot.attempts]
    refused = [each.attempt for each in snapshot.refused]
    entries = [entry.kind for entry in store.ledger_view(LEDGER).entries]
    reader = LocalObjectReader(state.objects)
    if mode in ("admit", "admit-refused"):
        if attempts != [1]:
            found.append(f"attempts {attempts}, expected the first alone")
        if entries != [EntryKind.THRESHOLD_SET, EntryKind.ADMITTED]:
            found.append(
                f"ledger entries {[e.value for e in entries]}, expected the threshold and one "
                "admission"
            )
        expected_refusals = [2] if mode == "admit-refused" else []
        if refused != expected_refusals:
            found.append(f"refused requests for attempts {refused}, expected {expected_refusals}")
        events = store.events(RUN, ATTEMPT)
        if len(events) != 1:
            found.append(f"{len(events)} events of the first attempt, expected its admission alone")
    elif mode == "publish":
        identity = run_export_key(version, RUN, ATTEMPT, READER)
        record = store.publication_of(RUN, ATTEMPT)
        if record is None or record.state is not PublicationStatus.PUBLISHED:
            found.append(f"the publication record is {record}, expected published")
        elif record.object_identity != identity or record.repaired_from_commit is not None:
            found.append(
                f"the record names {record.object_identity} repaired from "
                f"{record.repaired_from_commit}"
            )
        keys = reader.list_keys(run_prefix(version, RUN, ATTEMPT))
        if keys != (identity,):
            found.append(f"objects under the run's prefix {keys}, expected {identity} alone")
        else:
            held = reader.get(identity)
            assert held is not None
            digest = hashlib.sha256(held.content).hexdigest()
            if record is not None and record.object_digest != digest:
                found.append("the record's digest is not the object's")
            built = export_bytes(export_of(store.load(RUN, ATTEMPT, rules=histories.RULES)))
            if built != held.content:
                found.append("the object is not the reader's export of the log")
    else:
        assert mode == "inventory", mode
        keys = reader.list_keys(inventory_prefix(version))
        expected = 2 if killed_at is not None and injector.family(killed_at) == "put:after" else 1
        if len(keys) != expected:
            found.append(f"{len(keys)} inventories stored, expected {expected}")
        if ended.ending.get("outcome") != "created":
            found.append(f"the inventory's put was {ended.ending.get('outcome')}, expected created")
        for key in keys:
            held = reader.get(key)
            assert held is not None
            digest = hashlib.sha256(held.content).hexdigest()
            if key != inventory_key(version, digest):
                found.append(f"{key} does not digest to its name")
            inventory = decode_inventory_bytes(held.content)
            listed = inventory.attempts
            if len(listed) != 1 or not listed[0].closed:
                found.append(f"{key} lists {len(listed)} attempts, expected the closed one")
                continue
            publication = listed[0].publication
            if publication is None or publication.status is not PublicationStatus.PUBLISHED:
                found.append(f"{key} lists the attempt's publication as {publication}")
    return found


# --- The matrix ------------------------------------------------------------------------------


@dataclass
class MatrixResult:
    reference: Reference
    commands: list[CommandReference]
    rows: list[RowResult]

    @property
    def failures(self) -> list[RowResult]:
        return [row for row in self.rows if not row.passed]

    @property
    def families(self) -> set[str]:
        """Every family a reference crosses, the worker's as they are and a command's under
        its mode: what the manifest must name, each once."""
        crossed = {injector.family(c) for c in self.reference.crossings}
        for command in self.commands:
            crossed |= command.families
        return crossed

    def summary(self) -> dict[str, Any]:
        return {
            "reference_crossings": len(self.reference.crossings),
            "families": sorted({injector.family(c) for c in self.reference.crossings}),
            "command_crossings": {c.mode: len(c.crossings) for c in self.commands},
            "command_families": sorted(f for c in self.commands for f in c.families),
            "rows": len(self.rows),
            "passed": len(self.rows) - len(self.failures),
            "failed": [{"kills": row.kills, "findings": row.findings} for row in self.failures],
        }


def run_matrix(
    url: str, directory: Path, *, workers: int = 6, only: Sequence[str] | None = None
) -> MatrixResult:
    """The worker's reference and each command's, then every row, ``workers`` at a time;
    ``only`` restricts the rows to those whose name (a kill point, or ``<mode>/<kill point>``
    for a command's) matches one of the patterns."""
    prepared = prepare(url, directory)
    reference = run_reference(prepared)
    commands = [run_command_reference(prepared, mode) for mode in COMMAND_MODES]
    rows = rows_for(prepared, reference)
    for_commands = command_rows(commands)
    if only:
        rows = [row for row in rows if any(re.search(pattern, row[0]) for pattern in only)]
        for_commands = [
            (mode, kill)
            for mode, kill in for_commands
            if any(re.search(pattern, f"{mode}/{kill}") for pattern in only)
        ]

    def row(kills: tuple[str, ...]) -> RowResult:
        try:
            return run_row(prepared, reference, kills)
        except Exception as exc:  # noqa: BLE001 - a row's own fault is its finding, not the matrix's end
            failed = RowResult(kills)
            failed.findings.append(f"the row raised {type(exc).__name__}: {exc}"[:600])
            return failed

    def command_row(named: tuple[str, str]) -> RowResult:
        mode, kill = named
        try:
            return run_command_row(prepared, mode, kill)
        except Exception as exc:  # noqa: BLE001 - as above
            failed = RowResult((f"{mode}/{kill}",))
            failed.findings.append(f"the row raised {type(exc).__name__}: {exc}"[:600])
            return failed

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(row, rows))
        results.extend(pool.map(command_row, for_commands))
    return MatrixResult(reference, commands, results)


def manifest_families() -> set[str]:
    """The kill-point families the manifest forecasts: the backticked first cell of each row."""
    return {
        match.group(1)
        for line in MANIFEST.read_text(encoding="utf-8").splitlines()
        if line.startswith("| `")
        for match in [re.match(r"\| `([^`]+)`", line)]
        if match
    }


__all__ = [
    "COMMAND_MODES",
    "MANIFEST",
    "CommandReference",
    "MatrixResult",
    "Reference",
    "RowResult",
    "command_rows",
    "manifest_families",
    "prepare",
    "rows_for",
    "run_command_reference",
    "run_command_row",
    "run_matrix",
    "run_reference",
    "run_row",
]
