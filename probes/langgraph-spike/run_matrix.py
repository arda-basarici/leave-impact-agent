"""The crash matrix: the scripted run killed at every seam crossing it makes, recovered by a
fresh process, and reconciled against both stores and an uninterrupted reference.

The criteria are the ``crash matrix``, ``approval`` and ``same seam twice`` rows of the
committed acceptance section in ``probes/README.md``. A reference child runs with no kill
target; its injector record is the list of crossings and its export, built from its log, is
what a recovered run is compared with. The reference is itself checked against the script
(the usage of each call, the three model calls, the nine operations, the model's reads with
their outcomes, the final claims, the driver's steps) before anything is compared with it.

One row per crossing, each in a schema of its own:

1. A child is started with the crossing as its kill target. The row goes on only if the
   child exited with the injector's code and its last recorded line is that crossing; any
   other ending fails the row as not reaching its target.
2. *The boundary.* Once the dead child's database sessions have ended, the parent reads the
   log and every checkpoint with its pending writes. The invariant: each result a
   checkpoint or a pending write represents, a position and a digest, is in the log with
   that digest. An older checkpoint is expected; a digest the log does not hold is a
   failure.
3. A second child recovers and must complete.
4. *Reconciliation.* The invariant again over every checkpoint; the final checkpoint's
   results equal to the logged ones by position, no position missing on either side; no
   append by any child of the row repeated an event the log held, read from the injector's
   record, where a killed child's repeats are too (the log itself cannot hold a second
   approval or a second terminal event, so counting its rows would prove nothing); the
   export built from the log byte-equal to the reference's with the duration masked; the
   export's duration positive and equal to the per-segment sum the database computes from
   the raw rows; each segment's last offset no later than the last line its own process
   wrote to the injector's record, on that process's clock.
5. *The expected triple.* Written here before any run, and applied to what was witnessed at
   the boundary, never to the crossing's name, since a saver seam can fire while a model
   call is in flight. At the boundary the log holds ``I`` intents and ``O`` outcomes and
   the injector's record ``R`` requests and ``P`` returned responses, with ``I >= R >= P >=
   O`` required. Recovery makes exactly one more dispatch for each of the three calls that
   has no outcome, so at completion the intents are ``I + (3 - O)``, the requests ``R + (3 -
   O)``, the returned responses ``P + (3 - O)``, and the retained outcomes three. A response
   returned and lost before its outcome was appended stays counted as returned.

The same-seam-twice variant repeats each row with the recovering child given the same kill
target. It ends *recovered* (killed there again, then a third child completed and
reconciled), *not reached again* (the recovery completed without crossing it, having reused
what the log held), or *failed*. The expected triple is applied from the last boundary.

Measured, per crossing: the tool dispatches the injector witnessed beyond the reference's,
the steps the recovery driver took, the recovered duration.

    uv run --group harness python probes/langgraph-spike/run_matrix.py --out DIR

It prints one JSON summary, with the rows that did not pass in full, and exits non-zero
unless every row passes. ``--only N`` runs the first N crossings, for development.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import sys
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import psycopg
from eventlog import (
    APPROVAL,
    MODEL_INTENT,
    MODEL_OUTCOME,
    RUN_TERMINAL,
    SEGMENT_STARTED,
    TOOL_RESULT,
    Event,
    connect,
    harness_revision,
)
from log_export import export_from_log
from parent import (
    PARENT,
    Ended,
    World,
    checkpointed,
    create_schema,
    drop_schema,
    logged,
    prepare_world,
    sessions_ended,
    start_child,
)
from run_uninterrupted import ATTEMPT, MODEL_READS, PINNED, RUN_ID
from seams import parts, read_record

from leaveimpact.core.claims_json import encode_claims
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_export_json import (
    _encode_outcome,  # pyright: ignore[reportPrivateUsage]
    export_bytes,
)

CALLS = 3
"""The script's model calls; each ends with exactly one retained outcome."""
HEALTHY_STEPS = ["ran from the start", "delivered the approval", "found complete"]
"""What the driver does on a run nothing interrupts."""


def digests_by_position(events: tuple[Event, ...]) -> dict[str, str]:
    """The digest of each logged result, under the key graph state holds it by."""
    held: dict[str, str] = {}
    for event in events:
        if event.kind in (TOOL_RESULT, MODEL_OUTCOME):
            held[event.position] = event.digest
        elif event.kind in (APPROVAL, RUN_TERMINAL):
            held[event.kind] = event.digest
    return held


def represented(checkpoint: dict[str, Any]) -> dict[str, str]:
    """Every result ``checkpoint`` represents: its state's and its pending writes'."""
    results = dict(checkpoint["results"])
    for task in checkpoint["pending"]:
        for channel, value in task:
            if channel == "results" and isinstance(value, dict):
                results.update(value)
    return results


