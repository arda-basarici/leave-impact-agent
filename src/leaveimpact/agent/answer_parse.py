"""The derived parse: from a response as it arrived to what its answer carried.

An export states what a recorded response means under the registered parser, and never
when or whether a worker finished parsing it: whether a tool call is unparsed, a fact batch
or undispatched for its stop reason, and what the gates admitted, is one pure function of
the response, the frozen inputs and the permitted log prefix, called by the worker and by
the log reader (the event log step's ruling on tool calls, part 2). A worker killed between
an outcome's append and a recorded parse would otherwise export a complete response with
no answer and no failure. Malformed model content gives typed refusals here and never an
unexpected exception; a malformed response *shape*, which no provider returns, raises, and
the attempt that meets it ends by defect at that dispatch's parse phase.

The response is the provider's Converse object as the client returned it: the output
message's content blocks, the stop reason, the usage. What the parse reads from it:

- a ``toolUse`` block is a tool call, by the provider's id and the tool's name; one whose
  input is not an object is *unparsed* and kept as text beside the argument parser's
  identity. A call of the fact tool is *handled* by the harness as the batch its input
  holds. A call of a read tool takes the disposition the log gives it: the operation it
  became, a skip, or, with no resolution, undispatched for its stop reason, unreached
  because an earlier call of the answer stopped the sequence or was never resolved (the
  durability barrier, ruling 7 parts 5 and 6), or unresolved;
- a ``text`` block whose first character is ``{`` is a fact payload in the answer's own
  content, read as a batch; any other non-blank text block makes the answer's text present.

A batch is the entries the fact parser reads, each a stated fact or a refused input; a
stated fact is then admitted or refused by the gates over the reads logged before the
answer, which the caller supplies as ``gate`` (ruling 7 part 9: the gates are given the
reads strictly below the outcome's position). A payload the parser cannot read as a batch
at all is kept malformed, as it arrived, beside the parser's identity.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from leaveimpact.agent.fact_entries import parse_payload, refused_by
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes, canonical_json
from leaveimpact.core.model_calls import (
    TOOL_USE_STOP,
    Answer,
    AsOperation,
    Disposition,
    FactBatch,
    HandledAsBatch,
    MalformedBatch,
    ParsedBatch,
    RefusedBy,
    ToolCall,
    Undispatched,
    UndispatchedReason,
    Unparsed,
    UnresolvedToolCall,
)
from leaveimpact.core.run_trace import thawed_json
from leaveimpact.core.stated import Admission, RefusedInput, StatedFact
from leaveimpact.core.usage import ReportedUsage

FACT_TOOL = "state_facts"
"""The tool a model states facts through; the harness handles its calls as fact batches and
asks no source."""

ARGUMENT_PARSER = "tool-arguments-1"
ARGUMENT_SCHEMA: JsonObject = {"type": "object"}
"""What a tool call's arguments are read as: a JSON object, nothing more here; the tool's
own validation is the executor's and a refusal there is an operation."""


def arguments_refused_by() -> RefusedBy:
    """The argument parser and the digest of what it reads, for a call it could not parse."""
    return RefusedBy(ARGUMENT_PARSER, hashlib.sha256(canonical_bytes(ARGUMENT_SCHEMA)).hexdigest())


# --- Reading the response --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolUse:
    """One ``toolUse`` block: the provider's id, the tool's name, the input as it arrived."""

    id: str
    name: str
    input: object


