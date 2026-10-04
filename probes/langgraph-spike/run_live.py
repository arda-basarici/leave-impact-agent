"""The bounded live run: one scenario through the whole path on a real model, the graph, a
tool-result round trip, the approval and both stores, with every send captured.

The criterion is the ``live path`` row of the committed acceptance section in
``probes/README.md``. A probe: nothing about claim quality is read from it. The model is the
pinned chat client on the ``eu.`` Haiku 4.5 profile, the generated tool surface bound
unchanged through ``toolConfig`` with the choice ``auto``, temperature 0, not streamed. The
graph is the scripted half's, on the plain saver and real PostgreSQL in a schema of this
execution's own; no seam and no kill, since crash injection stays scripted.

The system prompt scripts the ending. It asks for at least one lookup and then the literal
``[]``, an empty claims array the claims codec accepts: the scenario's real claims are far
over the output limit, and a run that reads nothing about claim quality needs only an ending
the format can state. What the model does instead is reported, not judged: any answered
response that asks for no read ends the loop, and the export holds claims only when the
codec accepted them.

Bounds, against a loop bug: at most ``CALL_CAP`` model calls, each inside one recorder
invocation, so the recorder's own guards apply (the sends per execution, the cumulative
sends, the body size, an output limit on every request); client retries are off, so a call
is one send. Reaching the cap raises and fails the row.

A call's usage is read from the capture record's raw response, never from the message's
mapped usage, where the client has summed the cache counters into the input count and
written absent counters as zero. The Bedrock names are mapped to the export's and a counter
the provider did not report stays absent.

The row passes when nothing raised, the export is built from the log and round-trips, and:

- a read reached its source and answered a model call (a refused call is no read), and the
  captured body of the next request holds the exact rendering of its outcome under the
  call's id, as a success;
- one approval was delivered and no append repeated a held event;
- every model call is one captured send with a resolved response;
- each call's usage in the export is the usage in the captured response's bytes, read from
  the response file and not from the record line the harness took it from;
- no tool call the model made was left undispatched, which is what a call cut at the output
  limit would be: such a run reaches its terminal state, and the row still fails, since the
  path it took is not the one the row is about.

Reported and not checked, because the script's own construction makes them true whenever the
checks are evaluated: the model calls against the cap, the checkpoint rows, the driver's
steps.

Captures hold model requests and responses and go to the private directory
``LEAVE_IMPACT_SPIKE_CAPTURES`` names, with the log's events, the export and, on a failure,
the exception's text. The printed summary is meant to be citable and holds no model or
provider text: digests, counts, sizes, stop reasons, and a tool's name only when it is one
the surface declares. An exception appears as its type and the digest of its message, since
a provider's error text can name the account and the role. Credentials are ambient
(``AWS_PROFILE``).

    uv run --group harness python probes/langgraph-spike/run_live.py

``--offline`` replaces the network with a canned answer at botocore's ``before-send`` hook:
a short text beside a tool call while the request holds no tool result, then ``[]`` with a
trailing newline. It exercises this script's own logic without a send, proves nothing about
a provider, and its summary says so.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from importlib.metadata import version
from typing import Any

import psycopg
from bench import _Raw  # pyright: ignore[reportPrivateUsage]
from botocore.awsrequest import AWSResponse
from botocore.compat import HTTPHeaders
from capture import Recorder, capture_root, clients, require_tracing_off
from eventlog import (
    MODEL_INTENT,
    MODEL_OUTCOME,
    RUN_STARTED,
    Event,
    EventLog,
    connect,
    read_events,
    sorted_canonical,
)
from graph import DURABILITY, Harness, build, retry_policies, saver_on
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, BaseMessage
from log_export import export_from_log, unstated_by_format_1
from parent import checkpoint_rows, create_schema, drop_schema
from recovery import drive
from replay import ROLE
from run_uninterrupted import ATTEMPT, PINNED, RUN_ID, THREAD, provenance, scenario_and_baseline
from surface import LADDER, tool_config

from leaveimpact.core.provenance import ModelConfiguration, Setting, encode_model_configuration
from leaveimpact.core.run_export_json import (
    _encode_context,  # pyright: ignore[reportPrivateUsage]
    _encode_outcome,  # pyright: ignore[reportPrivateUsage]
    decode_export_bytes,
    export_bytes,
)
from leaveimpact.core.tools import TOOL_SPECIFICATIONS
from tests.unit.reads_fixture import systems_holding

PROFILE = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "eu-central-1"
CALL_CAP = 6
MAX_TOKENS = 512
LIVE_SYSTEM = (
    "You investigate the operational impact of an employee's leave. The first message holds "
    "the leave and what was already read. Look up at least one further record with a tool. "
    "When you have finished, answer with exactly [] and nothing else."
)
COUNTERS = {
    "inputTokens": "input_tokens",
    "outputTokens": "output_tokens",
    "cacheReadInputTokens": "cache_read_input_tokens",
    "cacheWriteInputTokens": "cache_write_input_tokens",
}
"""The provider's counter names and the export's, in the export's declared order."""
DECLARED = frozenset(specification.name for specification in TOOL_SPECIFICATIONS)
READS = ("record", "absent", "records")
"""The outcome kinds of a read that reached its source and was answered."""


