"""A completed run's format 1 export, built from the event log's events and nothing else.

The function is pure over the events of one run attempt: no connection, no checkpoint, no
graph state. Every field of the export has one supplier (the acceptance spike's rulings 1
and 5):

- run id, attempt, context and the provenance the harness set (the outage assignment, the
  preregistration, the model configuration, the pricing, the digests, the system, the
  retrieval, the prefetch rule, the caps): the ``run_started`` event;
- the harness revision: the first ``segment_started`` event;
- the observed condition: derived from the logged reads, as the rules-only baseline does;
- the status: the ``run_terminal`` event, without which there is no export;
- the model calls: one per ``model_outcome`` event, its role included; the usage aggregate
  folded over them. The request digest is the one the event holds, a digest of the logical
  request rebuilt from the log, which is not the bytes a provider client sends; the two are
  told apart at the contract step;
- the failure, the cost and each call's fault: absent, which is what a completed run with no
  call priced and no provider fault states;
- the operations: the ``tool_result`` events in append order;
- the claims: the last model outcome's, through the claims codec, when that response
  carried claims; none when it ended as a text, a refusal or an output the codec rejects,
  which the format reads as a completed run that states no claim;
- the duration: evidenced active execution, each segment contributing the offset of its last
  durable event.

The export is assembled as the JSON the package's codec reads and built by that codec's
decoder, so every validating constructor runs on it.

What the log holds and format 1 cannot state is read by ``unstated_by_format_1``,
measured cases for the contract step and never exported: the intents and their dispatch
attempts, the approval, a segment beyond the first with its own commit and tree state,
claims a response carried beside a tool call, which the format's one outcome per call
records as tool calls only, a tool call whose arguments the client could not parse,
which has no operation because an operation's arguments are a JSON object, and a tool call
a response held under a stop other than ``tool_use``, which was never dispatched and which
the format records as a text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from eventlog import (
    APPROVAL,
    MODEL_INTENT,
    MODEL_OUTCOME,
    RUN_STARTED,
    RUN_TERMINAL,
    SEGMENT_STARTED,
    TOOL_RESULT,
    Event,
)
from replay import carries_claims

from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.read_condition import observed_condition
from leaveimpact.core.run_export import EXPORT_FORMAT_VERSION, RunExport
from leaveimpact.core.run_export_json import (
    _decode_operation,  # pyright: ignore[reportPrivateUsage]
    decode_run_export,
)
from leaveimpact.core.run_trace import USAGE_COUNTER_NAMES, ModelCallOutcome


@dataclass(frozen=True, slots=True)
class Unstated:
    """What the log holds of the run and export format 1 has no place for."""

    intents: tuple[dict[str, Any], ...]
    approvals: tuple[dict[str, Any], ...]
    segments: tuple[dict[str, Any], ...]
    claims_beside_tool_calls: tuple[str, ...]
    unparsed_tool_calls: tuple[dict[str, Any], ...]
    undispatched_tool_calls: tuple[dict[str, Any], ...]


def export_from_log(events: tuple[Event, ...]) -> RunExport:
    """The export of the completed run attempt ``events`` record.

    Raises ``ValueError`` when the events are not one completed run: no start, no terminal
    state, no model call, or a last response that still asks for a read; and for anything
    the export's own constructors refuse.
    """
    started = _only(events, RUN_STARTED)
    terminal = _only(events, RUN_TERMINAL)
    segments = _of(events, SEGMENT_STARTED)
    if not segments:
        raise ValueError("the log holds no segment")
    answers = _of(events, MODEL_OUTCOME)
    reads = [event.data for event in _of(events, TOOL_RESULT)]
    if not answers:
        raise ValueError("a completed run made at least one model call")
    ending = ModelCallOutcome(answers[-1].data["outcome"])
    if ending is ModelCallOutcome.TOOL_CALLS:
        raise ValueError("a completed run's last response asks for no read")
    condition = observed_condition(_decode_operation(read) for read in reads).condition
    record = {
        **started.data["provenance"],
        "observed_condition": {"reachable": sorted(source.value for source in condition.reachable)},
        "harness": {key: segments[0].data[key] for key in ("commit", "tree")},
        "status": terminal.data["status"],
        "failure": None,
        "usage": {
            "counters": _aggregated(answers),
            "model_calls": len(answers),
            "duration_ms": active_duration_ms(events),
        },
        "cost": None,
    }
    trace = {
        "model_calls": [_model_call(answer.data) for answer in answers],
        "operations": reads,
        "claims": _json(answers[-1].data["text"]) if ending is ModelCallOutcome.CLAIMS else [],
    }
    return decode_run_export(
        {
            "format_version": EXPORT_FORMAT_VERSION,
            "run_id": started.data["run_id"],
            "attempt": started.data["attempt"],
            "context": started.data["context"],
            "record": record,
            "trace": trace,
        }
    )


def unstated_by_format_1(events: tuple[Event, ...]) -> Unstated:
    """The measured cases ``events`` hold that the export does not."""
    beside = tuple(
        answer.data["call"]
        for answer in _of(events, MODEL_OUTCOME)
        if ModelCallOutcome(answer.data["outcome"]) is ModelCallOutcome.TOOL_CALLS
        and carries_claims(answer.data["text"])
    )
    return Unstated(
        tuple(event.data for event in _of(events, MODEL_INTENT)),
        tuple(event.data for event in _of(events, APPROVAL)),
        tuple(event.data for event in _of(events, SEGMENT_STARTED)[1:]),
        beside,
        tuple(
            {"call": answer.data["call"], **call}
            for answer in _of(events, MODEL_OUTCOME)
            for call in answer.data["invalid_tool_calls"]
        ),
        tuple(
            {
                "call": answer.data["call"],
                "stop_reason": answer.data["stop_reason"],
                "tool_calls": len(answer.data["tool_calls"])
                + len(answer.data["invalid_tool_calls"]),
            }
            for answer in _of(events, MODEL_OUTCOME)
            if ModelCallOutcome(answer.data["outcome"]) is not ModelCallOutcome.TOOL_CALLS
            and (answer.data["tool_calls"] or answer.data["invalid_tool_calls"])
        ),
    )


def active_duration_ms(events: tuple[Event, ...]) -> int:
    """Evidenced active execution: the sum over segments of the last durable event's offset."""
    last: dict[int, int] = {}
    for event in events:
        last[event.segment] = max(last.get(event.segment, 0), event.offset_ms)
    return sum(last.values())