def content_blocks(response: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    """The output message's content blocks, in order, thawed from the log's frozen form;
    ``ValueError`` for a shape no provider returns, a defect of the harness or the recording."""
    output = cast("Mapping[str, object]", thawed_json(response)).get("output")
    if not isinstance(output, Mapping):
        raise ValueError("a response holds an output object")
    message = cast("Mapping[str, object]", output).get("message")
    if not isinstance(message, Mapping):
        raise ValueError("a response's output holds a message object")
    content = cast("Mapping[str, object]", message).get("content")
    if not isinstance(content, Sequence) or isinstance(content, str):
        raise ValueError("a response's message holds a content list")
    blocks: list[Mapping[str, object]] = []
    for block in cast("Sequence[object]", content):
        if not isinstance(block, Mapping):
            raise ValueError("a content block is an object")
        blocks.append(cast("Mapping[str, object]", block))
    return tuple(blocks)


def tool_uses(response: Mapping[str, object]) -> tuple[ToolUse, ...]:
    """The tool calls the response carries, in content order."""
    uses: list[ToolUse] = []
    for block in content_blocks(response):
        use = block.get("toolUse")
        if use is None:
            continue
        if not isinstance(use, Mapping):
            raise ValueError("a toolUse block is an object")
        held = cast("Mapping[str, object]", use)
        identifier, name = held.get("toolUseId"), held.get("name")
        if not isinstance(identifier, str) or not isinstance(name, str):
            raise ValueError("a toolUse block names its id and its tool")
        uses.append(ToolUse(identifier, name, held.get("input")))
    return tuple(uses)


def stop_reason_of(response: Mapping[str, object]) -> str:
    """The response's stop reason; ``ValueError`` when it holds none."""
    reason = response.get("stopReason")
    if not isinstance(reason, str) or not reason:
        raise ValueError("a response holds its stop reason")
    return reason


def reported_usage(response: Mapping[str, object]) -> ReportedUsage | None:
    """The usage object the response carried, or ``None`` when it carried none."""
    usage = response.get("usage")
    if usage is None:
        return None
    if not isinstance(usage, Mapping):
        raise ValueError("a response's usage is an object")
    return ReportedUsage(cast("Mapping[str, object]", usage))


# --- The answer ------------------------------------------------------------------------------

type Resolved = AsOperation | Undispatched
"""What the log gives a read tool call: the operation it became, or the skip it was given."""

type Gate = Callable[[StatedFact], Admission]
"""The gates over the permitted prefix, decided per stated fact."""


def is_payload(text: str) -> bool:
    """Whether a text block is a fact payload in the answer's own content."""
    return text.lstrip().startswith("{")


def parse_answer(
    response: Mapping[str, object],
    *,
    resolved: Mapping[str, Resolved],
    stopping: frozenset[str],
    gate: Gate,
) -> Answer:
    """What ``response`` carried, under the dispositions the log gives its read tool calls.

    ``resolved`` holds each read tool call's resolution by the call's id; ``stopping`` the
    ids whose operation holds a durable stopping result, after which no later call of the
    answer was reached. A read tool call in neither is undispatched for its stop reason
    under any stop but ``tool_use``; otherwise unreached when an earlier read call of the
    answer stopped the sequence or was itself never resolved; otherwise unresolved, which
    then blocks the calls after it the same way.
    """
    stop_reason = stop_reason_of(response)
    tool_use = stop_reason == TOOL_USE_STOP
    batches: list[FactBatch] = []
    calls: list[ToolCall] = []
    text_present = False
    blocked = False
    for block in content_blocks(response):
        text = block.get("text")
        if isinstance(text, str):
            if is_payload(text):
                batches.append(_batch_of_text(text, gate))
            elif text.strip():
                text_present = True
            continue
        if block.get("toolUse") is None:
            continue
        (use,) = tool_uses({"output": {"message": {"content": [block]}}})
        if use.name == FACT_TOOL:
            batches.append(_batch_of_input(use.input, gate))
            calls.append(ToolCall(use.id, use.name, HandledAsBatch(len(batches) - 1)))
            continue
        if not isinstance(use.input, Mapping):
            raw = canonical_json(use.input) if use.input is not None else ""
            calls.append(ToolCall(use.id, use.name, Unparsed(raw, arguments_refused_by())))
            continue
        disposition: Disposition
        if use.id in resolved:
            disposition = resolved[use.id]
            if use.id in stopping:
                blocked = True
        elif not tool_use:
            disposition = Undispatched(UndispatchedReason.STOP_REASON_NOT_TOOL_USE)
        elif blocked:
            disposition = Undispatched(UndispatchedReason.ATTEMPT_ENDED_FIRST)
        else:
            disposition = UnresolvedToolCall()
            blocked = True
        calls.append(ToolCall(use.id, use.name, disposition))
    return Answer(text_present, tuple(calls), tuple(batches))


def _batch_of_text(text: str, gate: Gate) -> FactBatch:
    try:
        payload: object = json.loads(text)
    except ValueError:
        return MalformedBatch(text, refused_by())
    entries = parse_payload(payload)
    if entries is None:
        return MalformedBatch(text, refused_by())
    return _gated(entries, gate)


def _batch_of_input(payload: object, gate: Gate) -> FactBatch:
    entries = parse_payload(payload)
    if entries is None:
        return MalformedBatch(canonical_json(payload), refused_by())
    return _gated(entries, gate)


def _gated(entries: Sequence[StatedFact | RefusedInput], gate: Gate) -> ParsedBatch:
    return ParsedBatch(
        tuple(entry if isinstance(entry, RefusedInput) else gate(entry) for entry in entries)
    )


__all__ = [
    "ARGUMENT_PARSER",
    "FACT_TOOL",
    "Gate",
    "Resolved",
    "ToolUse",
    "arguments_refused_by",
    "content_blocks",
    "is_payload",
    "parse_answer",
    "reported_usage",
    "stop_reason_of",
    "tool_uses",
]
