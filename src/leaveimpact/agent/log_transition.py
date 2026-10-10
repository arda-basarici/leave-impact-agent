"""The transition function: the legal next events of an attempt's log, and the state it folds to.

Unique keys do not prevent two terminal events under two keys, a resume with no accepted
approval, or work after a segment end: one pure function takes the attempt's state and an
event and gives the next state, an idempotent receipt, or a refusal (the event log step's
ruling on the event, part 8). The store runs it under the attempt's lock against the state
on the row before every insert, and the log reader folds it over the whole log before it
builds an export, so the rules are written once and nowhere as a database constraint.

What the function refuses, by the rulings it enforces:

- *ownership and segments* (one writer; the event, part 6): a worker's event is appended
  only under the current generation, in the segment that generation opened, while that
  segment has not ended, at an offset not below the segment's last; a claim opens the next
  segment under the next generation, always, since a claim always wins; a terminal event
  ends its segment; a closed attempt rejects every later append;
- *idempotence* (the event, part 5): an event equal in kind, key and canonical content to one
  the log holds is received at the held position and makes no transition; another content
  under a held key is refused;
- *the registered values* (group 4's first fork): the attribution table and the re-dispatch
  policy are taken from the caller and refused when they differ from what the admission
  froze, so no rule below is read against values the run did not register;
- *the dispatch rules* (the ledger, parts 1 and 4; re-dispatch, parts 1 and 2; counting,
  parts 13 and 15; group 1's review; the graph step's review): a dispatch intent is numbered
  next, opens a new call only after the last one is settled, rests on a durable count that
  counted this request, names reads the log holds, carries the registered configuration's
  output maximum and the worst case the registered rules give, follows a dispatch only when
  the within-call decision permits another, and is authorized by the run's account under
  the purpose the call holds, or the log's phase for a new one; a count is started only
  when the group's decision is to count;
- *the freeze and the stop* (recovery and endings, parts 1 to 3; counting, part 14; group
  3's second fork): after an approval was requested no model intent, no count and no tool
  resolution is appended; after a stopping failure is recorded (a malformed record, a
  defect the conclusion derives from the operations held, at the operation that
  established it (the graph step's rulings, amendment 1: a source contradicting itself,
  the leaver absent from the enumeration, a record no fact can be made from), a
  dispatch read as a defect, a call that stands failed by infrastructure, a count group
  refused, exhausted or failed in an unclassified way) nothing but segment bookkeeping, an
  approval already requested and the closing event is, an outcome arriving for a count or
  a dispatch still in flight included (its evidence is not logged and the reservation keeps
  that dispatch as unresolved, the shape ruling 1 part 5 gives a fenced worker's dispatch;
  the store group's review), and a worker's closing failure names that failure at its site
  in its category; a dispatch's bound is the number its count returned;
- *the commit* (recovery and endings, part 6): a claim on another commit than the first
  segment's is refused unless it records an override naming its authority and both commits;
- *the approval* (the event, part 8; the job seam, part 1): one request, one approval over
  the request's digest, one resume after it; a completion only after the resume;
- *closure* (one writer, part 7): an abandonment names the current generation.

The state is public, since the worker authorizes and recovers from it and the reader reads
it: the frozen inputs, the events so far, the generation, the segments with their last
offsets, the closing event, the approval's progress, the finalization position, the
account's fold and the first stopping failure. The per-call and per-count views are
projections over the events (``calls_of``, ``counts_of``, ``operations_of``), computed
where needed rather than kept, so no two fields can disagree.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from leaveimpact.agent.answer_parse import (
    FACT_TOOL,
    reported_usage,
    stop_reason_of,
    tool_uses,
)
from leaveimpact.agent.conclusion import defect_of, leave_of
from leaveimpact.agent.log_events import (
    Abandoned,
    Admitted,
    ApprovalRequested,
    Approved,
    CapExhausted,
    ClosingEvent,
    Completed,
    CountKey,
    CountOutcomeLogged,
    CountStarted,
    DispatchIntent,
    DispatchOutcome,
    EventKey,
    Failed,
    FinalizationEntered,
    FrozenInputs,
    HarnessReadKey,
    LoggedEvent,
    ModelReadKey,
    OperationEvent,
    OperationResult,
    PrefetchKey,
    Resumed,
    SegmentEnded,
    SegmentStarted,
    WorkerStamp,
    call_id,
    count_id,
    event_bytes,
    event_key,
    kind_of,
    operation_id,
)
from leaveimpact.core.attribution import (
    AttributionTable,
    RedispatchPolicy,
    attribution_table_digest,
)
from leaveimpact.core.call_decision import CallDecision, decide_call
from leaveimpact.core.counting_operations import Counted, read_outcome
from leaveimpact.core.input_bound import (
    CountDecision,
    CountResult,
    RegisteredInputBound,
    count_decision,
    output_maximum,
    worst_case_tokens,
)
from leaveimpact.core.model_calls import (
    TOOL_USE_STOP,
    UNRESOLVED_RULE,
    Attribution,
    AttributionKind,
    CompleteResponse,
    NoRecordedOutcome,
    Observation,
    RefusedBeforeSend,
)
from leaveimpact.core.pricing import absent_as_zero, cost_of_reported, worst_case_cost
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.run_account import (
    AccountIntent,
    AccountOutcome,
    AuthorizationDecision,
    CallPurpose,
    RunAccount,
    authorize,
)
from leaveimpact.core.run_ending import (
    DispatchPhase,
    DispatchSite,
    FailureSite,
    HarnessSite,
    InputBoundSite,
    OperationSite,
)
from leaveimpact.core.run_parts_json import review_payload_digest
from leaveimpact.core.run_record import HARNESS_READ_POLICIES, Failure, FailureCategory
from leaveimpact.core.run_timing import HarnessRevision
from leaveimpact.core.run_trace import (
    Cost,
    DefectOutcome,
    HarnessOrigin,
    ModelOrigin,
    Operation,
    Origin,
    PrefetchOrigin,
)
from leaveimpact.core.token_counting import count_tokens

# --- The registered values and the state ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rules:
    """The registration's values the transition function reads and the admission froze by
    digest or by value: the attribution table and the re-dispatch policy, each ``None`` for
    a system that calls no model. The count-retry maximum is the policy's, under the one
    registered count-retry rule."""

    table: AttributionTable | None
    redispatch: RedispatchPolicy | None


@dataclass(frozen=True, slots=True)
class SegmentState:
    """One segment as the log shows it: its revision, the largest offset among its events,
    and whether it ended (a segment end or a terminal event)."""

    number: int
    harness: HarnessRevision
    last_offset_ms: int
    ended: bool


@dataclass(frozen=True, slots=True)
class CallEvents:
    """One logical call's events: its intents in number order, and the outcome of each
    dispatch that recorded one, by number."""

    ordinal: int
    intents: tuple[LoggedEvent, ...]
    outcomes: Mapping[int, LoggedEvent]

    @property
    def role(self) -> str:
        return _intent(self.intents[0]).role

    @property
    def last_number(self) -> int:
        return len(self.intents)

    def pairs(self) -> tuple[tuple[Observation, Attribution], ...]:
        """What each dispatch observed and how it was read, for the within-call decision."""
        pairs: list[tuple[Observation, Attribution]] = []
        for intent in self.intents:
            number = _intent(intent).number
            outcome = self.outcomes.get(number)
            if outcome is None:
                pairs.append(
                    (NoRecordedOutcome(), Attribution(AttributionKind.UNRESOLVED, UNRESOLVED_RULE))
                )
            else:
                held = _outcome(outcome)
                pairs.append((held.observation, held.attribution))
        return tuple(pairs)

    @property
    def last_outcome(self) -> LoggedEvent | None:
        return self.outcomes.get(self.last_number)


@dataclass(frozen=True, slots=True)
class CountEvents:
    """One counting request's events: its start, and its outcome when one was recorded."""

    key: CountKey
    start: LoggedEvent
    outcome: LoggedEvent | None

    def reading(self) -> CountResult:
        """The method's reading of the outcome, re-read; unresolved with no outcome."""
        if self.outcome is None:
            return CountResult.UNRESOLVED
        return read_outcome(self.key.method, _count_outcome(self.outcome).outcome)