def violations(store: list[dict[str, Any]], events: tuple[Event, ...]) -> list[dict[str, Any]]:
    """Each result a checkpoint represents that the log does not hold with the same digest."""
    in_log = digests_by_position(events)
    found: list[dict[str, Any]] = []
    for checkpoint in store:
        for position, digest in represented(checkpoint).items():
            if in_log.get(position) != digest:
                found.append(
                    {
                        "step": checkpoint["step"],
                        "position": position,
                        "checkpoint": digest,
                        "log": in_log.get(position),
                    }
                )
    return found


def witnessed(record: Path, events: tuple[Event, ...]) -> dict[str, int]:
    """The four counts: intents and outcomes in the log, requests and returned responses in
    the injector's record."""
    lines = read_record(str(record))
    return {
        "intents": sum(event.kind == MODEL_INTENT for event in events),
        "requests": sum(line["kind"] == "model_request" for line in lines),
        "responses": sum(line["kind"] == "model_response" for line in lines),
        "outcomes": sum(event.kind == MODEL_OUTCOME for event in events),
    }


def expected_at_completion(boundary: dict[str, int]) -> dict[str, int]:
    """The rule: one more dispatch for each call the boundary holds no outcome for."""
    owed = CALLS - boundary["outcomes"]
    return {
        "intents": boundary["intents"] + owed,
        "requests": boundary["requests"] + owed,
        "responses": boundary["responses"] + owed,
        "outcomes": CALLS,
    }


def masked(export: RunExport) -> bytes:
    """The canonical bytes of ``export`` with its duration set to zero."""
    usage = replace(export.record.usage, duration_ms=0)
    return export_bytes(replace(export, record=replace(export.record, usage=usage)))


def repeated(record: Path) -> list[str]:
    """The appends any child of the row made of an event the log already held."""
    return [line["event"] for line in read_record(str(record)) if line["kind"] == "repeated_append"]


def segment_offsets(url: str, schema: str) -> dict[int, int]:
    """Each segment's last durable offset, computed by the database from the raw rows."""
    with connect(url, schema, PARENT) as connection:
        rows = connection.execute(
            "SELECT segment, max(offset_ms) FROM events WHERE run_id = %s AND attempt = %s "
            "GROUP BY segment",
            (RUN_ID, ATTEMPT),
        ).fetchall()
    return {segment: offset for segment, offset in rows}


def outside_their_process(events: tuple[Event, ...], record: Path) -> list[int]:
    """The segments whose last offset is later than the last line their own process wrote to
    the injector's record, on that process's clock, which started before the segment's."""
    last_line: dict[int, int] = {}
    for line in read_record(str(record)):
        last_line[line["pid"]] = max(last_line.get(line["pid"], 0), line["at_ms"])
    last_offset: dict[int, int] = {}
    for event in events:
        last_offset[event.segment] = max(last_offset.get(event.segment, 0), event.offset_ms)
    return [
        event.segment
        for event in events
        if event.kind == SEGMENT_STARTED
        and last_offset[event.segment] > last_line.get(event.data["pid"], -1)
    ]


def dispatches(record: Path) -> int:
    return sum(line["kind"] == "tool_dispatch" for line in read_record(str(record)))


