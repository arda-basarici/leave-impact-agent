"""Scripted fillings for the worker's tests: a system whose turns are a script, a model client
answering from a script by the request's digest, a token counter from a script, and the
admission of a run over the golden world's first scenario.

The worker is tested through its real path (the skeleton's nodes over the appender, the
prefetch over the executor against in-memory ports holding the golden world) with only the
three protocols scripted, as the acceptance spike scripted its model. A scripted client
answers by the request's digest and never by an invocation counter, so a recovering worker
that restates a request gets the same answer and a repeated send is visible as one more
entry in ``sends`` and nowhere else.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from hashlib import sha256
from typing import Any

from leaveimpact.agent.answer_parse import FACT_TOOL
from leaveimpact.agent.execution import ReadPorts
from leaveimpact.agent.graph import ReviewPayload, Sent, TurnRequest
from leaveimpact.agent.log_events import (
    Admitted,
    EventKind,
    FrozenInputs,
    LoggedEvent,
    Producer,
    SegmentEnded,
    SegmentStarted,
    event_key,
    kind_of,
)
from leaveimpact.agent.log_transition import AttemptState, calls_of
from leaveimpact.core.counting_operations import Counted, CountOutcome
from leaveimpact.core.enums import Source
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.model_calls import CompleteResponse, Observation
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.run_trace import OperationId
from leaveimpact.core.worldtime import RunContext
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.throwaway_world import loaded_world

ADMITTER = Producer("admitter")
RESERVATION = 10 * cases.ALLOCATION
"""Room for ten dispatches at the fixtures' worst case."""


def golden_context() -> RunContext:
    """The golden world's first scenario, the one every worker test investigates."""
    world = loaded_world("golden")
    return world.context_of(world.scenarios[0])


def admitted_inputs(context: RunContext | None = None) -> FrozenInputs:
    """The fixtures' frozen inputs for a model-calling run of ``context``."""
    return replace(
        histories.inputs(reservation=RESERVATION),
        context=context if context is not None else golden_context(),
    )


def admission(inputs: FrozenInputs) -> tuple[LoggedEvent, ...]:
    """The one-event log of an attempt just admitted."""
    return (LoggedEvent(1, cases.ADMITTED, ADMITTER, Admitted(inputs)),)


def request_digest(body: JsonObject) -> str:
    return sha256(canonical_bytes(body)).hexdigest()


# --- The scripted system ---------------------------------------------------------------------


def body_for(call: int, *, prompt: str = "investigate") -> JsonObject:
    """A Converse body that differs per logical call and names the fixtures' output maximum."""
    return {
        "system": [{"text": prompt}],
        "messages": [{"role": "user", "content": [{"text": f"turn {call}"}]}],
        "inferenceConfig": {"maxTokens": cases.OUTPUT_MAXIMUM, "temperature": 0},
    }


@dataclass(frozen=True)
class ScriptedTurns:
    """``bodies[n - 1]`` is call ``n``'s body; past the script the system asks nothing more.
    The input reads named are every operation the log holds before the call."""

    bodies: Sequence[JsonObject]
    payload: ReviewPayload = field(default_factory=lambda: ReviewPayload((), cases.RULES))
    role: str = cases.ROLE
    name_reads: bool = False

    def request_for(self, state: AttemptState, call: int) -> TurnRequest | None:
        if call > len(self.bodies):
            return None
        reads: tuple[OperationId, ...] = ()
        return TurnRequest(self.role, self.bodies[call - 1], reads)

    def payload_for(self, state: AttemptState) -> ReviewPayload:
        return self.payload


@dataclass
class ScriptedClient:
    """Answers by the request's digest, in order per digest; every send is recorded."""

    answers: Mapping[str, Sequence[Sent]]
    sends: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    given: dict[str, int] = field(default_factory=dict[str, int])
    operation: str = "Converse"
    client_region: str = "eu-central-1"

    def send(self, requested_profile: str, body: JsonObject) -> Sent:
        digest = request_digest(body)
        self.sends.append((requested_profile, digest))
        index = self.given.get(digest, 0)
        self.given[digest] = index + 1
        script = self.answers[digest]
        return script[min(index, len(script) - 1)]


@dataclass
class ScriptedCounter:
    """Answers from ``outcomes`` in order, the last one repeated; every call is recorded."""

    outcomes: Sequence[CountOutcome] = (Counted(cases.INPUT_BOUND, None, 12),)
    asked: list[tuple[str, Mapping[str, object]]] = field(
        default_factory=list[tuple[str, Mapping[str, object]]]
    )

    def count(self, counting_identifier: str, projection: Mapping[str, object]) -> CountOutcome:
        self.asked.append((counting_identifier, dict(projection)))
        return self.outcomes[min(len(self.asked) - 1, len(self.outcomes) - 1)]


