"""The failure-site catalogue: for each way a run attempt can stop that is not a model call
failing, what each store holds, what the injector knows, what recovery can establish, and
what shows the attempt existed.

Measured, no pass or fail (the acceptance spike's ruling 2): the table is what the contract
step and the event log step design from. Each row names exactly what was induced, since
several of the sites have more than one honest reading:

- *a crash before the first durable event:* the process killed before the segment's start is
  appended, never resumed;
- *a crash in the prefetch:* killed after the third read's append, then recovered;
- *a commit that succeeded with its acknowledgement lost:* killed after a model outcome's
  append returned and before the node could act on it, then recovered;
- *an attempt killed and never resumed:* killed after a model intent's append, left as is;
- *use of a closed client connection at an append* (a control, not an outage): the log's
  connection closed by the process itself before an append;
- *the log's session terminated by the server at an append:* ``pg_terminate_backend`` on the
  log's backend from another connection before an append, the nearest induced form of the
  database becoming unavailable to the log alone;
- *the latest checkpoint deleted* (a recoverable control): a run paused at the approval
  loses its newest checkpoint row, then recovers from the one before;
- *the latest checkpoint unloadable:* the same row's stored state overwritten so that
  loading it fails, recovery attempted, and then what the log alone allows: a run from the
  start on a new thread.

For the two faults that are exceptions and not kills, the run is in this process with the
seam hook replaced by one that induces the fault once at its target.

    uv run --group harness python probes/langgraph-spike/run_catalogue.py
"""

from __future__ import annotations

import json
import os
import pickle
import tempfile
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, LiteralString

import eventlog
import psycopg
from eventlog import RUN_STARTED, EventLog, connect, harness_revision
from graph import Harness, build, saver_on
from log_export import export_from_log
from parent import (
    World,
    checkpoint_rows,
    checkpointed,
    create_schema,
    drop_schema,
    logged,
    prepare_world,
    sessions_ended,
    start_child,
)
from psycopg.sql import SQL, Identifier
from recovery import drive
from run_uninterrupted import ATTEMPT, PINNED, RUN_ID, THREAD, provenance
from scripted import ScriptedChatModel, reported_usage
from seamed import counted, written
from seams import read_record

from leaveimpact.core.run_export_json import (
    _encode_context,  # pyright: ignore[reportPrivateUsage]
)


def stores(url: str, schema: str, thread: str = THREAD) -> dict[str, Any]:
    """What both stores hold now, the checkpoints those of ``thread``, and whether an export
    can be built from the log. The checkpoint table's rows are counted apart from loading
    them, so a store that holds a row it cannot load still shows the row."""
    events = logged(url, schema)
    kinds: dict[str, int] = {}
    for event in events:
        kinds[event.kind] = kinds.get(event.kind, 0) + 1
    rows = checkpoint_rows(url, schema)
    checkpoints: Any = {"tables": "absent" if rows is None else "present", "rows_all_threads": rows}
    try:
        store = checkpointed(url, schema, thread)
        checkpoints |= {
            "thread": thread,
            "steps": [checkpoint["step"] for checkpoint in store],
            "pending_writes": [
                written(task) for checkpoint in store for task in checkpoint["pending"]
            ],
        }
    except Exception as raised:  # noqa: BLE001 - how the store fails to load is the row
        checkpoints |= {"unreadable": f"{type(raised).__name__}: {raised}"[:200]}
    try:
        export_from_log(events)
        export = "builds"
    except ValueError as refused:
        export = f"refused: {refused}"
    return {
        "log": {
            "events": kinds,
            "last": f"{events[-1].kind}/{events[-1].position}" if events else None,
            "segments": kinds.get("segment_started", 0),
        },
        "checkpoints": checkpoints,
        "export_from_the_log": export,
        "shows_the_attempt_existed": {
            "a segment's start in the log": kinds.get("segment_started", 0) > 0,
            "the run's start in the log": kinds.get("run_started", 0) > 0,
            "a checkpoint row": bool(rows),
        },
    }


def injector(record: Path) -> dict[str, Any]:
    """What the injector's record holds: the last crossing and the witnessed counts."""
    lines = read_record(str(record))
    crossings = [line["crossing"] for line in lines if line["kind"] == "crossing"]
    return {
        "last_crossing": crossings[-1] if crossings else None,
        "model_requests": sum(line["kind"] == "model_request" for line in lines),
        "model_responses": sum(line["kind"] == "model_response" for line in lines),
        "tool_dispatches": sum(line["kind"] == "tool_dispatch" for line in lines),
    }


