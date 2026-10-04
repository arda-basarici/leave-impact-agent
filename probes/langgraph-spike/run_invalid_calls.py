"""Invalid tool calls through the scripted graph: each ends in an observable disposition, and
no port is called for any of them.

The criterion is the ``invalid tool calls`` row of the committed acceptance section in
``probes/README.md``: an unknown tool name, unparseable arguments and schema-violating
arguments. The shapes are the ones the parser fixtures showed the pinned client hands on
(``run_parser_fixtures.py``): an unknown name and schema-violating arguments arrive as
ordinary tool calls, and arguments that are not a JSON object arrive as an invalid tool call
beside no valid one, under a ``tool_use`` stop.

One run per case, in a schema of its own, through the recovery driver, the counted ports
and the event log: turn 1 makes the bad call, turn 2 carries the final claims. A case passes
when the run completes, its export is built from the log and round-trips, and:

- *no port was called for the bad call:* the injector's record holds exactly as many tool
  dispatches as the prefetch made reads, and none after the first model request;
- *the disposition is observable.* For an unknown name and for schema-violating arguments:
  the export holds an operation answering the call with a refused-call outcome and a
  reason. For unparseable arguments, which format 1 has no operation for: the logged
  response holds the call as the client returned it, the export records the model call as
  tool calls with no operation, and the next request, rebuilt from the log, answers the call
  by its id with an error reply.

For every case the next request is also converted by the pinned client's own message
conversion, and each tool result in it must answer a tool use of the same id: a reply the
provider has no call for would be a request it rejects.

How each disposition is represented is the measured part and is printed per case.

    uv run --group harness python probes/langgraph-spike/run_invalid_calls.py
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

import psycopg
from eventlog import (
    MODEL_OUTCOME,
    RUN_STARTED,
    EventLog,
    connect,
    harness_revision,
    read_events,
    sorted_canonical,
)
from graph import Harness, build, saver_on
from langchain_aws.chat_models.bedrock_converse import (
    _messages_to_bedrock,  # pyright: ignore[reportPrivateUsage]
)
from langchain_core.messages import ToolMessage
from log_export import export_from_log, unstated_by_format_1
from parent import create_schema, drop_schema
from recovery import drive
from replay import UNPARSED_REPLY, conversation
from run_uninterrupted import ATTEMPT, PINNED, RUN_ID, THREAD, provenance, scenario_and_baseline
from scripted import ScriptedChatModel, ToolCall, Turn, reported_usage, requests_counted
from seamed import counted
from seams import RECORD_VARIABLE, read_record

from leaveimpact.core.claims_json import encode_claims
from leaveimpact.core.run_export_json import (
    _encode_context,  # pyright: ignore[reportPrivateUsage]
    _encode_operation,  # pyright: ignore[reportPrivateUsage]
    decode_export_bytes,
    export_bytes,
)
from tests.unit.reads_fixture import systems_holding

UNPARSEABLE = "unparseable arguments"


def cases(leaver: str) -> dict[str, Turn]:
    """Turn 1 of each case: the one bad call."""
    return {
        "unknown tool name": Turn("", (ToolCall("employe", {"id": leaver}),), 1200, 40, 11),
        "schema-violating arguments": Turn(
            "", (ToolCall("employee", {"id": "LIA-42"}),), 1200, 40, 11
        ),
        UNPARSEABLE: Turn("", (), 1200, 40, 11, unparsed=(("employee", f"id is {leaver}"),)),
    }


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL names the local PostgreSQL; it is unset")
    execution = f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    prefix = "spike_" + execution.lower().replace("-", "_")
    work = Path(tempfile.mkdtemp(prefix="spike-invalid-"))
    context, baseline, leaver, world = scenario_and_baseline()
    final = Turn(encode_claims(baseline.claims), (), 2600, 300, 13)
    admin = psycopg.connect(url, autocommit=True)
    rows: list[dict[str, Any]] = []
    try:
        for index, (label, bad) in enumerate(cases(leaver).items()):
            schema = f"{prefix}_i{index}"
            record = work / f"case-{index}.jsonl"
            count_file = work / f"case-{index}-count.jsonl"
            os.environ[RECORD_VARIABLE] = str(record)
            create_schema(admin, schema)
            try:
                log = EventLog.open(connect(url, schema), RUN_ID, ATTEMPT)
                log.append(
                    RUN_STARTED,
                    "1",
                    {
                        "run_id": RUN_ID,
                        "attempt": ATTEMPT,
                        "context": _encode_context(context),
                        "provenance": provenance(log.events()[0].data["commit"]),
                    },
                )
                saver = saver_on(url, schema)
                model = ScriptedChatModel(turns=(bad, final), count_file=str(count_file))
                ports = counted(systems_holding(world).ports)
                graph = build(Harness(log, ports, model, context, reported_usage), saver)
                taken = drive(graph, log, saver, THREAD)
                events = read_events(log.connection, RUN_ID, ATTEMPT)
                saver.conn.close()
                log.connection.close()
            finally:
                drop_schema(admin, schema)
            rows.append(judged(label, events, taken, record, count_file, context))
    finally:
        os.environ.pop(RECORD_VARIABLE, None)
        admin.close()
    summary = {
        "probe": "invalid tool calls",
        "verdict": "pass" if all(row["verdict"] == "pass" for row in rows) else "fail",
        "execution": execution,
        "harness": harness_revision(),
        "versions": {name: version(name) for name in PINNED},
        "scenario": context.scenario_id,
        "rows": rows,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["verdict"] == "pass" else 1


def judged(
    label: str, events: Any, taken: list[str], record: Path, count_file: Path, context: Any
) -> dict[str, Any]:
    """One case's checks and how its disposition is represented."""
    export = export_from_log(events)
    raw = export_bytes(export)
    lines = read_record(str(record))
    kinds = [line["kind"] for line in lines if line["kind"] != "crossing"]
    first_request = kinds.index("model_request")
    prefetched = [op for op in export.trace.operations if op.id.startswith("pf-")]
    answering = [
        _encode_operation(op) for op in export.trace.operations if not op.id.startswith("pf-")
    ]
    unstated = unstated_by_format_1(events)
    response = next(e for e in events if e.kind == MODEL_OUTCOME and e.position == "mc-1").data
    second_request = conversation(context, events, 1)
    wire, _ = _messages_to_bedrock(second_request)
    uses = [
        block["toolUse"]["toolUseId"]
        for message in wire
        for block in message["content"]
        if "toolUse" in block
    ]
    results = [
        block["toolResult"]["toolUseId"]
        for message in wire
        for block in message["content"]
        if "toolResult" in block
    ]
    replies = [
        {"tool_call_id": m.tool_call_id, "status": m.status, "content": m.content}
        for m in second_request
        if isinstance(m, ToolMessage)
    ]
    checks = {
        "the run completed": taken[-1] == "found complete",
        "the export round-trips": decode_export_bytes(raw) == export,
        "on the wire every tool result of the next request answers a tool use": bool(results)
        and uses == results,
        "two model calls, each requested once": requests_counted(str(count_file)) == [1, 2],
        "the dispatches are the prefetch's reads and no other": kinds.count("tool_dispatch")
        == len(prefetched),
        "no dispatch after the first model request": "tool_dispatch" not in kinds[first_request:],
    }
    if label == UNPARSEABLE:
        held = response["invalid_tool_calls"]
        checks |= {
            "the logged response holds the call as the client returned it": len(held) == 1
            and held[0]["name"] == "employee"
            and isinstance(held[0]["args"], str),
            "the export records tool calls and no operation for it": export.trace.model_calls[
                0
            ].outcome.value
            == "tool_calls"
            and answering == [],
            "the next request answers the call by its id with an error reply": replies
            == [
                {
                    "tool_call_id": held[0]["id"] if held else None,
                    "status": "error",
                    "content": sorted_canonical(UNPARSED_REPLY),
                }
            ],
            "the call is listed as unstated by format 1": [
                call["id"] for call in unstated.unparsed_tool_calls
            ]
            == [call["id"] for call in held],
        }
    else:
        checks |= {
            "one operation answers the call, refused with a reason": len(answering) == 1
            and answering[0]["outcome"]["kind"] == "refused_call"  # type: ignore[index]
            and bool(answering[0]["outcome"]["reason"]),  # type: ignore[index]
            "the next request carries that refusal to the model as an error": len(replies) == 1
            and replies[0]["status"] == "error"
            and "refused_call" in str(replies[0]["content"]),
        }
    return {
        "case": label,
        "verdict": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "representation": {
            "model_call_outcome": export.trace.model_calls[0].outcome.value,
            "operations_answering_the_call": answering,
            "logged_invalid_tool_calls": response["invalid_tool_calls"],
            "reply_in_the_next_request": replies,
            "unstated_by_format_1": asdict(unstated)["unparsed_tool_calls"],
        },
        "tool_dispatches": kinds.count("tool_dispatch"),
        "prefetch_reads": len(prefetched),
    }


if __name__ == "__main__":
    raise SystemExit(main())
