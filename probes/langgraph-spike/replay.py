"""Replay over the event log: the executor that looks a read up before making it, and the
conversation a model call is asked with, rebuilt from the log.

A node may run twice: the framework reruns an interrupted or unfinished node from its start
on resume, and by then the log may already hold what the first run did (the acceptance
spike's ruling 3). So nothing here trusts graph state for a result. A read is looked up by
its deterministic position first and made only when the log holds none; a model request is
rebuilt from the logged reads and the logged responses, so two processes that reach the same
turn ask the same request.

``LoggedExecutor`` is the package's executor with that rule added around ``call``. A hit
checks that the logged read is the one being asked for (the same origin, tool and
arguments) and raises when replay has diverged from the log, and it restores the stop a
logged unreachable outcome implies. The stopped sources it starts from are the ones the
phases before it logged, named by their position prefixes, never its own positions' and
never a later phase's: the log can be ahead of the node, and a stop seeded from a read the
node has not reached yet would make the prefetch skip a call it made the first time. The
executor is built per node call and holds nothing between nodes.

``outcome_content`` is the one place a provider's answer becomes a logged response. The
pinned Bedrock client gives a message whose content is a list of blocks whenever a tool call
is present and whose latency is a one-item list, so the text is read from the text blocks
and the latency unwrapped. The usage is handed in by the caller from the provider's own
report, never read off the message's mapped usage, where the client has already summed the
cache counters into the input count and written absent counters as zero (the provider
half's finding). Tool calls the client could not parse are logged as it returned them.

The rendering of a tool result and of the opening message is the spike's own, the canonical
JSON of the outcome the export codec writes; the tool registry step owns the real one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from eventlog import MODEL_OUTCOME, TOOL_RESULT, Event, EventLog, digest_of, sorted_canonical
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from leaveimpact.agent.execution import Executor
from leaveimpact.core.claims_json import decode_claims
from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.run_export_json import (
    _decode_operation,  # pyright: ignore[reportPrivateUsage]
    _encode_operation,  # pyright: ignore[reportPrivateUsage]
    thawed_json,
)
from leaveimpact.core.run_trace import (
    ModelCallOutcome,
    OperationId,
    Origin,
    Outcome,
    UnreachableOutcome,
    frozen_json,
)
from leaveimpact.core.timeshape import encode_instant
from leaveimpact.core.tools import TOOL_SPECIFICATIONS, tool_surface_digest
from leaveimpact.core.worldtime import RunContext

ROLE = "investigator"
SYSTEM = (
    "You investigate the operational impact of an employee's leave with the tools you are "
    "given, and end with your claims."
)
PREFETCH_PREFIX = "pf-"
UNPARSED_REPLY = {
    "kind": "refused_call",
    "reason": "the arguments of this tool call are not a JSON object",
}
"""What a tool call the client could not parse is answered with. No operation is made for
it, since an operation's arguments are a JSON object and these are not one; the reply is
rebuilt from the logged response alone, so a restarted process asks the same next request."""
UNPARSED_ARGUMENTS = "unparsed_arguments"
"""The one key of the object an unparsed call's raw argument text is replayed under. The
provider pairs a tool result with a tool use by id and takes a tool use's input as an
object, and the pinned client sends only a message's parsed tool calls, so the assistant
turn is rebuilt with the call as a tool use holding its raw text under this key: the reply
then has a tool use to answer, and the model is shown what it wrote."""


class ReplayDiverged(RuntimeError):
    """The read being asked for is not the one the log holds at its position."""


def call_position(turn: int) -> str:
    """The position of the model call of ``turn``, which is also its id in the export."""
    return f"mc-{turn}"


def tool_prefix(turn: int) -> str:
    """The prefix of the positions of the reads that answer the model call of ``turn``."""
    return f"{call_position(turn)}-t"


def phases_before(turn: int) -> tuple[str, ...]:
    """The position prefixes of every phase that reads before the tools of ``turn``.

    >>> phases_before(3)
    ('pf-', 'mc-1-t', 'mc-2-t')
    """
    return (PREFETCH_PREFIX, *(tool_prefix(earlier) for earlier in range(1, turn)))


def response_text(message: AIMessage) -> str:
    """The text of ``message``: its content when that is a string, else its text blocks joined."""
    if isinstance(message.content, str):
        return message.content
    return "".join(
        block if isinstance(block, str) else str(block.get("text", ""))
        for block in message.content
        if isinstance(block, str) or block.get("type") == "text"
    )


@dataclass
class LoggedExecutor(Executor):
    """The executor with the log in front of it: a read the log holds at this position is
    returned, any other is made and appended. ``digests`` maps each position this executor
    reached to the digest of its logged event."""

    log: EventLog = field(kw_only=True)
    prefix: str = field(kw_only=True)
    earlier: tuple[str, ...] = field(kw_only=True)
    digests: dict[str, str] = field(default_factory=dict[str, str], kw_only=True)
    reached: int = field(default=0, kw_only=True)

    def __post_init__(self) -> None:
        for event in self.log.events(TOOL_RESULT):
            if not event.position.startswith(self.earlier):
                continue
            outcome = _decode_operation(event.data).outcome
            if isinstance(outcome, UnreachableOutcome):
                self.stopped.add(outcome.source)

    def call(self, origin: Origin, tool: str, arguments: Mapping[str, object]) -> Outcome:
        """The outcome of the call at the next position: the logged one, else a made one."""
        self.reached += 1
        position = f"{self.prefix}{self.reached}"
        held = self.log.find(TOOL_RESULT, position)
        if held is None:
            self.next_id = lambda: OperationId(position)
            outcome = super().call(origin, tool, arguments)
            held = self.log.append(TOOL_RESULT, position, _encode_operation(self.operations[-1]))
            self.digests[position] = held.digest
            return outcome
        operation = _decode_operation(held.data)
        asked = (origin, tool, thawed_json(frozen_json(dict(arguments), "arguments")))
        logged = (operation.origin, operation.tool, thawed_json(operation.arguments))
        if asked != logged:
            raise ReplayDiverged(f"{position}: the log holds {logged}, the replay asks {asked}")
        self.operations.append(operation)
        if isinstance(operation.outcome, UnreachableOutcome):
            self.stopped.add(operation.outcome.source)
        self.digests[position] = held.digest
        return operation.outcome


def conversation(context: RunContext, events: tuple[Event, ...], turns: int) -> list[BaseMessage]:
    """The request the model call after ``turns`` completed turns is asked with, from the log.

    The opening message names the leave and ``now`` and carries the prefetch's reads; no
    scenario id reaches the model. Raises ``RuntimeError`` when the log lacks a response or a
    tool result of a completed turn, which means graph state is ahead of the log.
    """
    by_position = {(event.kind, event.position): event for event in events}
    prefetch = [
        {key: event.data[key] for key in ("tool", "arguments", "outcome")}
        for event in events
        if event.kind == TOOL_RESULT and event.position.startswith(PREFETCH_PREFIX)
    ]
    opening = {
        "leave_id": context.leave_id,
        "now": encode_instant(context.now),
        "reference_timezone": context.reference_timezone,
        "prefetch": prefetch,
    }
    messages: list[BaseMessage] = [SystemMessage(SYSTEM), HumanMessage(canonical_json(opening))]
    for turn in range(1, turns + 1):
        response = by_position.get((MODEL_OUTCOME, call_position(turn)))
        if response is None:
            raise RuntimeError(f"graph state is at turn {turns}, the log holds no turn {turn}")
        calls = response.data["tool_calls"]
        unparsed = response.data["invalid_tool_calls"]
        messages.append(
            AIMessage(
                content=response.data["text"],
                tool_calls=[
                    {"name": call["tool"], "args": call["arguments"], "id": call["id"]}
                    for call in calls
                ]
                + [
                    {
                        "name": call["name"],
                        "args": {UNPARSED_ARGUMENTS: call["args"]},
                        "id": call["id"],
                    }
                    for call in unparsed
                ],
            )
        )
        for index, call in enumerate(calls, start=1):
            result = by_position.get((TOOL_RESULT, f"{tool_prefix(turn)}{index}"))
            if result is None:
                raise RuntimeError(f"the log holds no result for tool call {index} of turn {turn}")
            outcome = result.data["outcome"]
            status = "error" if outcome["kind"] == "refused_call" else "success"
            messages.append(
                ToolMessage(canonical_json(outcome), tool_call_id=call["id"], status=status)
            )
        for call in unparsed:
            messages.append(
                ToolMessage(canonical_json(UNPARSED_REPLY), tool_call_id=call["id"], status="error")
            )
    return messages


def request_digest(messages: list[BaseMessage]) -> str:
    """The digest of the logical request: the tool surface and every message, in one form."""
    rendered = [
        {
            "type": message.type,
            "content": message.content,
            "tool_calls": [
                {"name": call["name"], "args": call["args"], "id": call["id"]}
                for call in getattr(message, "tool_calls", [])
            ],
            "tool_call_id": getattr(message, "tool_call_id", None),
        }
        for message in messages
    ]
    surface = tool_surface_digest(TOOL_SPECIFICATIONS)
    return digest_of(sorted_canonical({"tool_surface": surface, "messages": rendered}))


def outcome_content(
    call: str,
    dispatch_attempt: int,
    digest: str,
    message: AIMessage,
    usage: dict[str, int] | None,
) -> dict[str, Any]:
    """What the log records of an answered model call: how the harness classified it, what the
    provider reported (``usage`` as the provider reported it, ``None`` when it reported none),
    and the response itself, the text, the tool calls and the calls that did not parse."""
    text = response_text(message)
    stop_reason = message.response_metadata.get("stopReason")
    latency = message.response_metadata.get("metrics", {}).get("latencyMs")
    return {
        "call": call,
        "role": ROLE,
        "dispatch_attempt": dispatch_attempt,
        "request_digest": digest,
        "outcome": classified(
            text, stop_reason, bool(message.tool_calls or message.invalid_tool_calls)
        ).value,
        "stop_reason": stop_reason,
        "provider_latency_ms": latency[0] if isinstance(latency, list) and latency else latency,
        "usage": usage,
        "text": text,
        "tool_calls": [
            {"id": call["id"], "tool": call["name"], "arguments": call["args"]}
            for call in message.tool_calls
        ],
        "invalid_tool_calls": [dict(call) for call in message.invalid_tool_calls],
    }


def classified(text: str, stop_reason: str | None, has_tool_calls: bool) -> ModelCallOutcome:
    """How the harness reads a response. Tool calls, the ones the client could not parse
    included, count only under a ``tool_use`` stop, since a call cut at the output limit
    arrives looking like one (the provider half's finding)."""
    if has_tool_calls and stop_reason == "tool_use":
        return ModelCallOutcome.TOOL_CALLS
    if not text.strip():
        return ModelCallOutcome.TEXT
    return ModelCallOutcome.CLAIMS if carries_claims(text) else ModelCallOutcome.INVALID_OUTPUT


def carries_claims(text: str) -> bool:
    """Whether ``text`` is a claims array the claims codec accepts."""
    try:
        decode_claims(text)
    except ValueError:
        return False
    return True