class Catalogue:
    def __init__(self, url: str, admin: psycopg.Connection[Any], world: World, work: Path) -> None:
        self.url = url
        self.admin = admin
        self.world = world
        self.work = work
        self.prefix = "spike_" + f"{datetime.now(UTC):%Y%m%dt%H%M%Sz}_{uuid.uuid4().hex[:6]}"
        self.rows: list[dict[str, Any]] = []
        self.schemas: list[str] = []

    def schema(self, label: str) -> str:
        name = f"{self.prefix}_{label}"
        self.schemas.append(name)
        create_schema(self.admin, name)
        return name

    def recovered(self, schema: str, label: str) -> dict[str, Any]:
        ended = start_child(
            schema, self.world, self.work / f"{label}.jsonl", self.work / f"{label}-c.jsonl"
        )
        return {
            "exit_code": ended.code,
            "steps": ended.report["taken"] if ended.report else None,
            "error": None if ended.code == 0 else ended.stderr.strip().splitlines()[-1][:300],
        }

    def killed(self, site: str, label: str, target: str, recover: bool) -> str:
        """A row for a kill at ``target``; the schema, for rows that go on from it."""
        schema = self.schema(label)
        record = self.work / f"{label}.jsonl"
        ended = start_child(schema, self.world, record, self.work / f"{label}-c.jsonl", target)
        sessions_ended(self.admin, schema)
        row = {
            "site": site,
            "induced": f"the process killed at {target}",
            "reached": ended.died_at(target),
            "at_the_fault": stores(self.url, schema),
            "the_injector_knows": injector(record),
        }
        if recover:
            row["recovery"] = self.recovered(schema, label)
            row["after_recovery"] = stores(self.url, schema)
        else:
            row["recovery"] = "not attempted: the attempt is left as the kill left it"
        self.rows.append(row)
        return schema

    def in_process(
        self, site: str, label: str, induced: str, fault: Callable[[EventLog], None]
    ) -> None:
        """A row for a fault induced once, before the append of the third prefetch read."""
        schema = self.schema(label)
        payload = pickle.loads(self.world.path.read_bytes())  # noqa: S301
        fired: list[str] = []

        def run(thread: str) -> list[str]:
            log = EventLog.open(connect(self.url, schema, schema), RUN_ID, ATTEMPT)
            if log.find(RUN_STARTED, "1") is None:
                log.append(
                    RUN_STARTED,
                    "1",
                    {
                        "run_id": RUN_ID,
                        "attempt": ATTEMPT,
                        "context": _encode_context(payload["context"]),
                        "provenance": provenance(log.events()[0].data["commit"]),
                    },
                )

            def hook(operation: str, phase: str) -> None:
                if (operation, phase) == ("tool_result/pf-3", "append:before") and not fired:
                    fired.append(operation)
                    fault(log)

            eventlog.cross = hook
            saver = saver_on(self.url, schema, application=schema)
            model = ScriptedChatModel(
                turns=payload["turns"], count_file=str(self.work / f"{label}-c.jsonl")
            )
            ports = counted(payload["systems"].ports)
            graph = build(Harness(log, ports, model, payload["context"], reported_usage), saver)
            try:
                return drive(graph, log, saver, thread)
            finally:
                saver.conn.close()
                if not log.connection.closed:
                    log.connection.close()

        original = eventlog.cross
        try:
            try:
                run(THREAD)
                raised = "nothing was raised"
            except Exception as error:  # noqa: BLE001 - what the fault raises is the row
                raised = f"{type(error).__name__}: {str(error).strip()[:160]}"
            sessions_ended(self.admin, schema)
            row = {
                "site": site,
                "induced": induced,
                "reached": bool(fired),
                "raised_out_of_the_graph": raised,
                "the_append_landed_all_the_same": any(
                    event.position == "pf-3" for event in logged(self.url, schema)
                ),
                "at_the_fault": stores(self.url, schema),
            }
            try:
                row["recovery"] = {"exit_code": 0, "steps": run(THREAD), "error": None}
            except Exception as error:  # noqa: BLE001
                row["recovery"] = {"error": f"{type(error).__name__}: {error}"[:300]}
            row["after_recovery"] = stores(self.url, schema)
        finally:
            eventlog.cross = original
        self.rows.append(row)

    def tampered(self, site: str, label: str, induced: str, statement: LiteralString) -> None:
        """A row for a run paused at the approval whose newest checkpoint row is tampered with."""
        schema = self.schema(label)
        record = self.work / f"{label}.jsonl"
        target = "approval/1:append:before#1"
        ended = start_child(schema, self.world, record, self.work / f"{label}-c.jsonl", target)
        sessions_ended(self.admin, schema)
        if not ended.died_at(target):
            self.rows.append(
                {
                    "site": site,
                    "induced": "nothing: the run was not killed at its target",
                    "reached": False,
                    "exit_code": ended.code,
                }
            )
            return
        before = stores(self.url, schema)
        table = Identifier(schema, "checkpoints")
        changed = self.admin.execute(SQL(statement).format(table, table)).rowcount
        row = {
            "site": site,
            "induced": f"{induced} ({changed} row), on a run killed at {target}",
            "reached": True,
            "before_the_fault": before["checkpoints"],
            "at_the_fault": stores(self.url, schema),
            "the_injector_knows": injector(record),
            "recovery": self.recovered(schema, label),
        }
        row["after_recovery"] = stores(self.url, schema)
        if row["recovery"]["exit_code"] != 0:
            row["from_the_log_alone"] = self.from_the_log(schema, label)
            row["after_the_run_from_the_log"] = stores(self.url, schema, f"{THREAD}/from-the-log")
        self.rows.append(row)

    def from_the_log(self, schema: str, label: str) -> dict[str, Any]:
        """Run the attempt from its start on a new thread, where no checkpoint exists."""
        payload = pickle.loads(self.world.path.read_bytes())  # noqa: S301
        count_file = self.work / f"{label}-c.jsonl"
        requests_before = len(read_record(str(count_file)))
        log = EventLog.open(connect(self.url, schema, schema), RUN_ID, ATTEMPT)
        events_before = len(log.events())
        saver = saver_on(self.url, schema, application=schema)
        model = ScriptedChatModel(turns=payload["turns"], count_file=str(count_file))
        graph = build(
            Harness(log, payload["systems"].ports, model, payload["context"], reported_usage),
            saver,
        )
        try:
            steps: Any = drive(graph, log, saver, f"{THREAD}/from-the-log")
        except Exception as error:  # noqa: BLE001
            steps = f"{type(error).__name__}: {error}"[:300]
        result = {
            "steps": steps,
            "events_added": [f"{e.kind}/{e.position}" for e in log.events()[events_before:]],
            "model_requests_added": len(read_record(str(count_file))) - requests_before,
        }
        saver.conn.close()
        log.connection.close()
        return result


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL names the local PostgreSQL; it is unset")
    work = Path(tempfile.mkdtemp(prefix="spike-catalogue-"))
    admin = psycopg.connect(url, autocommit=True)
    catalogue = Catalogue(url, admin, prepare_world(work), work)
    latest = "(SELECT max(checkpoint_id) FROM {})"

    def terminated(log: EventLog) -> None:
        # With a timeout the call returns once the backend has gone, not once it was signalled.
        admin.execute("SELECT pg_terminate_backend(%s, 5000)", (log.connection.info.backend_pid,))

    try:
        catalogue.killed(
            "a crash before the first durable event",
            "first",
            "segment_started/1:append:before#1",
            recover=False,
        )
        catalogue.killed(
            "a crash in the prefetch", "prefetch", "tool_result/pf-3:append:after#1", recover=True
        )
        catalogue.killed(
            "a commit that succeeded with its acknowledgement lost",
            "ack",
            "model_outcome/mc-1:append:after#1",
            recover=True,
        )
        catalogue.killed(
            "an attempt killed and never resumed",
            "abandoned",
            "model_intent/mc-2/1:append:after#1",
            recover=False,
        )
        catalogue.in_process(
            "use of a closed client connection at an append (control)",
            "closed",
            "the log's connection closed by the process before the append of tool_result/pf-3",
            lambda log: log.connection.close(),
        )
        catalogue.in_process(
            "the log's session terminated by the server at an append",
            "terminated",
            "pg_terminate_backend on the log's backend before the append of tool_result/pf-3",
            terminated,
        )
        catalogue.tampered(
            "the latest checkpoint deleted (recoverable control)",
            "deleted",
            "the newest checkpoint row deleted",
            "DELETE FROM {} WHERE checkpoint_id = " + latest,
        )
        catalogue.tampered(
            "the latest checkpoint unloadable",
            "unloadable",
            "the newest checkpoint row's stored state overwritten with an object of another shape",
            "UPDATE {} SET checkpoint = '{{\"overwritten\": true}}'::jsonb WHERE checkpoint_id = "
            + latest,
        )
    finally:
        for schema in catalogue.schemas:
            drop_schema(admin, schema)
        admin.close()
    summary = {
        "probe": "failure-site catalogue",
        "kind": "measured",
        "harness": harness_revision(),
        "versions": {name: version(name) for name in PINNED},
        "world_sha256": catalogue.world.sha256,
        "rows": catalogue.rows,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