def mapped(raw: object) -> dict[str, int] | None:
    """The counters ``raw`` reports under the export's names; an absent one stays absent."""
    if not isinstance(raw, dict):
        return None
    return {ours: raw[theirs] for theirs, ours in COUNTERS.items() if theirs in raw}


def shown(tool: object) -> str:
    """``tool`` when the surface declares it; a name the model invented is response content."""
    return tool if isinstance(tool, str) and tool in DECLARED else "<not a declared tool>"


class RecordedModel:
    """The bound chat client, each call inside one recorder invocation and under the cap."""

    def __init__(self, bound: Any, recorder: Recorder) -> None:
        self.bound = bound
        self.recorder = recorder
        self.calls: list[tuple[str, ...]] = []
        self.client_mapped: list[dict[str, Any] | None] = []

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        if len(self.calls) >= CALL_CAP:
            raise RuntimeError(f"the run reached its cap of {CALL_CAP} model calls")
        with self.recorder.invocation("live-path", f"mc-{len(self.calls) + 1}") as sends:
            message = self.bound.invoke(messages)
        self.calls.append(tuple(sends))
        self.client_mapped.append(
            None if message.usage_metadata is None else dict(message.usage_metadata)
        )
        return message

    def usage_of(self, message: AIMessage) -> dict[str, int] | None:
        """The usage the capture record holds for the call just made."""
        outcome = self.recorder.outcome_of(self.calls[-1][-1])
        return None if outcome is None else mapped(outcome["usage"])


def tool_results(body: dict[str, Any]) -> dict[str, Any]:
    """The tool results a captured request body carries, by the id of the call they answer."""
    return {
        block["toolResult"]["toolUseId"]: block["toolResult"]
        for message in body["messages"]
        for block in message["content"]
        if "toolResult" in block
    }


def answer_offline(runtime: Any) -> None:
    """Answer every Converse request in process: one read first, then the scripted ending."""

    def respond(request: Any, **_: Any) -> AWSResponse:
        body = json.loads(request.body)
        if tool_results(body):
            content: list[dict[str, Any]] = [{"text": "[]\n"}]
            stop = "end_turn"
        else:
            use = {"toolUseId": "offline-1", "name": "employees", "input": {}}
            content, stop = [{"text": "Looking up."}, {"toolUse": use}], "tool_use"
        answer = {
            "output": {"message": {"role": "assistant", "content": content}},
            "stopReason": stop,
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
            "metrics": {"latencyMs": 1},
        }
        headers = HTTPHeaders()
        headers["content-type"] = "application/json"
        headers["x-amzn-requestid"] = "offline"
        return AWSResponse(request.url, 200, headers, _Raw(json.dumps(answer).encode("utf-8")))

    runtime.meta.events.register("before-send.bedrock-runtime.Converse", respond)


def refused(raised: BaseException, recorder: Recorder) -> dict[str, Any]:
    """An exception as the summary may show it; its text goes to the private directory."""
    text = f"{type(raised).__name__}: {raised}"
    with (recorder.directory / "live-path-failure.txt").open("a", encoding="utf-8") as kept:
        kept.write(text + "\n")
    return {
        "type": type(raised).__name__,
        "message_sha256": hashlib.sha256(str(raised).encode("utf-8")).hexdigest(),
        "message_characters": len(str(raised)),
    }


