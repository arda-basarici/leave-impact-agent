"""Scripted fillings for the worker's tests: a system whose turns are a script, a model client
answering from a script by the request's digest, a token counter from a script, and the
admission of a run over the golden world's first scenario.

The worker is tested through its real path (the skeleton's nodes over the appender, the
prefetch over the executor against in-memory ports holding the golden world) with only the
three protocols scripted, as the acceptance spike scripted its model. A scripted client
answers by the request's digest and never by an invocation counter, so a recovering worker
that restates a request gets the same answer and a repeated send is visible as one more
entry in ``sends`` and nowhere else.

Since the graph step the real turns run through the same bench: ``investigator_inputs``
freezes what a run under them records, and ``ContentScriptedClient`` answers by the number
of assistant messages the request carries, since a request the real turns build has no
digest a script could know in advance; a recovering worker that restates a request gets the
same answer by the same count.

``SCRIPTS`` names the runs a process can be told to drive (the crash matrix's children, the
bench): each a ``RunScript``, the system and client built over the context and what the
script takes of the world (its material, computed once by whoever holds the world and
passed on as data, since the sealed world is neither pickled nor loaded in seconds), the
frozen inputs its admission records, and the ports it runs over. The stating script is
the smoke's run, the real turns reading a policy document and stating its clause's
requirement truthfully in the forced finalization call; the contradicting one is the same
run over a people port whose read by id answers the enumeration's record with another
name, the HR system contradicting itself, which the conclusion fails the run at.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from hashlib import sha256
from typing import Any, cast

from leaveimpact.agent.answer_parse import FACT_TOOL
from leaveimpact.agent.assets import load_prompt_assets
from leaveimpact.agent.composer import composing_policy
from leaveimpact.agent.execution import ReadPorts
from leaveimpact.agent.graph import ModelClient, ReviewPayload, TurnRequest, Turns
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
from leaveimpact.agent.surface import surface_digest
from leaveimpact.agent.turns import InvestigatorTurns
from leaveimpact.core.counting_operations import Counted, CountOutcome
from leaveimpact.core.entities import Document, DocumentSection, Employee
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import ClauseId, EmployeeId, employee_id
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.model_calls import CompleteResponse, Observation, Sent, ServiceError
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.ports.observed import Observed
from leaveimpact.core.ports.read import PeopleReader
from leaveimpact.core.prefetch import prefetch_rule
from leaveimpact.core.refs import clause_ref
from leaveimpact.core.run_trace import OperationId
from leaveimpact.core.stated import StatedFact
from leaveimpact.core.tools import Role
from leaveimpact.core.values import Requirement, SkillCriterion
from leaveimpact.core.worldtime import RunContext
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.stating_fixture import title_of
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


def investigator_inputs(context: RunContext) -> FrozenInputs:
    """The frozen inputs of a run under the real turns: the fixtures' with the prompt assets'
    digests, the investigator's surface digest, the composing policy and the prefetch rule
    this code computes, what the agent's provenance freezes (the evaluator holds a run to
    its prefetch plan only under this code's rule)."""
    return replace(
        admitted_inputs(context),
        prefetch_rule=prefetch_rule(),
        prompt_digests=load_prompt_assets().prompt_digests(cases.ROLE),
        tool_surface_digests=((cases.ROLE, surface_digest(Role.INVESTIGATOR)),),
        composing_policy=composing_policy(),
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
    The input reads named are every operation the log holds before the call; the call
    numbered ``final_call`` is flagged as the system's finalization."""

    bodies: Sequence[JsonObject]
    payload: ReviewPayload = field(default_factory=lambda: ReviewPayload((), cases.RULES))
    role: str = cases.ROLE
    name_reads: bool = False
    final_call: int | None = None

    def request_for(self, state: AttemptState, call: int) -> TurnRequest | None:
        if call > len(self.bodies):
            return None
        reads: tuple[OperationId, ...] = ()
        return TurnRequest(self.role, self.bodies[call - 1], reads, call == self.final_call)

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
class ContentScriptedClient:
    """Answers ``answers[k]`` to a request carrying ``k`` assistant messages; every send is
    recorded with its digest and its body."""

    answers: Sequence[Sent]
    sends: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])
    bodies: list[JsonObject] = field(default_factory=list[JsonObject])
    operation: str = "Converse"
    client_region: str = "eu-central-1"

    def send(self, requested_profile: str, body: JsonObject) -> Sent:
        self.sends.append((requested_profile, request_digest(body)))
        self.bodies.append(body)
        return self.answers[assistant_turns(body)]


def assistant_turns(body: JsonObject) -> int:
    """How many assistant messages ``body``'s conversation holds."""
    messages = body["messages"]
    assert isinstance(messages, list)
    held = cast("list[JsonObject]", messages)
    return sum(1 for message in held if message["role"] == "assistant")


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
    """A port whose one method answers unreachable from its ``after``-th call on in this
    process, every other call passing through: an outage of one read in a source that
    otherwise answers, placed after the prefetch's own call of it when ``after`` is one."""

    def __init__(self, inner: object, method: str, source: Source, after: int = 0) -> None:
        self._inner = inner
        self._method = method
        self._source = source
        self._after = after
        self.calls = 0

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name != self._method:
            return attribute

        def guarded(*args: Any, **kwargs: Any) -> Any:
            self.calls += 1
            if self.calls > self._after:
                raise SourceUnreachable(self._source, "provoked by the test")
            return attribute(*args, **kwargs)

        return guarded