@dataclass(frozen=True, slots=True)
class AttemptState:
    """The attempt as its log so far shows it; see the module."""

    events: tuple[LoggedEvent, ...] = ()
    inputs: FrozenInputs | None = None
    generation: int = 0
    segments: tuple[SegmentState, ...] = ()
    closed: LoggedEvent | None = None
    finalization_entered: int | None = None
    approval_requested: LoggedEvent | None = None
    approved: LoggedEvent | None = None
    resumed: LoggedEvent | None = None
    account: RunAccount = RunAccount()
    stopped: Failure | None = None

    @property
    def last_position(self) -> int:
        return len(self.events)

    @property
    def open(self) -> bool:
        return self.inputs is not None and self.closed is None

    @property
    def current_segment(self) -> SegmentState | None:
        """The segment the current generation opened, ended or not; ``None`` before a claim."""
        return self.segments[-1] if self.segments else None

    @property
    def closing(self) -> ClosingEvent | None:
        if self.closed is None:
            return None
        event = self.closed.event
        assert isinstance(event, Completed | CapExhausted | Failed | Abandoned)
        return event

    @property
    def frozen(self) -> bool:
        """Whether an approval was requested, after which the review payload is frozen."""
        return self.approval_requested is not None


# --- The results -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Appended:
    """The event is legal next: the state after it."""

    state: AttemptState


@dataclass(frozen=True, slots=True)
class Received:
    """The event equals one the log holds: its first position, and no transition."""

    position: int


@dataclass(frozen=True, slots=True)
class Refused:
    """No log holds this event after this prefix, and why."""

    reason: str


type Transition = Appended | Received | Refused


# --- Projections -----------------------------------------------------------------------------


def calls_of(state: AttemptState) -> tuple[CallEvents, ...]:
    """The logical calls in ordinal order."""
    intents: dict[int, list[LoggedEvent]] = {}
    outcomes: dict[int, dict[int, LoggedEvent]] = {}
    for logged in state.events:
        event = logged.event
        if isinstance(event, DispatchIntent):
            intents.setdefault(event.call, []).append(logged)
        elif isinstance(event, DispatchOutcome):
            outcomes.setdefault(event.call, {})[event.number] = logged
    return tuple(
        CallEvents(ordinal, tuple(held), outcomes.get(ordinal, {}))
        for ordinal, held in sorted(intents.items())
    )