def invocations(recorder: Recorder, model: RecordedModel, answers: dict[str, Any]) -> list[Any]:
    """Every invocation the recorder finished, answered or not: its sends, how each was
    resolved, the raw usage, and what the log holds of the call when it holds it."""
    listed: list[Any] = []
    for index, invocation in enumerate(recorder.finished):
        outcomes = [recorder.outcome_of(send) for send in invocation.sends]
        last = outcomes[-1] if outcomes else None
        sent = recorder.lines_of(invocation.sends[0])[0] if invocation.sends else {}
        answer = answers.get(invocation.label)
        client = model.client_mapped[index] if index < len(model.client_mapped) else None
        raw = None if last is None else mapped(last["usage"])
        entry: dict[str, Any] = {
            "call": invocation.label,
            "sends": list(invocation.sends),
            "resolved_as": ["unresolved" if o is None else o["outcome"] for o in outcomes],
            "http_status": [None if o is None else o["http_status"] for o in outcomes],
            "raw_usage": None if last is None else last["usage"],
            "counter_states": None if last is None else last["counters"],
            "client_mapped_usage_differs_from_raw": None
            if client is None or raw is None
            else {name: client.get(name) for name in ("input_tokens", "output_tokens")}
            != {name: raw.get(name) for name in ("input_tokens", "output_tokens")},
            "sent_body_sha256": sent.get("body_sha256"),
            "sent_body_bytes": sent.get("body_bytes"),
        }
        if answer is not None:
            entry |= {
                "outcome": answer["outcome"],
                "stop_reason": answer["stop_reason"],
                "provider_latency_ms": answer["provider_latency_ms"],
                "tool_calls": [shown(call["tool"]) for call in answer["tool_calls"]],
                "unparsed_tool_calls": len(answer["invalid_tool_calls"]),
                "text_characters": len(answer["text"]),
                "logical_request_digest": answer["request_digest"],
            }
        listed.append(entry)
    return listed