def with_unreachable(ports: ReadPorts, method: str, *, after: int = 0) -> ReadPorts:
    """``ports`` with the people system's ``method`` unreachable from its ``after``-th call."""
    return replace(
        ports,
        people=UnreachableMethod(ports.people, method, Source.FRAPPE, after),  # type: ignore[arg-type]
    )


class RenamingRead:
    """A people port whose read by id answers the record with another name, the enumeration
    untouched: the HR system returning one employee two ways, the self-contradiction the
    conclusion fails a run at once both reads are logged (``core.contradictions``)."""

    def __init__(self, inner: PeopleReader) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def employee(self, id: EmployeeId) -> Observed[Employee] | None:
        observed = self._inner.employee(id)
        if observed is None:
            return None
        renamed = replace(observed.value, name=f"{observed.value.name} (as read by id)")
        return Observed(renamed, observed.source)


def with_contradicting_employee(ports: ReadPorts) -> ReadPorts:
    """``ports`` with the people system's read by id disagreeing with its enumeration."""
    return replace(ports, people=RenamingRead(ports.people))  # type: ignore[arg-type]


# --- The reference script --------------------------------------------------------------------


def two_call_script(context: RunContext) -> tuple[ScriptedTurns, ScriptedClient]:
    """The reference run: call 1 asks for two reads, the leave and one employee (a people
    read the investigator's surface declares; the enumeration it asked for before the
    registry step is the prefetch's alone and would be refused), call 2 answers with text
    and no read; the run completes under the automatic approval."""
    bodies = (body_for(1), body_for(2))
    leaver = context.leave_id
    answers = {
        request_digest(bodies[0]): (
            answered(
                text("Looking the leave and the first employee up."),
                tool_use("tooluse_leave", "leave", {"id": str(leaver)}),
                tool_use("tooluse_people", "employee", {"id": str(employee_id(1))}),
                stop_reason="tool_use",
            ),
        ),
        request_digest(bodies[1]): (answered(text("Nothing further to read.")),),
    }
    return ScriptedTurns(bodies), ScriptedClient(answers)


def throttled_script(context: RunContext) -> tuple[ScriptedTurns, ScriptedClient]:
    """The infrastructure stop: the two-call turns, with every dispatch of the first call
    answered by a throttle, so the call exhausts the registered maximum and the attempt
    fails by infrastructure at its last dispatch's send; no read the model asked for, no
    approval, no claims. The crash matrix's second reference."""
    turns, _ = two_call_script(context)
    throttled = observed(ServiceError(429, "ThrottlingException", None, "too many requests"))
    return turns, ScriptedClient({request_digest(turns.bodies[0]): (throttled,)})


def a_read_comment(world: SealedWorld) -> tuple[str, str, str]:
    """A comment the prefetch's enumeration returns: its id, its author and a quote inside
    its text (the stand-in prose names nobody, so the anchor guard refuses a fact on it)."""
    comment = next(
        c
        for scenario in world.scenarios
        for item in scenario.owned.work_items
        for c in item.entity.comments
    )
    return comment.id, comment.author_id, comment.text.split("] ", 1)[-1][:30]


def investigator_script(
    world: SealedWorld, context: RunContext, *, probe_tool: str = "probe_tool"
) -> tuple[InvestigatorTurns, ContentScriptedClient]:
    """The reference run of the real turns: the first answer reads one employee, calls a
    tool the role does not declare (``probe_tool``, a name the capture varies), makes a call
    whose input is no object, and states one fact the guard refuses beside an entry the
    parser cannot read; the second answer reads nothing, so the loop ends; the forced last
    call states the fact again. Three sends, three counts, every ``toolUse`` answered."""
    carrier, author, quote = a_read_comment(world)
    entry = {
        "carrier": carrier,
        "predicate": "has_skill",
        "subject": author,
        "value": "kafka",
        "quote": quote,
    }
    answers = (
        answered(
            text("Reading an employee and probing."),
            tool_use("tu_emp", "employee", {"id": str(employee_id(1))}),
            tool_use("tu_probe", probe_tool, {}),
            tool_use("tu_bad", "leave", "not an object"),
            fact_tool("tu_facts", entry, "not an entry"),
            stop_reason="tool_use",
        ),
        answered(text("Nothing further to read.")),
        answered(fact_tool("tu_final", entry), stop_reason="tool_use"),
    )
    return InvestigatorTurns(load_prompt_assets()), ContentScriptedClient(answers)


