"""The execution skeleton: the five nodes of an attempt, each writing through the appender
before it returns, with the system's own content supplied through two small protocols.

The investigator's prompts, tools and composition are later build steps'; what every one
of their nodes needs is here, once: the prefetch over the executor with each read appended
as it resolves, the model call as the log fixes it (the bound established by a durable
count, the intent committed before the send, the outcome appended as it arrived), the
model's read calls resolved in the answer's order with each resolution committed before
the next begins, the finalization and the approval request, the interrupt, the resume, and
the closing event. The nodes read the attempt's state as the authority and the log as the
only memory: a node entered again, in this process or by the worker that recovers the
attempt, finds in the state what was done and does only what was not (the event log step's
rulings on tool calls from the log, parts 5 and 8, and on recovery, part 4). Checkpointed
state is a cursor, the route and the positions reached, and never something a result could
be rebuilt from.

*The system's two protocols.* ``Turns`` gives the request a logical call makes, as a
function of the state before it, and the review payload the run ends with; the request of
a call in progress must come back as the same bytes, since a re-dispatch sends the request
its first intent named, and a difference is this harness's defect. ``ModelClient`` sends a
body to a profile and answers with what arrived, the observation, the response for a
complete one and the digest of the bytes sent when it recorded them; ``TokenCounter``
answers the counting call. The tests fill the three with scripts; the live run fills them
with the Bedrock clients.

*The model call, in order.* The account is asked first, with the worst case the bound and
the output maximum give: a loop allocation that does not fit enters finalization and the
system is asked again for the finalization's request, a finalization allocation that does
not fit ends the run at its cap, through the approval of what it has (the ruling on the
ledger, part 4). A call keeps the purpose it was first authorized under: a loop call in
progress at the entry is re-dispatched with the same bytes and finishes from the reserve
(the graph step's rulings, amendment 2). The system declares the finalization too: a
request it flags final has the finalization event appended before the call's first
event, when the account has not entered it already (fork 2), so the call is accounted as
the finalization on both paths and the export's position shows the entry. The bound rests
on a durable count under the request's reuse key, reused when one exists, else counted
under the policy's retries with the log as the counter; a counting request is committed
before the counting call and its outcome after, and the transition records the stop when
the group is exhausted or refused. The request of a call is a function of the log below
the call's first event (amendment 5), so a count started since the previous call settled,
or since the entry into finalization, under another digest than the request now restated
is this harness's defect and is raised, as a restated intent is; the loop request counted
before the account entered finalization lies below the entry and is left behind, which is
the one legitimate recount. The entry the model node declares is appended after that
check has read the boundary, so a declared finalization hides no count.
The intent is appended and committed before anything leaves the machine (the ruling on one
writer, part 5); the outcome is appended as it arrived, attributed by the registered table;
then the within-call decision says whether to dispatch again after the registered delay,
measured from the outcome's logged timestamp on the log's own clock.

*What a read call gets.* A call of the fact tool and a call whose arguments are no object
run nothing (the parse module handles them); a read against a source a durable outcome has
marked unreachable is a skip, recorded as the worker's final decision; any other read runs
through the executor over the call's role's surface (the registry step) and its result is
appended, a wrapper's refusal included, a tool the role is not shown among the refusals. A
stop the transition records on an append, a malformed record's or a defect the conclusion
derives (a source contradicting itself, found at the read that completed it), ends the
sequence before the next port call, in the prefetch as in an answer's reads (the graph
step's rulings, amendment 1). What the model is shown of each result is the rendering
module's, from the logged resolution.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Protocol, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver

# The pinned library is typed, but it is installed as a namespace package (no top-level
# ``__init__``), whose ``py.typed`` pyright does not see; its types read as partially
# unknown and the three sites that touch them are marked.
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import interrupt

from leaveimpact.agent.answer_parse import FACT_TOOL, ToolUse, stop_reason_of, tool_uses
from leaveimpact.agent.appender import Appender
from leaveimpact.agent.execution import Executor, ReadPorts, run_prefetch
from leaveimpact.agent.log_events import (
    ApprovalRequested,
    CapExhausted,
    Completed,
    CountKey,
    CountOutcomeLogged,
    CountStarted,
    DispatchIntent,
    DispatchOutcome,
    Failed,
    FinalizationEntered,
    FrozenInputs,
    LoggedEvent,
    ModelReadKey,
    OperationEvent,
    OperationKey,
    OperationResult,
    OperationSkip,
    PrefetchKey,
    Resumed,
    call_id,
    count_id,
    event_digest,
)
from leaveimpact.agent.log_transition import (
    AttemptState,
    CallEvents,
    call_purpose,
    calls_of,
    count_group,
    counts_of,
    operations_of,
)
from leaveimpact.core.attribution import AttributionTable, RedispatchPolicy, attribute
from leaveimpact.core.call_decision import CallDecision, decide_call
from leaveimpact.core.claims import Claim
from leaveimpact.core.counting_operations import Counted, CountOutcome, read_outcome
from leaveimpact.core.input_bound import (
    CountDecision,
    EstablishedBound,
    count_decision,
    counted_projection,
    output_maximum,
    worst_case_tokens,
)
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.model_calls import (
    TOOL_USE_STOP,
    CompleteResponse,
    Sent,
    UndispatchedReason,
)
from leaveimpact.core.pricing import worst_case_cost
from leaveimpact.core.run_account import AccountIntent, AuthorizationDecision, authorize
from leaveimpact.core.run_ending import Composition
from leaveimpact.core.run_parts_json import review_payload_digest
from leaveimpact.core.run_trace import (
    ModelOrigin,
    OperationId,
    Origin,
    Outcome,
    PrefetchOrigin,
    UnreachableOutcome,
)
from leaveimpact.core.tools import (
    TOOL_SPECIFICATIONS,
    Role,
    ToolSpecification,
    role_surface,
    specification_named,
)

DURABILITY = "sync"
"""Every invocation waits for its checkpoint (the acceptance spike's accepted configuration)."""


# --- The system's protocols ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TurnRequest:
    """One logical call as the system asks it: the role, the Converse body as the client
    will send it, the operations whose returned records the body rendered, and whether it
    is the system's finalization call, after which it asks nothing more (the graph step,
    fork 2: the model node declares the finalization before dispatching a flagged request
    when the account has not)."""

    role: str
    body: JsonObject
    input_reads: tuple[OperationId, ...]
    final: bool = False


@dataclass(frozen=True, slots=True)
class ReviewPayload:
    """What the run asks to have approved: its claims and how they were composed."""

    claims: tuple[Claim, ...]
    composition: Composition


class Turns(Protocol):
    """The system's content: the request of logical call ``call`` given the state before it,
    ``None`` when the system has nothing more to ask and the run finalizes; and the review
    payload. Both are functions of the state alone (see the module)."""

    def request_for(self, state: AttemptState, call: int) -> TurnRequest | None: ...

    def payload_for(self, state: AttemptState) -> ReviewPayload: ...


class ModelClient(Protocol):
    """One serialized client of the inference API: the operation it calls and the region it
    calls from are the intent's provenance; ``send`` makes exactly one send."""

    @property
    def operation(self) -> str: ...

    @property
    def client_region(self) -> str: ...

    def send(self, requested_profile: str, body: JsonObject) -> Sent: ...


class TokenCounter(Protocol):
    """The counting call: the counted projection of a request, asked of a counting identifier."""

    def count(self, counting_identifier: str, projection: Mapping[str, object]) -> CountOutcome: ...


@dataclass(frozen=True)
class Harness:
    """What the nodes work with: the appender of this generation, the system's turns, the
    two clients, the ports the executor reads through, and the wait seam."""

    appender: Appender
    turns: Turns
    client: ModelClient
    counter: TokenCounter
    ports: ReadPorts
    sleep: Callable[[float], None]
    boundary: Callable[[str], None] = lambda name: None
    """Named points of the approval handoff a crash check kills at; a no-op in production."""

    @property
    def inputs(self) -> FrozenInputs:
        inputs = self.appender.state.inputs
        assert inputs is not None
        return inputs


# --- The cursor ------------------------------------------------------------------------------


def _merged(held: dict[str, str], reached: dict[str, str]) -> dict[str, str]:
    return {**held, **reached}


class Cursor(TypedDict):
    """The checkpointed state: where the loop goes next, whether a finalization allocation
    was refused (the run then ends at its cap), and the digest of each logged event a node
    reached, by position."""

    route: str
    at_cap: bool
    reached: Annotated[dict[str, str], _merged]


INITIAL: Cursor = {"route": "", "at_cap": False, "reached": {}}


def _reached(events: tuple[LoggedEvent, ...], since: int) -> dict[str, str]:
    return {str(e.position): event_digest(e.event) for e in events[since:]}


# --- Reads through the executor -------------------------------------------------------------


class LoggedExecutor(Executor):
    """The executor with every resolution appended as it happens and every held one reused:
    a read the log already holds is answered from the log and never made again, and a read
    made is appended before the next begins (the ruling on tool calls, part 5).

    A stopped source is one a durable unreachable outcome marked, in the order the log
    shows: the operations before the replayed phase's first held operation count from the
    start, the phase's own count only as their held results are replayed, and operations
    after the phase (a model's reads, during a prefetch replay) count not at all, so a
    replay skips exactly the calls the first run skipped and the ordinals it assigns are the
    first run's (the worker group's review, second finding, and its second read's first). A
    reused result is held to the tool and arguments the replay asks for; a difference is a
    fault of this harness.
    """

    def __init__(
        self,
        harness: Harness,
        *,
        replaying: Callable[[OperationKey], bool],
        surface: tuple[ToolSpecification, ...] = TOOL_SPECIFICATIONS,
    ) -> None:
        super().__init__(harness.ports, surface=surface)
        self.appender = harness.appender
        self.stopped = set()
        for logged in operations_of(self.appender.state):
            operation = _operation(logged)
            if replaying(operation.key):
                break
            resolution = operation.resolution
            if (
                isinstance(resolution, OperationResult)
                and isinstance(resolution.outcome, UnreachableOutcome)
                and resolution.source is not None
            ):
                self.stopped.add(resolution.source)
        # The ordinal counts this process's calls; a held read is reused by it, never skipped.
        self.prefetched = 0

    def call(self, origin: Origin, tool: str, arguments: Mapping[str, object]) -> Outcome:
        """The prefetch's path: its next ordinal, resolved from the log or made and appended."""
        if not isinstance(origin, PrefetchOrigin):
            raise ValueError("a model's read goes through resolve, with its key")
        self.prefetched += 1
        return self.resolve(PrefetchKey(self.prefetched), origin, tool, arguments)

    def resolve(
        self, key: OperationKey, origin: Origin, tool: str, arguments: Mapping[str, object]
    ) -> Outcome:
        """The read under ``key``: the held result when the log holds one, else made through
        the executor and appended, the result being this call's return."""
        held = _held_operation(self.appender.state, key)
        if held is not None:
            if not isinstance(held, OperationResult):
                raise ValueError(f"{key} was skipped; a skipped read is not resolved again")
            if held.tool != tool or dict(held.arguments) != dict(arguments):
                raise RuntimeError(
                    f"the replay asks {key} for {tool!r} with other arguments than the log holds "
                    f"for {held.tool!r}"
                )
            if isinstance(held.outcome, UnreachableOutcome) and held.source is not None:
                self.stopped.add(held.source)
            return held.outcome
        outcome = super().call(origin, tool, arguments)
        made = self.operations[-1]
        self.appender.append(
            OperationEvent(key, OperationResult(made.tool, made.source, made.arguments, outcome))
        )
        return outcome


def _held_operation(
    state: AttemptState, key: OperationKey
) -> OperationResult | OperationSkip | None:
    for logged in operations_of(state):
        operation = _operation(logged)
        if operation.key == key:
            return operation.resolution
    return None


def _operation(logged: LoggedEvent) -> OperationEvent:
    event = logged.event
    assert isinstance(event, OperationEvent)
    return event


# --- The nodes -------------------------------------------------------------------------------


def build(harness: Harness, saver: BaseCheckpointSaver[Any]) -> Any:
    """The compiled graph over ``harness``, checkpointed by ``saver``, with no retry policy
    anywhere (a node that raises is the driver's to classify, never rerun)."""
    appender = harness.appender

    def prefetch(state: Cursor) -> dict[str, Any]:
        since = appender.state.last_position
        executor = LoggedExecutor(harness, replaying=lambda key: isinstance(key, PrefetchKey))
        run_prefetch(
            executor,
            harness.inputs.context,
            halted=lambda: appender.state.stopped is not None,
        )
        route = "terminal" if appender.state.stopped is not None else "model"
        return {"route": route, "reached": _reached(appender.state.events, since)}

    def model(state: Cursor) -> dict[str, Any]:
        since = appender.state.last_position
        route, at_cap = _model_step(harness)
        return {
            "route": route,
            "at_cap": state["at_cap"] or at_cap,
            "reached": _reached(appender.state.events, since),
        }

    def tools(state: Cursor) -> dict[str, Any]:
        since = appender.state.last_position
        _resolve_reads(harness)
        return {"route": "model", "reached": _reached(appender.state.events, since)}

    def approval(state: Cursor) -> dict[str, Any]:
        since = appender.state.last_position
        held = appender.state
        if held.approval_requested is None:
            if held.finalization_entered is None:
                appender.append(FinalizationEntered())
            payload = harness.turns.payload_for(appender.state)
            appender.append(
                ApprovalRequested(payload.claims, payload.composition, state["at_cap"])
            )
        request = appender.state.approval_requested
        assert request is not None and isinstance(request.event, ApprovalRequested)
        digest = review_payload_digest(request.event.claims, request.event.composition)
        delivered: object = interrupt({"payload_digest": digest})
        if delivered != digest:
            raise RuntimeError("the graph was resumed with a digest that is not its request's")
        harness.boundary("approval:node-resumed")
        if appender.state.resumed is None:
            appender.append(Resumed())
        return {"route": "terminal", "reached": _reached(appender.state.events, since)}

    def terminal(state: Cursor) -> dict[str, Any]:
        since = appender.state.last_position
        held = appender.state
        if held.closed is None:
            stopped = held.stopped
            if stopped is not None:
                appender.close(Failed(stopped.category, stopped.site, stopped.reason, None))
            elif _at_cap(held):
                appender.close(CapExhausted(None))
            else:
                appender.close(Completed(None))
        return {"route": "", "reached": _reached(appender.state.events, since)}

    builder = StateGraph(Cursor)
    for node in (prefetch, model, tools, approval, terminal):
        builder.add_node(node.__name__, node)  # pyright: ignore[reportUnknownMemberType]
    builder.add_edge(START, "prefetch")
    builder.add_conditional_edges("prefetch", _route, {"model": "model", "terminal": "terminal"})
    builder.add_conditional_edges(
        "model",
        _route,
        {"model": "model", "tools": "tools", "approval": "approval", "terminal": "terminal"},
    )
    builder.add_edge("tools", "model")
    builder.add_edge("approval", "terminal")
    builder.add_edge("terminal", END)
    graph = builder.compile(checkpointer=saver)  # pyright: ignore[reportUnknownMemberType]
    policies = retry_policies(graph)
    if any(policies.values()):
        raise RuntimeError(
            f"the worker runs with no retry policy; the compiled graph holds {policies}"
        )
    return graph


def _route(state: Cursor) -> str:
    return state["route"]


def retry_policies(graph: Any) -> dict[str, list[str]]:
    """The retry policies the compiled ``graph`` holds, its own and each node's, as their
    representations; every list is empty when none is set."""
    held = {"graph": [repr(policy) for policy in graph.retry_policy or ()]}
    for name, node in graph.nodes.items():
        held[name] = [repr(policy) for policy in node.retry_policy or ()]
    return held


# --- The model call --------------------------------------------------------------------------


def _model_step(harness: Harness) -> tuple[str, bool]:
    """One step of the loop: the route after it, and whether a finalization allocation was
    refused. A call in progress is continued, an answered call's reads are resolved first,
    then the system is asked for the next call or the run goes to its approval."""
    appender = harness.appender
    state = appender.state
    if state.stopped is not None:
        return "terminal", False
    if state.frozen:
        # The review payload is frozen (the ruling on recovery, part 3): the system is asked
        # nothing more, and the ending it froze toward is the request's, not this process's.
        return "approval", _at_cap(state)
    calls = calls_of(state)
    current = calls[-1] if calls else None
    if current is not None:
        standing = decide_call(current.pairs(), _table(harness), _policy(harness)).decision
        if standing is CallDecision.DISPATCH_AGAIN:
            request = harness.turns.request_for(state, current.ordinal)
            if request is None:
                raise RuntimeError(
                    f"{call_id(current.ordinal)} is in progress and the system restates no request"
                )
            return _dispatch(harness, current.ordinal, request, current)
        if standing is CallDecision.ANSWERED and _pending_reads(state, current):
            return "tools", False
        if standing in (CallDecision.FAILED_BY_INFRASTRUCTURE, CallDecision.FAILED_BY_DEFECT):
            return "terminal", False
    ordinal = len(calls) + 1
    request = harness.turns.request_for(state, ordinal)
    if request is None:
        return "approval", False
    return _dispatch(harness, ordinal, request, None)


def _dispatch(
    harness: Harness, ordinal: int, request: TurnRequest, current: CallEvents | None
) -> tuple[str, bool]:
    appender = harness.appender
    inputs = harness.inputs
    role = request.role
    configuration = inputs.configuration_of(role)
    selection = inputs.selection_of(role)
    identifier = inputs.counting_identifier_of(role)
    if configuration is None or selection is None or identifier is None:
        raise RuntimeError(f"{role!r} is not a configured role")
    digest = hashlib.sha256(canonical_bytes(request.body)).hexdigest()
    if current is not None and _intent_of(current.intents[0]).request_digest != digest:
        raise RuntimeError(
            f"the system restated {call_id(ordinal)}'s request with other bytes than its "
            f"first intent named"
        )
    # The boundary is read before a declared entry is appended: the entry is part of this
    # call, not the log below it, and appended first it hid the loop count a recovering
    # process restated past (the group's review).
    counted = restated_since_counted(appender.state, ordinal, digest)
    if counted is not None:
        raise RuntimeError(
            f"the system restated {call_id(ordinal)}'s request with other bytes than the "
            f"count {count_id(counted)!r} was asked for"
        )
    if request.final and appender.state.finalization_entered is None:
        appender.append(FinalizationEntered())
    bound = _established_bound(harness, role, identifier, digest, request.body)
    if bound is None:
        return "terminal", False
    maximum = output_maximum(configuration)
    tokens = worst_case_tokens(bound, maximum)
    money = worst_case_cost(bound.input_tokens, maximum, selection, inputs.pricing)
    state = appender.state
    purpose = call_purpose(state, ordinal)
    number = (current.last_number if current is not None else 0) + 1
    if current is not None:
        # The registered delay runs from the previous dispatch's logged outcome, or from its
        # intent when it stays unresolved, whichever process does the dispatching (the ruling
        # on re-dispatch, part 3; the worker group's review, fourth finding).
        anchor = current.last_outcome or current.intents[-1]
        _wait(harness, anchor.timestamp)
    assert inputs.reservation_pico_usd is not None
    intent = AccountIntent(call_id(ordinal), number, purpose, tokens, money)
    decision = authorize(
        state.account,
        inputs.caps,
        inputs.reservation_pico_usd,
        intent,
        finalization_entered=state.finalization_entered is not None,
    ).decision
    match decision:
        case AuthorizationDecision.AUTHORIZED:
            pass
        case AuthorizationDecision.ENTER_FINALIZATION:
            appender.append(FinalizationEntered())
            return "model", False
        case AuthorizationDecision.AT_CAP:
            return "approval", True
        case _:
            raise RuntimeError(f"the account answered {decision.value} to a request the loop built")
    appender.append(
        DispatchIntent(
            ordinal,
            number,
            role,
            digest,
            harness.client.operation,
            configuration.model_id,
            harness.client.client_region,
            request.input_reads,
            bound,
            maximum,
            tokens,
            money,
        )
    )
    sent = harness.client.send(configuration.model_id, request.body)
    attribution, _ = attribute(_table(harness), sent.observation)
    appender.append(
        DispatchOutcome(
            ordinal,
            number,
            sent.observation,
            sent.response,
            attribution,
            None,
            sent.sent_body_digest,
        )
    )
    return "model", False


def _established_bound(
    harness: Harness, role: str, identifier: str, digest: str, body: JsonObject
) -> EstablishedBound | None:
    """The bound of the request with ``digest``: a durable count under its reuse key, reused,
    else counted under the policy's retries; ``None`` when the counting group stopped the
    run, which the transition recorded."""
    appender = harness.appender
    inputs = harness.inputs
    method = inputs.caps.input_bound
    probe = CountKey(method, identifier, digest, 1)
    projection: JsonObject | None = None
    while True:
        group = count_group(appender.state, probe)
        for count in group:
            if count.outcome is None:
                continue
            outcome = count.outcome.event
            assert isinstance(outcome, CountOutcomeLogged)
            if isinstance(outcome.outcome, Counted):
                return EstablishedBound(
                    method, identifier, digest, outcome.outcome.input_tokens, count_id(count.key)
                )
        decision = count_decision(
            [count.reading() for count in group], _policy(harness).max_dispatches
        )
        if decision is not CountDecision.COUNT:
            return None
        if projection is None:
            projection = counted_projection(method, body)
        if group:
            # As for a dispatch: the delay from the previous request's outcome, or its start.
            previous = group[-1]
            _wait(harness, (previous.outcome or previous.start).timestamp)
        key = CountKey(method, identifier, digest, len(group) + 1)
        appender.append(CountStarted(key, role))
        answer = harness.counter.count(identifier, projection)
        reading = read_outcome(method, answer)
        after = appender.append(CountOutcomeLogged(key, answer, reading))
        if after.stopped is not None:
            return None


def count_boundary(state: AttemptState, ordinal: int) -> int:
    """The position below which no count belongs to logical call ``ordinal``: the later of
    the previous call's settling outcome (the outcome of its last dispatch, which a late
    outcome of an earlier dispatch never moves) and the entry into finalization; zero when
    neither is held."""
    calls = calls_of(state)
    settled = 0
    if ordinal >= 2:
        previous = calls[ordinal - 2]
        last = previous.last_outcome
        assert last is not None, "a new call follows a settled one"
        settled = last.position
    entered = state.finalization_entered or 0
    return max(settled, entered)


def restated_since_counted(state: AttemptState, ordinal: int, digest: str) -> CountKey | None:
    """The key of a count started for call ``ordinal`` under another request digest than
    ``digest``, resolved or not, or ``None``: every count above the call's boundary is the
    call's own, and one under other bytes means the system restated the request."""
    boundary = count_boundary(state, ordinal)
    for count in counts_of(state):
        if count.start.position > boundary and count.key.request_digest != digest:
            return count.key
    return None


def _wait(harness: Harness, anchor: datetime) -> None:
    """The registered delay from ``anchor``, the log's own timestamp of the previous outcome,
    measured on the log's clock and slept on the monotonic one, never longer than the delay
    itself (the ruling on re-dispatch, part 3, as the worker group amended it)."""
    delay = _policy(harness).delay_ms / 1000
    if delay <= 0:
        return
    elapsed = (harness.appender.store.now() - anchor).total_seconds()
    remaining = min(max(delay - elapsed, 0.0), delay)
    if remaining > 0:
        harness.sleep(remaining)


# --- The reads an answer asked for ----------------------------------------------------------


def _read_calls(response: Mapping[str, object]) -> tuple[ToolUse, ...]:
    """The tool calls that run a read: not the fact tool's, not one whose input is no object
    (the transition's barrier counts the same calls)."""
    if stop_reason_of(response) != TOOL_USE_STOP:
        return ()
    return tuple(
        use
        for use in tool_uses(response)
        if use.name != FACT_TOOL and isinstance(use.input, Mapping)
    )


def _answered_response(call: CallEvents) -> Mapping[str, object] | None:
    last = call.last_outcome
    if last is None:
        return None
    outcome = last.event
    assert isinstance(outcome, DispatchOutcome)
    if not isinstance(outcome.observation, CompleteResponse):
        return None
    return outcome.response


def _pending_reads(state: AttemptState, call: CallEvents) -> tuple[ToolUse, ...]:
    response = _answered_response(call)
    if response is None:
        return ()
    return tuple(
        use
        for use in _read_calls(response)
        if _held_operation(state, ModelReadKey(call.ordinal, use.id)) is None
    )


def _resolve_reads(harness: Harness) -> None:
    appender = harness.appender
    call = calls_of(appender.state)[-1]
    response = _answered_response(call)
    assert response is not None, "the tools node follows an answered call"
    # The role's surface, not the harness's: a known tool the role is not shown is refused at
    # execution (the registry step, fork 9), and a refusal precedes the stop check, so such a
    # call against a stopped source is refused rather than skipped.
    surface = role_surface(Role(call.role))
    executor = LoggedExecutor(
        harness,
        replaying=lambda key: isinstance(key, ModelReadKey) and key.call == call.ordinal,
        surface=surface,
    )
    origin = ModelOrigin(call_id(call.ordinal))
    for use in _read_calls(response):
        key = ModelReadKey(call.ordinal, use.id)
        held = _held_operation(appender.state, key)
        if isinstance(held, OperationSkip):
            continue
        if held is None:
            specification = specification_named(use.name, surface)
            if specification is not None and specification.facts.source in executor.stopped:
                appender.append(
                    OperationEvent(key, OperationSkip(UndispatchedReason.SOURCE_UNREACHABLE))
                )
                continue
        # A held result goes through the executor too: it is replayed, not made, and the
        # stop it carries reaches the reads after it (the second read's second finding).
        arguments = cast("Mapping[str, object]", use.input)
        executor.resolve(key, origin, use.name, arguments)
        if appender.state.stopped is not None:
            # A malformed record's stop or a derived defect's: the transition recorded it on
            # the append, and no later read of the answer reaches a port.
            return


# --- Small readers ---------------------------------------------------------------------------


def _table(harness: Harness) -> AttributionTable:
    table = harness.appender.rules.table
    assert table is not None, "a model-calling run registers an attribution table"
    return table


def _policy(harness: Harness) -> RedispatchPolicy:
    policy = harness.appender.rules.redispatch
    assert policy is not None, "a model-calling run registers a re-dispatch policy"
    return policy


def _at_cap(state: AttemptState) -> bool:
    """The ending the held approval request froze toward, read from the log."""
    request = state.approval_requested
    assert request is not None and isinstance(request.event, ApprovalRequested)
    return request.event.at_cap


def _intent_of(logged: LoggedEvent) -> DispatchIntent:
    event = logged.event
    assert isinstance(event, DispatchIntent)
    return event


__all__ = [
    "DURABILITY",
    "INITIAL",
    "Cursor",
    "Harness",
    "LoggedExecutor",
    "ModelClient",
    "ReviewPayload",
    "TokenCounter",
    "TurnRequest",
    "Turns",
    "build",
    "count_boundary",
    "restated_since_counted",
    "retry_policies",
]