def judged(
    events: tuple[Event, ...], recorder: Recorder, model: RecordedModel, held_again: list[str]
) -> dict[str, Any]:
    """The checks and the measured facts of a run that raised nothing."""
    answers = [event.data for event in events if event.kind == MODEL_OUTCOME]
    intents = [event.data for event in events if event.kind == MODEL_INTENT]
    resolved = [recorder.outcome_of(sends[-1]) if sends else None for sends in model.calls]
    export = export_from_log(events)
    raw = export_bytes(export)
    (recorder.directory / "live-path-export.json").write_bytes(raw)
    answered = [op for op in export.trace.operations if not op.id.startswith("pf-")]
    reads = [op for op in answered if _encode_outcome(op.outcome)["kind"] in READS]
    round_trip = False
    if reads:
        first = reads[0]
        turn = int(first.id.split("-")[1])
        asked = answers[turn - 1]["tool_calls"][int(first.id.rsplit("t", 1)[1]) - 1]
        if turn < len(model.calls):
            result = tool_results(recorder.request_of(model.calls[turn][0])).get(asked["id"], {})
            rendered = sorted_canonical(_encode_outcome(first.outcome))
            round_trip = (
                result.get("content") == [{"text": rendered}] and result.get("status") == "success"
            )
    unstated = unstated_by_format_1(events)
    from_bytes = [
        mapped((recorder.response_of(sends[-1]) or {}).get("usage")) if sends else None
        for sends in model.calls
    ]
    checks = {
        "the export is built from the log and round-trips": decode_export_bytes(raw) == export,
        "a read reached its source and answered a model call": bool(reads),
        "the next request's captured body holds that read's exact rendering, as a success": (
            round_trip
        ),
        "one approval, and no append repeated a held event": len(unstated.approvals) == 1
        and held_again == [],
        "every model call is one captured send with a resolved response": len(model.calls)
        == len(answers)
        == len(intents)
        and all(len(sends) == 1 for sends in model.calls)
        and all(outcome is not None and outcome["outcome"] == "response" for outcome in resolved),
        "each call's usage in the export is the captured response's": [
            None if call.usage is None else dict(call.usage.counters)
            for call in export.trace.model_calls
        ]
        == from_bytes,
        "no tool call the model made was left undispatched": not unstated.undispatched_tool_calls,
    }
    return {
        "checks": checks,
        "export": {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
        "operations": {
            "prefetch": len(export.trace.operations) - len(answered),
            "model": [
                [op.id, shown(op.tool), _encode_outcome(op.outcome)["kind"]] for op in answered
            ],
        },
        "claims_exported": len(export.trace.claims),
        "final_outcome": answers[-1]["outcome"],
        "final_stop_reason": answers[-1]["stop_reason"],
        "usage_aggregate": [list(counter) for counter in export.record.usage.counters],
        "duration_ms": export.record.usage.duration_ms,
        "undispatched_tool_calls": list(unstated.undispatched_tool_calls),
        "unparsed_wire_shape": "exercised"
        if unstated.unparsed_tool_calls
        else "not exercised: the model made no unparseable call",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="answer in process, send nothing")
    offline = parser.parse_args().offline
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL names the local PostgreSQL; it is unset")
    require_tracing_off()
    if offline:
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "offline")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "offline")
    recorder = Recorder(capture_root(), REGION, offline=offline)
    print(f"cumulative sends before this execution: {recorder.cumulative_sends()}", file=sys.stderr)
    runtime, control = clients(recorder)
    if offline:
        answer_offline(runtime)
    chat = ChatBedrockConverse(
        model=PROFILE,
        client=runtime,
        bedrock_client=control,
        region_name=REGION,
        temperature=0,
        max_tokens=MAX_TOKENS,
    )
    model = RecordedModel(chat.bind(toolConfig=tool_config(LADDER[0], "auto")), recorder)
    context, _, _, world = scenario_and_baseline()
    schema = "spike_" + recorder.execution.lower().replace("-", "_")
    admin = psycopg.connect(url, autocommit=True)
    create_schema(admin, schema)
    failure: dict[str, Any] | None = None
    taken: list[str] = []
    try:
        log = EventLog.open(connect(url, schema), RUN_ID, ATTEMPT)
        revision = log.events()[0].data
        held = provenance(revision["commit"])
        settings = (Setting("max_tokens", MAX_TOKENS), Setting("temperature", 0))
        held["model_configurations"] = [
            {
                "role": ROLE,
                "configuration": encode_model_configuration(ModelConfiguration(PROFILE, settings)),
            }
        ]
        held["prompt_digests"] = [
            {
                "role": ROLE,
                "name": "system",
                "digest": hashlib.sha256(LIVE_SYSTEM.encode()).hexdigest(),
            }
        ]
        log.append(
            RUN_STARTED,
            "1",
            {
                "run_id": RUN_ID,
                "attempt": ATTEMPT,
                "context": _encode_context(context),
                "provenance": held,
            },
        )
        saver = saver_on(url, schema)
        ports = systems_holding(world).ports
        harness = Harness(log, ports, model, context, model.usage_of, LIVE_SYSTEM)  # type: ignore[arg-type]
        graph = build(harness, saver)
        policies = retry_policies(graph)
        try:
            taken = drive(graph, log, saver, THREAD)
        except Exception as raised:  # noqa: BLE001 - how the live run failed is the row
            failure = refused(raised, recorder)
        held_again = list(log.held_again)
        events = read_events(log.connection, RUN_ID, ATTEMPT)
        checkpoints = checkpoint_rows(url, schema)
        saver.conn.close()
        log.connection.close()
        # The log is kept with the captures before its schema goes, so a failure after this
        # point still leaves what the run did.
        with (recorder.directory / "live-path-events.jsonl").open("w", encoding="utf-8") as kept:
            for event in events:
                line = {"kind": event.kind, "position": event.position, "segment": event.segment}
                kept.write(json.dumps({**line, "content": event.data}, ensure_ascii=False) + "\n")
    finally:
        drop_schema(admin, schema)
        admin.close()

    answers = {event.data["call"]: event.data for event in events if event.kind == MODEL_OUTCOME}
    summary: dict[str, Any] = {
        "probe": "live path",
        "offline": offline,
        "execution": recorder.execution,
        "harness": revision,
        "versions": {name: version(name) for name in PINNED},
        "configuration": {
            "profile": PROFILE,
            "region": REGION,
            "temperature": 0,
            "max_tokens": MAX_TOKENS,
            "call_cap": CALL_CAP,
            "tool_choice": "auto",
            "surface": LADDER[0].name,
            "streamed": False,
            "durability": DURABILITY,
            "retry_policies_read_from_the_compiled_graph": policies,
        },
        "scenario": context.scenario_id,
        "sends": {"this_execution": recorder.sends_made, "cumulative": recorder.cumulative_sends()},
        "model_calls": {"answered": len(model.calls), "cap": CALL_CAP},
        "checkpoint_rows": checkpoints,
        "driver": taken,
        "events": len(events),
        "calls": invocations(recorder, model, answers),
    }
    if failure is None:
        try:
            summary |= judged(events, recorder, model, held_again)
        except Exception as raised:  # noqa: BLE001 - an export the log cannot give is the row
            failure = refused(raised, recorder)
    summary["failure"] = failure
    passed = failure is None and all(summary["checks"].values())
    summary["verdict"] = ("offline, proves nothing: " if offline else "") + (
        "pass" if passed else "fail"
    )
    rendered_summary = json.dumps(summary, indent=2, ensure_ascii=False)
    (recorder.directory / "live-path-summary.json").write_text(rendered_summary, encoding="utf-8")
    print(rendered_summary)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