def call_of(state: AttemptState, ordinal: int) -> CallEvents | None:
    for call in calls_of(state):
        if call.ordinal == ordinal:
            return call
    return None


def counts_of(state: AttemptState) -> tuple[CountEvents, ...]:
    """The counting requests in start order."""
    starts: dict[CountKey, LoggedEvent] = {}
    outcomes: dict[CountKey, LoggedEvent] = {}
    for logged in state.events:
        event = logged.event
        if isinstance(event, CountStarted):
            starts[event.key] = logged
        elif isinstance(event, CountOutcomeLogged):
            outcomes[event.key] = logged
    return tuple(CountEvents(key, start, outcomes.get(key)) for key, start in starts.items())


def count_group(state: AttemptState, key: CountKey) -> tuple[CountEvents, ...]:
    """The counting requests under ``key``'s reuse key, in ordinal order."""
    return tuple(count for count in counts_of(state) if count.key.reuse == key.reuse)


def operations_of(state: AttemptState) -> tuple[LoggedEvent, ...]:
    """The operation events in position order, results and skips."""
    return tuple(logged for logged in state.events if isinstance(logged.event, OperationEvent))


def results_of(state: AttemptState) -> tuple[LoggedEvent, ...]:
    """The operation events that hold a result."""
    return tuple(
        logged
        for logged in operations_of(state)
        if isinstance(_operation(logged).resolution, OperationResult)
    )


def held_operation_ids(state: AttemptState) -> frozenset[str]:
    return frozenset(operation_id(_operation(logged).key) for logged in results_of(state))


# --- The function ----------------------------------------------------------------------------


def next_state(state: AttemptState, logged: LoggedEvent, rules: Rules) -> Transition:
    """What appending ``logged`` after ``state`` gives, under the registered ``rules``."""
    inputs = state.inputs
    if inputs is None:
        return _admit(state, logged)
    held = _held_under(state, event_key(logged))
    if held is not None:
        if event_bytes(held.event) == event_bytes(logged.event):
            return Received(held.position)
        return Refused(
            f"another content under the identifier of the event at position {held.position}"
        )
    if logged.position != state.last_position + 1:
        return Refused(
            f"positions are dense: the next is {state.last_position + 1}, got {logged.position}"
        )
    if state.closed is not None:
        return Refused(f"the attempt is closed at position {state.closed.position}")
    mismatch = rules_differ(inputs, rules)
    if mismatch is not None:
        return Refused(mismatch)
    event = logged.event
    if isinstance(event, Admitted):
        return Refused("an attempt is admitted once")
    stamp = logged.stamp
    if isinstance(event, SegmentStarted):
        assert stamp is not None
        return _claim(state, logged, stamp, event, rules)
    if stamp is not None:
        refusal = _stamp_refusal(state, stamp)
        if refusal is not None:
            return Refused(refusal)
    match event:
        case SegmentEnded():
            return Appended(_with_segment(state, logged, ended=True))
        case OperationEvent():
            return _operation_next(state, logged, event)
        case CountStarted():
            return _count_start(state, logged, event, rules)
        case CountOutcomeLogged():
            return _count_outcome_next(state, logged, event, rules)
        case DispatchIntent():
            return _intent_next(state, logged, event, rules)
        case DispatchOutcome():
            return _outcome_next(state, logged, event, rules)
        case FinalizationEntered():
            if state.finalization_entered is not None:
                return Refused("the run entered finalization once")
            if state.frozen:
                return Refused("no finalization after an approval was requested")
            if state.stopped is not None:
                return Refused(_stopped(state, "no finalization"))
            return Appended(
                replace(_with_segment(state, logged), finalization_entered=logged.position)
            )
        case ApprovalRequested():
            if state.frozen:
                return Refused("an approval is requested once")
            if state.stopped is not None:
                return Refused(_stopped(state, "no approval request"))
            return Appended(replace(_with_segment(state, logged), approval_requested=logged))
        case Approved():
            request = state.approval_requested
            if request is None:
                return Refused("an approval answers a request")
            if state.approved is not None:
                return Refused("an approval is given once")
            asked = _request(request)
            if event.payload_digest != review_payload_digest(asked.claims, asked.composition):
                return Refused("an approval names the digest of the payload that was requested")
            return Appended(replace(_with_event(state, logged), approved=logged))
        case Resumed():
            if state.approved is None:
                return Refused("a worker resumes after an approval was given")
            if state.resumed is not None:
                return Refused("a worker resumes once")
            if state.stopped is not None:
                return Refused(_stopped(state, "no resume"))
            return Appended(replace(_with_segment(state, logged), resumed=logged))
        case Completed() | CapExhausted():
            if state.resumed is None:
                return Refused("a completion follows the resume from an approval")
            if state.stopped is not None:
                return Refused(_stopped(state, "no completion"))
            assert state.approval_requested is not None
            if _request(state.approval_requested).at_cap != isinstance(event, CapExhausted):
                return Refused(
                    "the closing event names the ending the approval request froze toward: "
                    + ("the cap" if isinstance(event, Completed) else "a completion")
                )
            refusal = _settlement_refusal(inputs, event.settlement is not None)
            if refusal is not None:
                return Refused(refusal)
            return Appended(_close(_with_segment(state, logged, ended=True), logged))
        case Failed():
            refusal = _failure_refusal(state, event) or _settlement_refusal(
                inputs, event.settlement is not None
            )
            if refusal is not None:
                return Refused(refusal)
            return Appended(_close(_with_segment(state, logged, ended=True), logged))
        case Abandoned():
            if event.expected_generation != state.generation:
                return Refused(
                    f"the abandon command expects generation {event.expected_generation}; "
                    f"the attempt is at {state.generation}"
                )
            refusal = _settlement_refusal(inputs, event.settlement is not None)
            if refusal is not None:
                return Refused(refusal)
            return Appended(_close(_with_event(state, logged), logged))
        case _:
            return Refused(f"no rule admits {kind_of(event).value} here")


