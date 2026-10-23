"""The restore drill's verification: what a restored scratch database must show before a
backup counts as recoverable (the demo milestone's backup ruling, as the platform's ticket
settled it).

A listing of the archive is a preflight; the verification is the restore itself, read by
the application that will serve from it. The platform's monthly unit restores the newest
object into a scratch database, runs the recovery procedure the runbook states (both
bootstraps, idempotent), and calls this with the capture the backup recorded on the object:
the ``ledger_capture`` view's rows, read in the session that exported the dump's snapshot,
so the capture and the dump are one instant. The checks, in order: the app schema at this
code's version; the corpus cache marking the served world ready, since the replay routes
answer 503 without it; the restored view equal to the capture row for row, the one
comparison against the dump's own snapshot; every captured ledger's head equal to the fold
of its entries, which the log store refuses to read otherwise; every closed attempt's charge
recomputed by the account rule from its restored log and equal to what the closing event
logged and the ledger's settled entry holds, the retained liability's check, done here
because that rule lives in ``core.run_account`` and is not a column the capture could hold;
the listing of the served world admitting at least one row; and one listed replay admitted,
folded to its export and built into the report view, the page a visitor would read.

Nothing here writes, claims, admits or dispatches: the reads are the surface's own (the
read model's admission, the reader's fold, the report's view) and this module imports no
module that sends a request to a model or a vendor, which a test holds by the module's
import edges; the integration test runs it under the suite's network block with PostgreSQL
the one allowed host, so a call that left the database would fail there. That is what
"execution disabled" means for the drill: a restored open attempt is read, never resumed.

Every check answers a ``Check`` with a name, whether it passed and one line of detail that
names ids and counts, never a value from the data; the command prints the lines and exits
0 only when every check passed. A store that does not answer is not a failed check but a
refusal the command names, since the drill cannot tell a bad backup from an absent
database and must not call one the other.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from leaveimpact.agent.inventory import StoreSnapshot
from leaveimpact.agent.ledger import EntryKind
from leaveimpact.agent.log_events import Admitted
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import LedgerView, LogStoreInvariantBroken
from leaveimpact.agent.log_transition import AttemptState, Rules, rules_differ
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.read_model import (
    PublishableReads,
    admitted,
    instants_of,
    listing,
    replay_view,
)
from leaveimpact.app.report import report_view
from leaveimpact.app.store import AppStoreInvariantBroken
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.run_account import settle


class RestoreLog(Protocol):
    """The log store's reads the drill makes, over the restored database."""

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState: ...

    def ledger_view(self, ledger_id: str) -> LedgerView: ...

    def snapshot(self, ledger_id: str) -> StoreSnapshot: ...


@dataclass(frozen=True, slots=True)
class RestoreReads:
    """Everything the verification reads, bound by the command to the restored database:
    the app schema's support, the view's rows as the backup script reads them, the cache's
    ready versions, the publishable rows, the log, and the configuration and rules the
    surface serves under."""

    app_schema: Callable[[], bool]
    ledger_capture: Callable[[], list[JsonObject]]
    cache_versions: Callable[[], frozenset[WorldVersion]]
    rows: PublishableReads
    log: RestoreLog
    configuration: DemoConfiguration
    rules: Rules


@dataclass(frozen=True, slots=True)
class Check:
    """One check's answer: its name, whether it passed, and one line naming what it saw."""

    name: str
    passed: bool
    detail: str


def verify(capture: list[JsonObject], reads: RestoreReads) -> tuple[Check, ...]:
    """Every check over ``reads``, in the module's order, against the backup's ``capture``;
    an invariant the stores refuse while a check reads is that check's failure, named."""
    checks: list[Check] = []
    for check in (
        lambda: app_schema_check(reads),
        lambda: cache_check(reads),
        lambda: capture_check(capture, reads),
        lambda: fold_check(capture, reads),
        lambda: settlement_check(reads),
        lambda: listing_check(reads),
        lambda: replay_check(reads),
    ):
        try:
            checks.append(check())
        except (LogStoreInvariantBroken, AppStoreInvariantBroken, ValueError) as error:
            checks.append(Check(_NAMES[len(checks)], False, f"refused while reading: {error}"))
    return tuple(checks)


_NAMES = (
    "app-schema",
    "served-world-cached",
    "ledger-capture",
    "ledger-fold",
    "settlements",
    "listing",
    "replay",
)


def app_schema_check(reads: RestoreReads) -> Check:
    """The app schema at this code's version after the recovery procedure's bootstrap."""
    supported = reads.app_schema()
    return Check(
        _NAMES[0],
        supported,
        "the app schema is at this code's version"
        if supported
        else "the app schema is missing or at another version",
    )


def cache_check(reads: RestoreReads) -> Check:
    """The corpus cache inside the dump marks the served world ready."""
    served = reads.configuration.served_world_version
    ready = served in reads.cache_versions()
    return Check(
        _NAMES[1],
        ready,
        f"the cache serves the served world {served[:12]}…"
        if ready
        else f"the cache does not mark the served world {served[:12]}… ready",
    )