# --- Responses -------------------------------------------------------------------------------


def answered(*blocks: JsonObject, stop_reason: str = "end_turn") -> Sent:
    """A complete response with ``blocks`` as its content."""
    body = histories.body(stop_reason, *blocks)
    return Sent(CompleteResponse(stop_reason, 840, 0), body, None)


def observed(observation: Observation) -> Sent:
    """A send that produced ``observation`` and no response body."""
    return Sent(observation, None, None)


def text(content: str) -> JsonObject:
    return histories.text(content)


def tool_use(identifier: str, name: str, arguments: object) -> JsonObject:
    return histories.tool_use(identifier, name, arguments)


def fact_tool(identifier: str, *entries: object) -> JsonObject:
    return tool_use(identifier, FACT_TOOL, histories.payload(*entries))


# --- Comparing two logs of one attempt ---------------------------------------------------------

IN_FLIGHT_KINDS = (EventKind.COUNT_STARTED, EventKind.DISPATCH_INTENT)
REQUEST_KINDS = (
    EventKind.COUNT_STARTED,
    EventKind.COUNT_OUTCOME,
    EventKind.DISPATCH_INTENT,
    EventKind.DISPATCH_OUTCOME,
)


def settled(events: Sequence[LoggedEvent]) -> list[tuple[str, tuple[object, ...]]]:
    """Every event but the segment boundaries and the counting and dispatch requests, by kind
    and key: what two logs of one attempt agree on however many segments and in-flight
    requests each took."""
    return [
        (kind_of(e.event).value, event_key(e)[1])
        for e in events
        if not isinstance(e.event, SegmentStarted | SegmentEnded)
        and kind_of(e.event) not in REQUEST_KINDS
    ]


def in_flight(events: Sequence[LoggedEvent]) -> list[tuple[object, ...]]:
    """The keys of the counting and dispatch requests ``events`` hold no outcome for."""
    outcomes = {
        event_key(e)[1]
        for e in events
        if kind_of(e.event) in (EventKind.COUNT_OUTCOME, EventKind.DISPATCH_OUTCOME)
    }
    return [
        event_key(e)[1]
        for e in events
        if kind_of(e.event) in IN_FLIGHT_KINDS and event_key(e)[1] not in outcomes
    ]


# --- Outages -----------------------------------------------------------------------------------


class UnreachableMethod:
    """A port whose one method answers unreachable, every other call passing through: an
    outage of one read in a source that otherwise answers."""

    def __init__(self, inner: object, method: str, source: Source) -> None:
        self._inner = inner
        self._method = method
        self._source = source

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name != self._method:
            return attribute

        def unreachable(*args: Any, **kwargs: Any) -> Any:
            raise SourceUnreachable(self._source, "provoked by the test")

        return unreachable


def with_unreachable(ports: ReadPorts, method: str) -> ReadPorts:
    """``ports`` with the people system's ``method`` unreachable."""
    return replace(ports, people=UnreachableMethod(ports.people, method, Source.FRAPPE))  # type: ignore[arg-type]


# --- The reference script --------------------------------------------------------------------


def two_call_script(context: RunContext) -> tuple[ScriptedTurns, ScriptedClient]:
    """The reference run: call 1 asks for two reads about the leaver's team and the leaver,
    call 2 answers with text and no read; the run completes under the automatic approval."""
    bodies = (body_for(1), body_for(2))
    leaver = context.leave_id
    answers = {
        request_digest(bodies[0]): (
            answered(
                text("Looking the leave and the team up."),
                tool_use("tooluse_leave", "leave", {"id": str(leaver)}),
                tool_use("tooluse_people", "employees", {}),
                stop_reason="tool_use",
            ),
        ),
        request_digest(bodies[1]): (answered(text("Nothing further to read.")),),
    }
    return ScriptedTurns(bodies), ScriptedClient(answers)


def sends_of(client: ScriptedClient) -> int:
    return len(client.sends)


def calls_in(state: AttemptState) -> int:
    return len(calls_of(state))


__all__ = [
    "ADMITTER",
    "RESERVATION",
    "ScriptedClient",
    "ScriptedCounter",
    "ScriptedTurns",
    "admission",
    "admitted_inputs",
    "answered",
    "body_for",
    "calls_in",
    "fact_tool",
    "golden_context",
    "in_flight",
    "observed",
    "request_digest",
    "sends_of",
    "settled",
    "text",
    "tool_use",
    "two_call_script",
    "with_unreachable",
]