def fold(events: Iterable[LoggedEvent], rules: Rules) -> AttemptState:
    """The state of a log, folded from empty; ``ValueError`` at the first event no log
    holds, naming its position and the reason, or at a duplicate, which a stored log never
    holds."""
    state = AttemptState()
    for logged in events:
        match next_state(state, logged, rules):
            case Appended(after):
                state = after
            case Received(position):
                raise ValueError(
                    f"the event at position {logged.position} repeats the one at {position}"
                )
            case Refused(reason):
                raise ValueError(f"no log holds the event at position {logged.position}: {reason}")
    return state


# --- The admission and the claim -------------------------------------------------------------


def _admit(state: AttemptState, logged: LoggedEvent) -> Transition:
    event = logged.event
    if not isinstance(event, Admitted):
        return Refused("the first event is the admission")
    if logged.position != 1:
        return Refused(f"the admission is at position 1, got {logged.position}")
    return Appended(AttemptState(events=(logged,), inputs=event.inputs))


def _claim(
    state: AttemptState,
    logged: LoggedEvent,
    stamp: WorkerStamp,
    event: SegmentStarted,
    rules: Rules,
) -> Transition:
    number = len(state.segments) + 1
    if stamp.segment != number or stamp.generation != number:
        return Refused(
            f"a claim opens segment {number} under generation {number}, got segment "
            f"{stamp.segment} under generation {stamp.generation}"
        )
    if stamp.offset_ms != 0:
        return Refused("a segment starts at offset 0")
    if state.segments:
        first = state.segments[0].harness.commit
        override = event.override
        if event.harness.commit != first and override is None:
            return Refused(
                f"a claim on commit {event.harness.commit[:12]} needs an override; the first "
                f"segment ran {first[:12]}"
            )
        if override is not None and override.from_commit != first:
            return Refused(
                f"the override names {override.from_commit[:12]} as the first segment's commit, "
                f"which is {first[:12]}"
            )
    opened = SegmentState(number, event.harness, 0, False)
    after = replace(
        state,
        events=(*state.events, logged),
        generation=number,
        segments=(*state.segments, opened),
    )
    stop = _dead_segment_stop(after, rules)
    return Appended(after if stop is None else _stop(after, stop))


def _stamp_refusal(state: AttemptState, stamp: WorkerStamp) -> str | None:
    current = state.current_segment
    if current is None:
        return "no worker has claimed the attempt"
    if stamp.generation != state.generation:
        return f"generation {stamp.generation} is not the current {state.generation}"
    if stamp.segment != current.number:
        return f"segment {stamp.segment} is not the current {current.number}"
    if current.ended:
        return f"segment {current.number} has ended"
    if stamp.offset_ms < current.last_offset_ms:
        return f"offset {stamp.offset_ms} is below the segment's last {current.last_offset_ms}"
    return None


# --- Operations ------------------------------------------------------------------------------


def _operation_next(state: AttemptState, logged: LoggedEvent, event: OperationEvent) -> Transition:
    if state.stopped is not None:
        return Refused(_stopped(state, "no tool resolution"))
    if state.frozen:
        return Refused("no tool resolution after an approval was requested")
    key = event.key
    match key:
        case PrefetchKey():
            expected = (
                sum(isinstance(_operation(o).key, PrefetchKey) for o in operations_of(state)) + 1
            )
            if key.ordinal != expected:
                return Refused(f"the prefetch's next call is {expected}, got {key.ordinal}")
        case HarnessReadKey():
            expected = (
                sum(
                    isinstance(k := _operation(o).key, HarnessReadKey) and k.policy == key.policy
                    for o in operations_of(state)
                )
                + 1
            )
            if key.ordinal != expected:
                return Refused(f"{key.policy}'s next read is {expected}, got {key.ordinal}")
            # The baselines step, fork 4: a harness read is the admitted system's preparation,
            # under a policy that system issues and before its first model call.
            inputs = state.inputs
            assert inputs is not None, "an operation follows an admission"
            if key.policy not in HARNESS_READ_POLICIES[inputs.system.kind]:
                return Refused(
                    f"{inputs.system.kind.value} issues no harness read under {key.policy!r}"
                )
            if calls_of(state):
                return Refused("a harness read precedes the first model call")
        case ModelReadKey():
            refusal = _model_read_refusal(state, key, event)
            if refusal is not None:
                return Refused(refusal)
    after = _with_segment(state, logged)
    resolution = event.resolution
    if isinstance(resolution, OperationResult) and isinstance(resolution.outcome, DefectOutcome):
        after = _stop(
            after,
            Failure(FailureCategory.DEFECT, OperationSite(operation_id(key)), "a malformed record"),
        )
    if after.stopped is None:
        # The conclusion over the operations held so far: a defect it derives is a stop at
        # the operation that established it, so recovery, the reader and an outside
        # closure see the same ending (the graph step's rulings, amendment 1).
        derived = derived_defect(after)
        if derived is not None:
            after = _stop(after, derived)
    return Appended(after)