def _model_call(answer: dict[str, Any]) -> dict[str, Any]:
    usage = answer["usage"]
    return {
        "id": answer["call"],
        "role": answer["role"],
        "outcome": answer["outcome"],
        "stop_reason": answer["stop_reason"],
        "provider_latency_ms": answer["provider_latency_ms"],
        "request_digest": answer["request_digest"],
        "usage": None
        if usage is None
        else {
            "counters": [
                {"name": name, "value": usage[name]}
                for name in USAGE_COUNTER_NAMES
                if name in usage
            ]
        },
        "cost": None,
        "fault": None,
    }


def _aggregated(answers: tuple[Event, ...]) -> list[dict[str, Any]]:
    counters: list[dict[str, Any]] = []
    for name in USAGE_COUNTER_NAMES:
        reported = [
            answer.data["usage"][name]
            for answer in answers
            if answer.data["usage"] is not None and name in answer.data["usage"]
        ]
        if reported:
            counters.append({"name": name, "value": sum(reported), "reported_calls": len(reported)})
    return counters


def _of(events: tuple[Event, ...], kind: str) -> tuple[Event, ...]:
    return tuple(event for event in events if event.kind == kind)


def _only(events: tuple[Event, ...], kind: str) -> Event:
    held = _of(events, kind)
    if len(held) != 1:
        raise ValueError(f"a completed run holds one {kind} event, the log holds {len(held)}")
    return held[0]


def _json(text: str) -> Any:
    text = text.strip()
    value = json.loads(text)
    if canonical_json(value) != text:
        raise ValueError("the claims text is not the claims codec's canonical encoding")
    return value