class Matrix:
    """One execution of the matrix: the connections, the world and the reference."""

    def __init__(self, url: str, admin: psycopg.Connection[Any], world: World, work: Path) -> None:
        self.url = url
        self.admin = admin
        self.world = world
        self.work = work
        self.schemas: list[str] = []
        self.lock = threading.Lock()
        self.reference_masked = b""
        self.reference_dispatches = 0

    def child(self, schema: str, label: str, kill_at: str | None = None) -> Ended:
        return start_child(
            schema,
            self.world,
            self.work / f"{label}.jsonl",
            self.work / f"{label}-count.jsonl",
            kill_at,
        )

    def schema(self, name: str) -> str:
        with self.lock:
            self.schemas.append(name)
            create_schema(self.admin, name)
        return name

    def reference(self, schema: str) -> tuple[list[str], dict[str, Any]]:
        """Run the reference, check it against the script, and keep its masked export."""
        ended = self.child(self.schema(schema), "reference")
        if ended.code != 0:
            print(ended.stderr, file=sys.stderr)
            raise SystemExit(f"the reference child exited {ended.code}")
        events = logged(self.url, schema)
        export = export_from_log(events)
        raw = export_bytes(export)
        turns = pickle.loads(self.world.path.read_bytes())["turns"]  # noqa: S301
        reads = tuple(
            (operation.id, operation.tool, _encode_outcome(operation.outcome)["kind"])
            for operation in export.trace.operations
            if not operation.id.startswith("pf-")
        )
        checks = {
            "the reference's usage is the script's": [
                None if call.usage is None else call.usage.counters
                for call in export.trace.model_calls
            ]
            == [
                (("input_tokens", turn.input_tokens), ("output_tokens", turn.output_tokens))
                for turn in turns
            ],
            "three model calls and nine operations": len(export.trace.model_calls) == CALLS
            and len(export.trace.operations) == 9,
            "the model's reads are the script's, each answered by its source": reads == MODEL_READS,
            "the claims are the script's final turn's": encode_claims(export.trace.claims)
            == turns[-1].text,
            "the driver took the healthy three steps": ended.report is not None
            and ended.report["taken"] == HEALTHY_STEPS,
            "the triple is three of each": witnessed(self.work / "reference.jsonl", events)
            == {"intents": 3, "requests": 3, "responses": 3, "outcomes": 3},
            "no append repeated a held event": ended.report is not None
            and ended.report["held_again"] == [],
        }
        if not all(checks.values()):
            raise SystemExit(f"the reference fails its own checks: {checks}")
        self.reference_masked = masked(export)
        self.reference_dispatches = dispatches(self.work / "reference.jsonl")
        return ended.crossings(), {
            "checks": checks,
            "steps": ended.report["taken"] if ended.report else None,
            "export_sha256": hashlib.sha256(raw).hexdigest(),
            "masked_sha256": hashlib.sha256(self.reference_masked).hexdigest(),
            "tool_dispatches": self.reference_dispatches,
        }

    def boundary(self, schema: str, label: str) -> dict[str, Any]:
        """Both stores and the injector's record after a kill, read once the sessions ended."""
        with psycopg.connect(self.url, autocommit=True) as watcher:
            quiet = sessions_ended(watcher, schema)
        events = logged(self.url, schema)
        counts = witnessed(self.work / f"{label}.jsonl", events)
        return {
            "sessions_ended": quiet,
            "events": len(events),
            "checkpoints": len(checkpointed(self.url, schema)),
            "violations": violations(checkpointed(self.url, schema), events),
            "counts": counts,
            "ordered": counts["intents"]
            >= counts["requests"]
            >= counts["responses"]
            >= counts["outcomes"],
        }

    def guarded(self, schema: str, label: str, target: str, twice: bool) -> dict[str, Any]:
        """``row``, with anything it raises turned into a failed row, so one row's fault
        neither passes nor takes the other rows' results with it."""
        try:
            return self.row(schema, label, target, twice)
        except Exception as raised:  # noqa: BLE001 - whatever a row raises fails that row
            failed: dict[str, Any] = {
                "target": target,
                "verdict": "fail",
                "failure": f"the row raised {type(raised).__name__}: {raised}"[:400],
            }
            return {**failed, "twice": "failed"} if twice else failed

    def row(self, schema: str, label: str, target: str, twice: bool) -> dict[str, Any]:
        """Kill at ``target``, recover (killing there once more when ``twice``), reconcile."""
        self.schema(schema)
        row: dict[str, Any] = {"target": target, "verdict": "fail"}
        children = [self.child(schema, label, kill_at=target)]
        if not children[0].died_at(target):
            row["failure"] = f"the child exited {children[0].code} and not at its target"
            row["stderr"] = children[0].stderr
            return row
        boundaries = [self.boundary(schema, label)]
        if twice:
            children.append(self.child(schema, label, kill_at=target))
            if children[1].died_at(target):
                row["twice"] = "recovered"
                boundaries.append(self.boundary(schema, label))
                children.append(self.child(schema, label))
            elif children[1].code == 0:
                row["twice"] = "not reached again"
            else:
                row["twice"] = "failed"
                row["failure"] = f"the second child exited {children[1].code}"
                row["stderr"] = children[1].stderr
                return row
        else:
            children.append(self.child(schema, label))
        final = children[-1]
        if final.code != 0 or final.report is None:
            row["failure"] = f"the recovering child exited {final.code}"
            row["stderr"] = final.stderr
            if twice:
                row["twice"] = "failed"
            return row

        events = logged(self.url, schema)
        store = checkpointed(self.url, schema)
        counts = witnessed(self.work / f"{label}.jsonl", events)
        expected = expected_at_completion(boundaries[-1]["counts"])
        export = export_from_log(events)
        duration = export.record.usage.duration_ms
        checks = {
            "the invariant held at each boundary": all(
                boundary["sessions_ended"] and not boundary["violations"] for boundary in boundaries
            ),
            "intents >= requests >= responses >= outcomes at each boundary": all(
                boundary["ordered"] for boundary in boundaries
            ),
            "the invariant holds at completion": not violations(store, events),
            "the final checkpoint's results are the logged ones": bool(store)
            and dict(store[0]["results"]) == digests_by_position(events),
            "no append by any child repeated a held event": not repeated(
                self.work / f"{label}.jsonl"
            ),
            "one approval event and one terminal event": sum(e.kind == APPROVAL for e in events)
            == 1
            and sum(e.kind == RUN_TERMINAL for e in events) == 1,
            "the export's bytes equal the reference's, duration masked": masked(export)
            == self.reference_masked,
            "the triple is the expected one": counts == expected,
            "the duration is positive and the per-segment sum the database computes": 0
            < duration
            == sum(segment_offsets(self.url, schema).values()),
            "each segment's last offset is inside its own process's clock": not (
                outside_their_process(events, self.work / f"{label}.jsonl")
            ),
        }
        row.update(
            {
                "verdict": "pass" if all(checks.values()) else "fail",
                "checks": checks,
                "boundaries": boundaries,
                "counts": counts,
                "expected": expected,
                "recovery_steps": final.report["taken"],
                "segments": final.report["segment"],
                "duration_ms": duration,
                "tool_dispatch_duplicates": dispatches(self.work / f"{label}.jsonl")
                - self.reference_dispatches,
            }
        )
        if twice and row["verdict"] == "fail":
            row["twice"] = "failed"
        return row


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--only", type=int, help="run the first N crossings only")
    parser.add_argument("--out", type=Path, help="also write the summary and every row here")
    parser.add_argument("--workers", type=int, default=6, help="rows run at once")
    arguments = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL names the local PostgreSQL; it is unset")
    execution = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    prefix = "spike_" + execution.lower().replace("-", "_")
    work = Path(tempfile.mkdtemp(prefix="spike-matrix-"))
    admin = psycopg.connect(url, autocommit=True)
    matrix = Matrix(url, admin, prepare_world(work), work)
    single: list[dict[str, Any]] = []
    twice: list[dict[str, Any]] = []
    try:
        crossings, reference = matrix.reference(f"{prefix}_ref")
        declared = crossings if arguments.only is None else crossings[: arguments.only]

        def both(numbered: tuple[int, str]) -> tuple[dict[str, Any], dict[str, Any]]:
            index, target = numbered
            once = matrix.guarded(f"{prefix}_s{index}", f"single-{index}", target, False)
            again = matrix.guarded(f"{prefix}_t{index}", f"twice-{index}", target, True)
            print(
                f"{index + 1}/{len(declared)} {target}: {once['verdict']}, "
                f"twice {again.get('twice', 'failed')}",
                file=sys.stderr,
            )
            return once, again

        # Rows share nothing but the server: each has its own schema, record and children.
        with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
            for once, again in pool.map(both, enumerate(declared)):
                single.append(once)
                twice.append(again)
    finally:
        for schema in matrix.schemas:
            drop_schema(admin, schema)
        admin.close()

    handoff = [row for row in single if parts(row["target"])[0].startswith("approval")]
    summary = {
        "probe": "crash matrix, approval, same seam twice",
        "verdict": "pass"
        if len(single) == len(crossings)
        and all(row["verdict"] == "pass" for row in single)
        and all(row.get("twice") in ("recovered", "not reached again") for row in twice)
        else "fail",
        "execution": execution,
        "harness": harness_revision(),
        "versions": {name: version(name) for name in PINNED},
        "world_sha256": matrix.world.sha256,
        "reference": reference,
        "crossings": {"declared": len(crossings), "run": len(single)},
        "kills_by_phase": _counted(parts(row["target"])[1] for row in single),
        "single": _counted(row["verdict"] for row in single),
        "approval_handoff": {row["target"]: row["verdict"] for row in handoff},
        "twice": _counted(row.get("twice", "failed") for row in twice),
        "recovery_steps": _counted(
            " > ".join(row.get("recovery_steps", ["none"])) for row in single
        ),
        "triples_at_completion": _counted(
            json.dumps(row.get("counts"), sort_keys=True) for row in single
        ),
        "tool_dispatch_duplicates": _counted(
            str(row.get("tool_dispatch_duplicates")) for row in single
        ),
        "rows_not_passing": [row for row in single if row["verdict"] != "pass"]
        + [row for row in twice if row.get("twice") not in ("recovered", "not reached again")],
    }
    rendered = json.dumps(summary, indent=2, ensure_ascii=False)
    print(rendered)
    if arguments.out is not None:
        arguments.out.mkdir(parents=True, exist_ok=True)
        (arguments.out / f"{execution}-matrix-summary.json").write_text(rendered, encoding="utf-8")
        (arguments.out / f"{execution}-matrix-rows.json").write_text(
            json.dumps({"single": single, "twice": twice}, indent=1, ensure_ascii=False),
            encoding="utf-8",
        )
    return 0 if summary["verdict"] == "pass" else 1


def _counted(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


if __name__ == "__main__":
    raise SystemExit(main())