def derived_defect(state: AttemptState) -> Failure | None:
    """The defect the conclusion derives from the operations ``state`` holds, or ``None``:
    the same function the baseline and the review payload ask, over the trace's view of
    the log."""
    inputs = state.inputs
    assert inputs is not None
    operations = trace_operations(state)
    projection = project_reads(operations, inputs.context.today)
    return defect_of(operations, projection, inputs.context, leave_of(operations, inputs.context))


def trace_operations(state: AttemptState) -> tuple[Operation, ...]:
    """Every operation the log holds a result for, as the trace holds it, in position order;
    a skip is no operation."""
    return tuple(
        _trace_operation(logged)
        for logged in operations_of(state)
        if isinstance(_operation(logged).resolution, OperationResult)
    )


def _trace_operation(logged: LoggedEvent) -> Operation:
    event = _operation(logged)
    result = event.resolution
    assert isinstance(result, OperationResult)
    return Operation(
        operation_id(event.key),
        _origin_of(event.key),
        result.tool,
        result.source,
        result.arguments,
        result.outcome,
        logged.position,
    )


def _origin_of(key: PrefetchKey | ModelReadKey | HarnessReadKey) -> Origin:
    match key:
        case PrefetchKey():
            return PrefetchOrigin()
        case ModelReadKey():
            return ModelOrigin(call_id(key.call))
        case HarnessReadKey():
            return HarnessOrigin(key.policy)


def _model_read_refusal(
    state: AttemptState, key: ModelReadKey, event: OperationEvent
) -> str | None:
    call = call_of(state, key.call)
    if call is None:
        return f"no call {key.call} to answer a read for"
    last = call.last_outcome
    if last is None or not isinstance(_outcome(last).observation, CompleteResponse):
        return f"{call_id(key.call)} has no complete response to read for"
    response = _outcome(last).response
    assert response is not None
    if stop_reason_of(response) != TOOL_USE_STOP:
        return f"{call_id(key.call)} stopped for {stop_reason_of(response)!r}; no read is made"
    # The barrier holds between calls that execute or are skipped: a fact tool's call is
    # handled by the harness and an unparsed call runs nothing, so neither is resolved.
    uses = [
        use
        for use in tool_uses(response)
        if use.name != FACT_TOOL and isinstance(use.input, Mapping)
    ]
    asked = {use.id: use for use in uses}
    if key.tool_call not in asked:
        return f"{call_id(key.call)} made no tool call {key.tool_call!r}"
    resolved: set[str] = set()
    for held in operations_of(state):
        held_key = _operation(held).key
        if isinstance(held_key, ModelReadKey) and held_key.call == key.call:
            resolved.add(held_key.tool_call)
    for use in uses:
        if use.id == key.tool_call:
            break
        if use.id not in resolved:
            return f"tool call {use.id!r} of {call_id(key.call)} is resolved first"
    resolution = event.resolution
    if isinstance(resolution, OperationResult) and resolution.tool != asked[key.tool_call].name:
        return (
            f"tool call {key.tool_call!r} asked for {asked[key.tool_call].name!r}, the result "
            f"names {resolution.tool!r}"
        )
    return None


# --- Counts ----------------------------------------------------------------------------------


def _count_start(
    state: AttemptState, logged: LoggedEvent, event: CountStarted, rules: Rules
) -> Transition:
    inputs = state.inputs
    assert inputs is not None
    if state.stopped is not None:
        return Refused(_stopped(state, "no counting request"))
    if state.frozen:
        return Refused("no counting request after an approval was requested")
    if rules.redispatch is None:
        return Refused("a counting request is bounded by the re-dispatch policy, which is absent")
    identifier = inputs.counting_identifier_of(event.role)
    if identifier is None:
        return Refused(f"{event.role!r} is not a configured role")
    key = event.key
    if key.method != inputs.caps.input_bound:
        return Refused("a count is asked under the registered method")
    if key.counting_identifier != identifier:
        return Refused(
            f"{event.role}'s counting identifier is {identifier!r}, got {key.counting_identifier!r}"
        )
    group = count_group(state, key)
    if key.ordinal != len(group) + 1:
        return Refused(f"the next counting request for this request is {len(group) + 1}")
    decision = count_decision([count.reading() for count in group], rules.redispatch.max_dispatches)
    if decision is not CountDecision.COUNT:
        return Refused(f"the decision for this request is {decision.value}, not to count")
    return Appended(_with_segment(state, logged))