def capture_check(capture: list[JsonObject], reads: RestoreReads) -> Check:
    """The restored view's rows equal the capture the backup recorded, row for row."""
    restored = reads.ledger_capture()
    if restored == capture:
        return Check(_NAMES[2], True, f"{len(capture)} ledger rows equal the capture")
    captured = [str(row.get("ledger_id")) for row in capture]
    held = [str(row.get("ledger_id")) for row in restored]
    differing = [name for name, row in zip(captured, capture, strict=True) if row not in restored]
    return Check(
        _NAMES[2],
        False,
        f"the capture names ledgers {captured} and the restored view {held}; captured rows "
        f"the view does not hold: {differing}",
    )


def fold_check(capture: list[JsonObject], reads: RestoreReads) -> Check:
    """Every captured ledger's head is what its entries fold to (the log store refuses the
    read otherwise) and states the capture's total and revision."""
    for row in capture:
        ledger_id = str(row.get("ledger_id"))
        view = reads.log.ledger_view(ledger_id)
        head = view.head
        if (head.total_pico_usd, head.revision) != (row.get("total_pico_usd"), row.get("revision")):
            return Check(
                _NAMES[3],
                False,
                f"ledger {ledger_id}'s head folds to revision {head.revision}; the capture "
                f"says {row.get('revision')}",
            )
    return Check(_NAMES[3], True, f"{len(capture)} ledger heads fold from their entries")


def settlement_check(reads: RestoreReads) -> Check:
    """Every closed attempt with a reservation admitted under the served rules: the charge
    the account rule computes from the restored log equals what its closing event logged
    and what the ledger's settled entry holds, at the revision the event names. An attempt
    admitted under another registration (the development runs before the freeze sit in
    the same database) cannot be folded under the rules the image ships, since the
    transition refuses rules that differ from the admission's; it is counted by name and
    not folded, and the ledger's fold check above still covers its entry."""
    snapshot = reads.log.snapshot(reads.configuration.ledger_id)
    settled_by_ledger: dict[str, dict[tuple[str, int], tuple[int, int]]] = {}
    checked = 0
    other_registration = 0
    for attempt in snapshot.attempts:
        if not attempt.closed or attempt.ledger_id is None:
            continue
        admission = attempt.events[0].event if attempt.events else None
        if isinstance(admission, Admitted) and rules_differ(admission.inputs, reads.rules):
            other_registration += 1
            continue
        if attempt.ledger_id not in settled_by_ledger:
            settled_by_ledger[attempt.ledger_id] = {
                (entry.run_id, entry.attempt): (entry.amount_pico_usd, entry.revision)
                for entry in reads.log.ledger_view(attempt.ledger_id).entries
                if entry.kind is EntryKind.SETTLED and entry.run_id is not None
                if entry.attempt is not None
            }
        state = reads.log.load(attempt.run_id, attempt.attempt, rules=reads.rules)
        closing = state.closed
        logged = getattr(closing.event, "settlement", None) if closing is not None else None
        where = f"run {attempt.run_id} attempt {attempt.attempt}"
        if logged is None:
            return Check(
                _NAMES[4], False, f"{where} is closed against a ledger with no settlement logged"
            )
        entry = settled_by_ledger[attempt.ledger_id].get((attempt.run_id, attempt.attempt))
        if entry is None:
            return Check(
                _NAMES[4], False, f"{where} has no settled entry on ledger {attempt.ledger_id}"
            )
        computed = settle(state.account).charged_pico_usd
        if (
            not (computed == logged.charged_pico_usd == entry[0])
            or entry[1] != logged.ledger_revision
        ):
            return Check(
                _NAMES[4],
                False,
                f"{where}: the account rule charges {computed}, the closing event logged "
                f"{logged.charged_pico_usd} at revision {logged.ledger_revision}, the ledger's "
                f"settled entry holds {entry[0]} at revision {entry[1]}",
            )
        checked += 1
    skipped = (
        f"; {other_registration} admitted under another registration, not folded"
        if other_registration
        else ""
    )
    return Check(
        _NAMES[4],
        True,
        f"{checked} closed attempts charged as the account rule, the closing event and the "
        f"ledger agree{skipped}",
    )


def listing_check(reads: RestoreReads) -> Check:
    """The served world's listing admits at least one published row."""
    rows = listing(reads.rows, reads.configuration)
    return Check(
        _NAMES[5],
        len(rows) > 0,
        f"{len(rows)} published replays of the served world"
        if rows
        else "no published replay of the served world: nothing the surface could serve",
    )


def replay_check(reads: RestoreReads) -> Check:
    """The first listed replay admitted for content, folded to its export and built into
    the report view, as the replay page would."""
    rows = listing(reads.rows, reads.configuration)
    if not rows:
        return Check(_NAMES[6], False, "no listed replay to serve")
    public_id = rows[0].public_id
    admission = admitted(public_id, reads.rows, reads.log, reads.configuration, reads.rules)
    if admission is None:
        return Check(_NAMES[6], False, f"{public_id} is listed and the admission refuses it")
    state = admission.state
    if state.closed is None:
        return Check(_NAMES[6], False, f"{public_id} is listed and its attempt is open")
    export = export_of(state)
    view = report_view(replay_view(admission), export, instants_of(state))
    return Check(
        _NAMES[6],
        True,
        f"{public_id} served: {len(state.events)} events folded, the report built with "
        f"{len(view.impacts)} impact sections",
    )