@dataclass(frozen=True)
class PlantedRequirement:
    """A planted document, one of its sections carrying a sealed requirement, and that
    requirement stated as the truthful stater writes it: what the stating script takes of
    the world."""

    document: Document
    section: DocumentSection
    stated: StatedFact


def a_planted_requirement(world: SealedWorld) -> PlantedRequirement:
    """The first planted section carrying a sealed requirement about skills alone, stated
    truthfully: the quote the section's whole text, the span the title of what the sealed
    world scopes the clause to (the smoke's valid forced fact; the stand-in prose names
    nobody, so a skill fact on a comment is refused by the anchor guard and a requirement
    is not)."""
    for scenario in world.scenarios:
        for planted in scenario.owned.documents:
            document = planted.entity
            for section in document.sections:
                carrier = clause_ref(ClauseId(section.id))
                for fact in world.index.carried.get(carrier, ()):
                    if not isinstance(fact.value, Requirement):
                        continue
                    if not all(isinstance(c, SkillCriterion) for c in fact.value.criteria):
                        continue
                    span = title_of(world, world.index.scope[ClauseId(section.id)])
                    stated = StatedFact(
                        fact.predicate, fact.subject, fact.value, carrier, section.text, span
                    )
                    return PlantedRequirement(document, section, stated)
    raise AssertionError("the world plants no requirement about skills alone")


def stating_script(
    planted: PlantedRequirement, context: RunContext
) -> tuple[InvestigatorTurns, ContentScriptedClient]:
    """The smoke's run of the real turns: the first answer reads one employee and the
    document holding ``planted``'s requirement, the second reads nothing, so the loop
    ends, and the forced finalization call states that requirement truthfully, which the
    guard admits. Three sends, three counts."""
    answers = (
        answered(
            text("Reading an employee and the policy."),
            tool_use("tu_emp", "employee", {"id": str(employee_id(1))}),
            tool_use("tu_doc", "document", {"id": planted.document.id}),
            stop_reason="tool_use",
        ),
        answered(text("Nothing further to read.")),
        answered(
            fact_tool("tu_final", histories.entry_of(planted.stated)), stop_reason="tool_use"
        ),
    )
    return InvestigatorTurns(load_prompt_assets()), ContentScriptedClient(answers)


def text_only_finalization(
    planted: PlantedRequirement, context: RunContext
) -> tuple[InvestigatorTurns, ContentScriptedClient]:
    """The stating script with its forced finalization call answered by text alone, no fact
    call: the turns ask nothing after it and the payload is the baseline's."""
    turns, client = stating_script(planted, context)
    return turns, replace(client, answers=(*client.answers[:-1], answered(text("Done."))))


@dataclass(frozen=True)
class RunScript[M]:
    """A run a process can be told to drive by name: what it takes of the world (``material``,
    computed by whoever holds the world, ``None`` for a scripted system), the system and
    client built over that and the context, the frozen inputs its admission records (the
    fixtures' for a scripted system, the real turns' for the investigator's), and the ports
    it runs over, the planted ones unless the script changes a source's behaviour."""

    build: Callable[[M, RunContext], tuple[Turns, ModelClient]]
    material: Callable[[SealedWorld], M]
    inputs: Callable[[RunContext], FrozenInputs] = admitted_inputs
    ports: Callable[[ReadPorts], ReadPorts] = lambda ports: ports

    def over(self, world: SealedWorld, context: RunContext) -> tuple[Turns, ModelClient]:
        """The system and client, for a caller that holds the world."""
        return self.build(self.material(world), context)


def _scripted(
    factory: Callable[[RunContext], tuple[ScriptedTurns, ScriptedClient]],
) -> RunScript[None]:
    return RunScript(lambda material, context: factory(context), lambda world: None)


SCRIPTS: Mapping[str, RunScript[Any]] = {
    "two-call": _scripted(two_call_script),
    "throttled": _scripted(throttled_script),
    "stating": RunScript(stating_script, a_planted_requirement, investigator_inputs),
    "contradicting": RunScript(
        stating_script, a_planted_requirement, investigator_inputs, with_contradicting_employee
    ),
}
"""The runs by name, for a process that is told which to drive."""


def sends_of(client: ScriptedClient) -> int:
    return len(client.sends)


def calls_in(state: AttemptState) -> int:
    return len(calls_of(state))


__all__ = [
    "ADMITTER",
    "RESERVATION",
    "ContentScriptedClient",
    "PlantedRequirement",
    "RenamingRead",
    "RunScript",
    "ScriptedClient",
    "ScriptedCounter",
    "ScriptedTurns",
    "admission",
    "a_planted_requirement",
    "a_read_comment",
    "admitted_inputs",
    "answered",
    "assistant_turns",
    "body_for",
    "calls_in",
    "fact_tool",
    "golden_context",
    "in_flight",
    "investigator_inputs",
    "investigator_script",
    "observed",
    "request_digest",
    "sends_of",
    "settled",
    "stating_script",
    "text",
    "text_only_finalization",
    "tool_use",
    "throttled_script",
    "two_call_script",
    "with_contradicting_employee",
    "with_unreachable",
]