def _count_outcome_next(
    state: AttemptState, logged: LoggedEvent, event: CountOutcomeLogged, rules: Rules
) -> Transition:
    if state.stopped is not None:
        return Refused(_stopped(state, "no count outcome"))
    held = next((count for count in counts_of(state) if count.key == event.key), None)
    if held is None:
        return Refused("a count outcome follows its start")
    if held.outcome is not None:
        return Refused("a counting request has one outcome")
    start_stamp = held.start.stamp
    stamp = logged.stamp
    assert start_stamp is not None and stamp is not None
    if start_stamp.segment != stamp.segment:
        return Refused("a count's outcome is recorded by the segment that started it")
    if (event.reading is CountResult.COUNTED) != isinstance(event.outcome, Counted):
        return Refused("a counting operation is read as counted exactly when a count arrived")
    after = _with_segment(state, logged)
    assert rules.redispatch is not None
    group = count_group(after, event.key)
    stop = _count_stop(group, rules.redispatch.max_dispatches)
    return Appended(after if stop is None else _stop(after, stop))


# --- Dispatches ------------------------------------------------------------------------------


def _intent_next(
    state: AttemptState, logged: LoggedEvent, event: DispatchIntent, rules: Rules
) -> Transition:
    inputs = state.inputs
    assert inputs is not None
    if state.stopped is not None:
        return Refused(_stopped(state, "no dispatch"))
    if state.frozen:
        return Refused("no dispatch after an approval was requested")
    if rules.table is None or rules.redispatch is None or inputs.reservation_pico_usd is None:
        return Refused("a dispatch needs the attribution table, the policy and a reservation")
    configuration = inputs.configuration_of(event.role)
    selection = inputs.selection_of(event.role)
    if configuration is None or selection is None:
        return Refused(f"{event.role!r} is not a configured role")
    calls = calls_of(state)
    call = call_of(state, event.call)
    if call is None:
        if event.call != len(calls) + 1:
            return Refused(f"the next logical call is {len(calls) + 1}, got {event.call}")
        if event.number != 1:
            return Refused("a new call's first dispatch is numbered 1")
        if calls:
            # A new call follows a settled one, so a call's ordinal order is its outcome
            # order and every reader of the log may rely on it (the graph step's review).
            # The condition is the positive one: a call exhausted by unresolved dispatches
            # stands failed with no stop recorded, and admits no new call either (the
            # review's second read).
            last = calls[-1]
            standing = decide_call(last.pairs(), rules.table, rules.redispatch).decision
            if standing not in (CallDecision.ANSWERED, CallDecision.ENDED_AS_BEHAVIOUR):
                return Refused(f"{call_id(last.ordinal)} stands {standing.value}: no new call")
    else:
        if event.number != call.last_number + 1:
            return Refused(f"{call_id(event.call)}'s next dispatch is {call.last_number + 1}")
        if call.role != event.role:
            return Refused(f"{call_id(event.call)} is {call.role}'s")
        standing = decide_call(call.pairs(), rules.table, rules.redispatch)
        if standing.decision is not CallDecision.DISPATCH_AGAIN:
            return Refused(f"{call_id(event.call)} stands {standing.decision.value}")
    refusal = _bound_refusal(state, event)
    if refusal is not None:
        return Refused(refusal)
    held = held_operation_ids(state)
    for read in event.input_reads:
        if read not in held:
            return Refused(f"the input read {read!r} is not an operation the log holds")
    maximum = output_maximum(configuration)
    if event.output_maximum != maximum:
        return Refused(f"{event.role}'s output maximum is {maximum}, got {event.output_maximum}")
    tokens = worst_case_tokens(event.bound, maximum)
    money = worst_case_cost(event.bound.input_tokens, maximum, selection, inputs.pricing)
    if (event.allocation_tokens, event.allocation_pico_usd) != (tokens, money):
        return Refused(
            f"the worst case is {tokens} tokens and {money} pico-dollars, got "
            f"{event.allocation_tokens} and {event.allocation_pico_usd}"
        )
    entered = state.finalization_entered is not None
    purpose = call_purpose(state, event.call)
    intent = AccountIntent(call_id(event.call), event.number, purpose, tokens, money)
    decision = authorize(
        state.account,
        inputs.caps,
        inputs.reservation_pico_usd,
        intent,
        finalization_entered=entered,
    )
    if decision.decision is not AuthorizationDecision.AUTHORIZED:
        return Refused(f"the account does not authorize the dispatch: {decision.decision.value}")
    return Appended(replace(_with_segment(state, logged), account=state.account.after(intent)))


def call_purpose(state: AttemptState, call: int) -> CallPurpose:
    """The purpose a dispatch of logical call ``call`` is authorized under: the one the
    call already holds, else the phase the log is in (a call opened after the entry into
    finalization is the finalization call). A call keeps its first purpose across the
    entry, and its re-dispatch is then measured against the whole caps (amendment 2)."""
    held = state.account.purpose_of(call_id(call))
    if held is not None:
        return held
    return CallPurpose.LOOP if state.finalization_entered is None else CallPurpose.FINALIZATION


def _bound_refusal(state: AttemptState, event: DispatchIntent) -> str | None:
    bound = event.bound
    if bound.request_digest != event.request_digest:
        return "the bound covers another request than the dispatch's"
    for count in counts_of(state):
        if count_id(count.key) != bound.evidence:
            continue
        if count.outcome is None:
            return f"the count {bound.evidence!r} did not count"
        counted = _count_outcome(count.outcome).outcome
        if not isinstance(counted, Counted):
            return f"the count {bound.evidence!r} did not count"
        if not bound.covers(
            count.key.method, count.key.counting_identifier, count.key.request_digest
        ):
            return f"the count {bound.evidence!r} covers another request, identifier or method"
        if bound.input_tokens != counted.input_tokens:
            return (
                f"the count {bound.evidence!r} returned {counted.input_tokens}; the bound claims "
                f"{bound.input_tokens}"
            )
        return None
    return f"the bound rests on {bound.evidence!r}, which the log does not hold"


def _outcome_next(
    state: AttemptState, logged: LoggedEvent, event: DispatchOutcome, rules: Rules
) -> Transition:
    inputs = state.inputs
    assert inputs is not None and rules.table is not None
    if state.stopped is not None:
        return Refused(_stopped(state, "no dispatch outcome"))
    call = call_of(state, event.call)
    if call is None or event.number > call.last_number:
        return Refused("a dispatch outcome follows its intent")
    if event.number in call.outcomes:
        return Refused("a dispatch has one outcome")
    intent = call.intents[event.number - 1]
    intent_stamp, stamp = intent.stamp, logged.stamp
    assert intent_stamp is not None and stamp is not None
    if intent_stamp.segment != stamp.segment:
        return Refused("a dispatch's outcome is recorded by the segment that authorized it")
    if (event.response is not None) != isinstance(event.observation, CompleteResponse):
        return Refused("a response body is held exactly for a complete response")
    row = rules.table.row(event.attribution.rule)
    if row is None or row.reading is not event.attribution.kind:
        return Refused(
            f"the table has no row {event.attribution.rule!r} reading "
            f"{event.attribution.kind.value}"
        )
    role = _intent(intent).role
    selection = inputs.selection_of(role)
    assert selection is not None
    usage = None if event.response is None else reported_usage(event.response)
    sent = not isinstance(event.observation, RefusedBeforeSend)
    if event.zero_cost_rule is not None:
        if usage is not None:
            return Refused("a zero-cost rule prices a send that reported no usage")
        cost, tokens = Cost(0, True), None
    elif usage is not None:
        cost = cost_of_reported(usage, selection, inputs.pricing)
        tokens = count_tokens(
            inputs.caps.counting_rule, usage, absent_as_zero(selection, inputs.pricing)
        )
    else:
        cost, tokens = None, None
    outcome = AccountOutcome(call_id(event.call), event.number, sent, cost, tokens)
    after = replace(_with_segment(state, logged), account=state.account.after(outcome))
    held = call_of(after, event.call)
    assert held is not None and rules.redispatch is not None
    stop = _call_stop(held, rules.table, rules.redispatch)
    return Appended(after if stop is None else _stop(after, stop))


# --- Closure ---------------------------------------------------------------------------------


def _failure_refusal(state: AttemptState, event: Failed) -> str | None:
    stopped = state.stopped
    if stopped is not None and (event.category, event.site) != (stopped.category, stopped.site):
        return _stopped(state, "a worker's closing failure names it")
    site = event.site
    match site:
        case OperationSite():
            if site.operation not in held_operation_ids(state):
                return f"no operation {site.operation!r} to fail at"
        case DispatchSite():
            call = call_of(state, _ordinal_of(site.model_call))
            if call is None or site.dispatch > call.last_number:
                return f"no dispatch {site.dispatch} of {site.model_call} to fail at"
        case InputBoundSite():
            if site.counting_operation not in {count_id(c.key) for c in counts_of(state)}:
                return f"no counting operation {site.counting_operation!r} to fail at"
        case HarnessSite():
            pass
    return None


def _settlement_refusal(inputs: FrozenInputs, settled: bool) -> str | None:
    if settled != (inputs.reservation_pico_usd is not None):
        return "a closing event settles exactly when a reservation was admitted"
    return None


def _close(state: AttemptState, logged: LoggedEvent) -> AttemptState:
    return replace(state, closed=logged)


# --- The stop --------------------------------------------------------------------------------


def _stop(state: AttemptState, failure: Failure) -> AttemptState:
    """``state`` with ``failure`` as its recorded stopping failure, unless one is held."""
    return state if state.stopped is not None else replace(state, stopped=failure)


def _stopped(state: AttemptState, what: str) -> str:
    stopped = state.stopped
    assert stopped is not None
    return (
        f"a recorded {stopped.category.value} at {_site_name(stopped.site)} is the ending: {what}"
    )


def _count_stop(group: tuple[CountEvents, ...], maximum: int) -> Failure | None:
    """The stopping failure a count group holds, by its re-read readings: a refusal is a
    defect, an unclassified failure or an exhausted maximum is infrastructure, each at the
    group's last count."""
    decision = count_decision([count.reading() for count in group], maximum)
    site = InputBoundSite(count_id(group[-1].key))
    match decision:
        case CountDecision.DEFECT:
            return Failure(
                FailureCategory.DEFECT,
                site,
                "the counting request was refused as a misconfiguration",
            )
        case CountDecision.UNCLASSIFIED:
            return Failure(
                FailureCategory.INFRASTRUCTURE,
                site,
                "the counting request failed in a way the method does not classify",
            )
        case CountDecision.EXHAUSTED:
            return Failure(
                FailureCategory.INFRASTRUCTURE,
                site,
                "the counting requests were exhausted without a count",
            )
        case _:
            return None


def _call_stop(
    call: CallEvents, table: AttributionTable | None, policy: RedispatchPolicy
) -> Failure | None:
    """The stopping failure a call holds: its standing failed by defect or by infrastructure,
    at its last dispatch's send."""
    assert table is not None
    standing = decide_call(call.pairs(), table, policy)
    site = DispatchSite(call_id(call.ordinal), call.last_number, DispatchPhase.SEND)
    if standing.decision is CallDecision.FAILED_BY_DEFECT:
        last = call.last_outcome
        rule = _outcome(last).attribution.rule if last is not None else UNRESOLVED_RULE
        return Failure(FailureCategory.DEFECT, site, f"read as a defect under {rule}")
    if standing.decision is CallDecision.FAILED_BY_INFRASTRUCTURE:
        return Failure(
            FailureCategory.INFRASTRUCTURE,
            site,
            "the call failed by infrastructure and no further dispatch is permitted",
        )
    return None


def _dead_segment_stop(state: AttemptState, rules: Rules) -> Failure | None:
    """What a new claim finds stopped in the segments before it: a count started with no
    outcome, or a dispatch intended with no outcome, each now final and counted against
    its maximum, in position order."""
    if rules.redispatch is None:
        return None
    found: list[tuple[int, Failure]] = []
    for group in _groups(state):
        last = group[-1]
        if last.outcome is None:
            stop = _count_stop(group, rules.redispatch.max_dispatches)
            if stop is not None:
                found.append((last.start.position, stop))
    for call in calls_of(state):
        if call.last_outcome is None:
            stop = _call_stop(call, rules.table, rules.redispatch)
            if stop is not None:
                found.append((call.intents[-1].position, stop))
    return min(found, key=lambda pair: pair[0])[1] if found else None


def _groups(state: AttemptState) -> tuple[tuple[CountEvents, ...], ...]:
    held: dict[tuple[RegisteredInputBound, str, str], list[CountEvents]] = {}
    for count in counts_of(state):
        held.setdefault(count.key.reuse, []).append(count)
    return tuple(tuple(group) for group in held.values())


# --- Bookkeeping -----------------------------------------------------------------------------


def _with_event(state: AttemptState, logged: LoggedEvent) -> AttemptState:
    return replace(state, events=(*state.events, logged))


def _with_segment(state: AttemptState, logged: LoggedEvent, *, ended: bool = False) -> AttemptState:
    """The state with ``logged`` appended and its segment's last offset and end updated."""
    stamp = logged.stamp
    assert stamp is not None
    current = state.segments[-1]
    updated = SegmentState(
        current.number,
        current.harness,
        max(current.last_offset_ms, stamp.offset_ms),
        current.ended or ended,
    )
    return replace(state, events=(*state.events, logged), segments=(*state.segments[:-1], updated))


def _held_under(state: AttemptState, key: EventKey) -> LoggedEvent | None:
    for held in state.events:
        if event_key(held) == key:
            return held
    return None


def rules_differ(inputs: FrozenInputs, rules: Rules) -> str | None:
    """Why ``rules`` are not the ones ``inputs`` froze, or ``None`` when they are: the
    transition refuses every event after the admission on this, and the inventory's builder
    lists an attempt it cannot fold on it."""
    if inputs.attribution_table is None:
        if rules.table is not None or rules.redispatch is not None:
            return "a system that calls no model registers no table and no policy"
        return None
    if rules.table is None or rules.redispatch is None:
        return "the registered table and policy are needed and absent"
    if attribution_table_digest(rules.table) != inputs.attribution_table:
        return "the attribution table given is not the one the admission froze"
    if rules.redispatch != inputs.redispatch:
        return "the re-dispatch policy given is not the one the admission froze"
    return None


def _site_name(site: FailureSite) -> str:
    match site:
        case OperationSite():
            return site.operation
        case DispatchSite():
            return f"{site.model_call} dispatch {site.dispatch}"
        case InputBoundSite():
            return site.counting_operation
        case HarnessSite():
            return site.site.value


def _ordinal_of(call: str) -> int:
    prefix = "call-"
    if call.startswith(prefix) and call[len(prefix) :].isdigit():
        return int(call[len(prefix) :])
    return 0


def _intent(logged: LoggedEvent) -> DispatchIntent:
    event = logged.event
    assert isinstance(event, DispatchIntent)
    return event


def _outcome(logged: LoggedEvent) -> DispatchOutcome:
    event = logged.event
    assert isinstance(event, DispatchOutcome)
    return event


def _count_outcome(logged: LoggedEvent) -> CountOutcomeLogged:
    event = logged.event
    assert isinstance(event, CountOutcomeLogged)
    return event


def _operation(logged: LoggedEvent) -> OperationEvent:
    event = logged.event
    assert isinstance(event, OperationEvent)
    return event


def _request(logged: LoggedEvent) -> ApprovalRequested:
    event = logged.event
    assert isinstance(event, ApprovalRequested)
    return event


__all__ = [
    "Appended",
    "rules_differ",
    "AttemptState",
    "CallEvents",
    "CountEvents",
    "Received",
    "Refused",
    "Rules",
    "SegmentState",
    "Transition",
    "call_of",
    "calls_of",
    "count_group",
    "counts_of",
    "fold",
    "held_operation_ids",
    "next_state",
    "operations_of",
    "results_of",
]
