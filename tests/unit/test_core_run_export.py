"""The run export's plain data holds the rulings' invariants at construction: usage counters in
the declared order and never synthesized, an accepted read naming its source and every record
read from it, ids unique, one event order over reads and dispatches, a model-originated read
and the tool call that asked for it naming each other, a failure exactly on a failed status
and pointing into the trace at its site, an approval following the status and not the claims,
rules-only with no model and no retrieval, reserves inside the caps, an embedding model
exactly for vector retrieval, and role-indexed provenance unique by role and held in role
order. The model call's own invariants are ``test_core_model_calls``'s."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from leaveimpact.core import (
    EXPORT_FORMAT_VERSION,
    UNRESOLVED_RULE,
    Abandonment,
    AbandonmentReason,
    AbsentOutcome,
    Answer,
    Approval,
    ApprovalState,
    Approver,
    AsOperation,
    Attribution,
    AttributionKind,
    CallConfiguration,
    CallSetting,
    Caps,
    ClaimAuthor,
    ClientError,
    ClientErrorKind,
    CompleteResponse,
    ComposingPolicy,
    Composition,
    Cost,
    Counted,
    CountingOperation,
    CountingOperationId,
    CountResult,
    CountServiceError,
    DefectOutcome,
    Dispatch,
    DispatchPhase,
    DispatchSite,
    Entity,
    EstablishedBound,
    Failure,
    FailureCategory,
    HarnessOrigin,
    HarnessRevision,
    HarnessSite,
    HarnessSiteName,
    InputBoundSite,
    KeptReason,
    Leave,
    LeaveKind,
    LeaveStatus,
    ModelCall,
    ModelCallId,
    ModelOrigin,
    NoRecordedOutcome,
    Observed,
    Operation,
    OperationId,
    OperationSite,
    OutageAssignment,
    PredicateName,
    PrefetchOrigin,
    PrefetchRule,
    PricingBasis,
    PricingRow,
    PricingSelection,
    RecordOutcome,
    RecordsOutcome,
    RefusedCallOutcome,
    RegisteredInputBound,
    ReportedUsage,
    RequestIdentity,
    Reservation,
    ReservationState,
    Retrieval,
    RetrievalKind,
    RunCondition,
    RunContext,
    RunExport,
    RunRecord,
    RunTrace,
    Segment,
    Source,
    Stamp,
    System,
    SystemKind,
    TerminalStatus,
    Timing,
    ToolCall,
    TreeState,
    Unknown,
    UnknownReason,
    UnreachableOutcome,
    Usage,
    UsageAggregate,
    employee_ref,
    evidenced_active_ms,
    frozen_json,
    is_completed_read,
    is_failed_read,
)
from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion, claim_id, employee_id, leave_id
from leaveimpact.core.model_calls import Observation
from leaveimpact.core.run_trace import Origin

DIGEST = "a" * 64
COMMIT = "b" * 40
LEAVE: Observed[Entity] = Observed(
    Leave(
        leave_id(5),
        employee_id(17),
        date(2026, 9, 15),
        date(2026, 9, 19),
        LeaveKind.ANNUAL,
        LeaveStatus.APPROVED,
    ),
    Source.FRAPPE,
)
CALL = ModelCallId("call-1")
REPORTED = {"inputTokens": 120, "outputTokens": 30, "totalTokens": 150}
PRICED = Cost(297_000_000, True)
PREFETCH = PrefetchOrigin()
HAIKU = PricingSelection("model-a", "eu-central-1", "on_demand")
AGENT = System(SystemKind.AGENT, "reference")
FULL_TEXT = Retrieval(RetrievalKind.FULL_TEXT, None)
CONTEXT = RunContext(
    ScenarioId("scenario_003"),
    WorldVersion("4f2c"),
    LeaveId("leave_005"),
    datetime(2026, 9, 14, 22, 30, tzinfo=UTC),
    "Europe/Istanbul",
)
PRICING = PricingBasis(
    DIGEST,
    "USD",
    date(2026, 9, 1),
    (
        PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_100_000),
        PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_500_000),
    ),
)
COMPOSITION = Composition(ClaimAuthor.RULES, ComposingPolicy("a-policy", DIGEST), (), ())
REQUEST = RequestIdentity(DIGEST, "Converse", "eu.model", "eu-central-1", None)
ANSWERED = CompleteResponse("end_turn", 840, 0)
TIMED_OUT = ClientError(ClientErrorKind.TIMEOUT, "timeout")
ADMITTED = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
REVISION = HarnessRevision(COMMIT, TreeState.CLEAN)
TIMING = Timing((Segment(1, REVISION, 12_000, True),), ADMITTED, ADMITTED, None, None)
APPROVED = Approval(ApprovalState.APPROVED, Approver.AUTOMATIC, DIGEST)
NOT_REQUESTED = Approval(ApprovalState.NOT_REQUESTED, None, None)
METHOD = RegisteredInputBound("provider_count", 1)
CAPS = Caps(20, 100_000, 2, 5_000, "input_plus_output_cached_included", METHOD)
RECONCILED = Reservation(5_000_000_000, ReservationState.RECONCILED, None, 3, 297_000_000)
KEPT = Reservation(
    5_000_000_000, ReservationState.KEPT, KeptReason.USAGE_INCOMPLETE, 3, 5_000_000_000
)


def _dispatch(
    intent: int = 10,
    observation: Observation = ANSWERED,
    read_as: AttributionKind = AttributionKind.BEHAVIOUR,
    *,
    number: int = 1,
    segment: int = 1,
    input_reads: tuple[str, ...] = (),
    count: str = "count-1",
) -> Dispatch:
    """A dispatch whose usage and cost are the priced ones exactly when a response arrived,
    resting on the counting operation ``count``, which ``_trace`` holds for it."""
    answered = isinstance(observation, CompleteResponse)
    return Dispatch(
        number=number,
        segment=segment,
        intent_position=intent,
        outcome_position=None if isinstance(observation, NoRecordedOutcome) else intent + 1,
        request=REQUEST,
        input_reads=tuple(OperationId(read) for read in input_reads),
        observation=observation,
        attribution=Attribution(
            read_as, UNRESOLVED_RULE if read_as is AttributionKind.UNRESOLVED else "a-rule"
        ),
        usage=ReportedUsage(REPORTED) if answered else None,
        cost=PRICED if answered else None,
        zero_cost_rule=None,
        allocation=5_000_000_000,
        allocation_tokens=4_608,
        bound=EstablishedBound(METHOD, "model-a-base", DIGEST, 4_096, CountingOperationId(count)),
        output_maximum=512,
    )


def _count(id: str = "count-1", start: int = 90_000, segment: int = 1) -> CountingOperation:
    """A successful count at positions no dispatch or read of these tests reaches."""
    return CountingOperation(
        CountingOperationId(id),
        METHOD,
        "model-a-base",
        DIGEST,
        segment,
        start,
        start + 1,
        Counted(4_096, None, 100),
        CountResult.COUNTED,
    )


def _counts_for(calls: tuple[ModelCall, ...]) -> tuple[CountingOperation, ...]:
    """One count per distinct counting operation the calls' dispatches rest on."""
    named = dict.fromkeys(d.bound.evidence for call in calls for d in call.dispatches)
    return tuple(_count(id, 90_000 + 10 * index) for index, id in enumerate(named))


def _call(
    id: str = "call-1",
    role: str = "investigator",
    *dispatches: Dispatch,
    answer: Answer | None = None,
) -> ModelCall:
    """A call answered on one dispatch at position 10, unless ``dispatches`` says otherwise;
    an answered call carries text and nothing else unless ``answer`` says what."""
    held = dispatches if dispatches else (_dispatch(),)
    if answer is None and isinstance(held[-1].observation, CompleteResponse):
        answer = Answer(True, (), ())
    return ModelCall(ModelCallId(id), role, held, answer)


def _faulted(id: str = "call-1", intent: int = 10) -> ModelCall:
    return _call(id, "investigator", _dispatch(intent, TIMED_OUT, AttributionKind.INFRASTRUCTURE))


def _asking(operation: str = "op-2") -> ModelCall:
    """call-1 answered with one tool call that became ``operation``."""
    asked = Answer(False, (ToolCall("tu_1", "leave", AsOperation(OperationId(operation))),), ())
    return _call(
        "call-1", "investigator", _dispatch(observation=CompleteResponse("tool_use", 840, 0)),
        answer=asked,
    )  # fmt: skip


def _operation(
    id: str = "op-1",
    origin: Origin = PREFETCH,
    source: Source | None = Source.FRAPPE,
    outcome: object = RecordOutcome(LEAVE),
    position: int | None = 1,
) -> Operation:
    return Operation(
        OperationId(id), origin, "leave", source, {"id": "leave_005"}, outcome, position  # type: ignore[arg-type]
    )


def _claim() -> Unknown:
    return Unknown(
        claim_id=claim_id(1),
        evidence_refs=(),
        subject=employee_ref(employee_id(17)),
        required_fact=PredicateName.HAS_SKILL,
        reason=UnknownReason.ABSENT,
    )


def _trace(
    calls: tuple[ModelCall, ...] | None = None,
    operations: tuple[Operation, ...] | None = None,
    claims: tuple[Unknown, ...] | None = None,
) -> RunTrace:
    held = (_call(),) if calls is None else calls
    return RunTrace(
        held,
        (_operation(),) if operations is None else operations,
        (_claim(),) if claims is None else claims,
        COMPOSITION,
        _counts_for(held),
        None,
    )


def _record(
    system: System = AGENT,
    retrieval: Retrieval = FULL_TEXT,
    status: TerminalStatus = TerminalStatus.COMPLETED,
    failure: Failure | None = None,
    configurations: tuple[tuple[str, CallConfiguration], ...] = (
        ("investigator", CallConfiguration("eu.model", (CallSetting("temperature", 0),))),
    ),
    selections: tuple[tuple[str, PricingSelection], ...] | None = None,
    cost: Cost | None = PRICED,
    reservation: Reservation | None = RECONCILED,
) -> RunRecord:
    """A record whose approval follows its status, and whose attribution table and reservation
    exist exactly when a role calls a model."""
    if selections is None:
        selections = tuple((role, HAIKU) for role, _ in configurations)
    return RunRecord(
        observed_condition=RunCondition.all_reachable(),
        outage=OutageAssignment(frozenset(), DIGEST),
        corpus_level="base",
        preregistration_commit=COMMIT,
        attribution_table=DIGEST if configurations else None,
        model_configurations=configurations,
        pricing_selections=selections,
        prompt_digests=tuple((role, "system", DIGEST) for role, _ in configurations),
        tool_surface_digests=tuple((role, DIGEST) for role, _ in configurations),
        system=system,
        retrieval=retrieval,
        prefetch_rule=PrefetchRule("prefetch-v1", DIGEST),
        caps=CAPS,
        status=status,
        failure=failure,
        abandonment=None,
        timing=TIMING,
        usage=UsageAggregate((("input_tokens", 120, 1), ("output_tokens", 30, 1)), 1, 1),
        cost=cost,
        reservation=reservation if configurations else None,
        approval=NOT_REQUESTED if status is TerminalStatus.FAILED else APPROVED,
        pricing=PRICING,
    )


def _export(record: RunRecord | None = None, trace: RunTrace | None = None) -> RunExport:
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-7",
        1,
        CONTEXT,
        record if record is not None else _record(),
        trace if trace is not None else _trace(),
    )


def _failed(failure: Failure) -> RunRecord:
    """A record of an attempt that failed with ``failure``, no dispatch priced, its
    reservation kept."""
    return _record(status=TerminalStatus.FAILED, failure=failure, cost=None, reservation=KEPT)


# --- Usage and cost ---------------------------------------------------------------------


def test_usage_counters_hold_the_declared_order_and_a_missing_one_reads_as_unknown() -> None:
    usage = Usage((("input_tokens", 120), ("cache_read_input_tokens", 40)))
    assert usage.value("output_tokens") is None
    assert usage.value("cache_read_input_tokens") == 40
    with pytest.raises(ValueError, match="declared order"):
        Usage((("output_tokens", 30), ("input_tokens", 120)))
    with pytest.raises(ValueError, match="not a usage counter"):
        Usage((("total_tokens", 150),))
    with pytest.raises(ValueError, match="reported once"):
        Usage((("input_tokens", 1), ("input_tokens", 2)))
    with pytest.raises(ValueError, match="is an integer, got True"):
        Usage((("input_tokens", True),))
    with pytest.raises(ValueError, match="is an integer, got 1.5"):
        Usage((("input_tokens", 1.5),))  # type: ignore[arg-type]


def test_an_aggregate_carries_its_coverage_and_a_sum_over_no_dispatch_is_no_row() -> None:
    aggregate = UsageAggregate((("input_tokens", 500, 3),), 3, 4)
    assert aggregate.value("input_tokens") == (500, 3)
    assert aggregate.value("output_tokens") is None
    with pytest.raises(ValueError, match="reported by 5 dispatches of 4"):
        UsageAggregate((("input_tokens", 500, 5),), 4, 4)
    with pytest.raises(ValueError, match="input_tokens reported is at least 1, got 0"):
        UsageAggregate((("input_tokens", 0, 0),), 4, 4)
    with pytest.raises(ValueError, match="every call holds a dispatch: 4 calls, 3 dispatches"):
        UsageAggregate((), 4, 3)
    with pytest.raises(ValueError, match="dispatches is an integer, got 2.5"):
        UsageAggregate((), 0, 2.5)  # type: ignore[arg-type]


def test_a_cost_is_an_exact_count_of_pico_dollars_with_its_completeness() -> None:
    with pytest.raises(ValueError, match="a cost in pico-dollars is at least 0, got -1"):
        Cost(-1, True)
    with pytest.raises(ValueError, match="a cost in pico-dollars is an integer, got 1.5"):
        Cost(1.5, True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="completeness is a boolean, got 1"):
        Cost(1, 1)  # type: ignore[arg-type]
    assert PRICED.pico_usd == 120 * 1_100_000 + 30 * 5_500_000


# --- Operations -------------------------------------------------------------------------


def test_the_six_outcomes_split_into_completed_failed_and_neither() -> None:
    completed = (RecordOutcome(LEAVE), AbsentOutcome(), RecordsOutcome(()))
    failed = (
        UnreachableOutcome(Source.JIRA, "refused"),
        DefectOutcome(Source.JIRA, "LIA-42", "no id"),
    )
    assert all(is_completed_read(o) and not is_failed_read(o) for o in completed)
    assert all(is_failed_read(o) and not is_completed_read(o) for o in failed)
    refused = RefusedCallOutcome("limit above the bound")
    assert not is_completed_read(refused) and not is_failed_read(refused)


def test_an_accepted_read_names_its_source_and_every_record_was_read_from_it() -> None:
    with pytest.raises(ValueError, match="only a refused call may name none"):
        _operation(source=None, outcome=AbsentOutcome())
    assert _operation(source=None, outcome=RefusedCallOutcome("unknown tool")).source is None
    with pytest.raises(ValueError, match="a record read from frappe in an operation on jira"):
        _operation(source=Source.JIRA, outcome=RecordsOutcome((LEAVE,)))
    with pytest.raises(ValueError, match="a failure of jira in an operation on frappe"):
        _operation(outcome=UnreachableOutcome(Source.JIRA, "refused"))
    assert _operation(outcome=RecordsOutcome(())).source is Source.FRAPPE


def test_arguments_are_frozen_as_accepted_all_the_way_down() -> None:
    span = {"start": "2026-09-10", "end": "2026-09-12"}
    operation = Operation(
        OperationId("op-2"),
        PREFETCH,
        "leaves_within",
        Source.FRAPPE,
        {"span": span},
        AbsentOutcome(),
    )
    span["end"] = "2026-12-31"
    assert operation.arguments["span"]["end"] == "2026-09-12"  # type: ignore[index]
    with pytest.raises(TypeError):
        operation.arguments["span"]["end"] = "2026-12-31"  # type: ignore[index]
    with pytest.raises(ValueError, match="arguments holds date, which JSON cannot carry"):
        Operation(
            OperationId("op-3"),
            PREFETCH,
            "leave",
            Source.FRAPPE,
            {"on": date(2026, 9, 10)},
            AbsentOutcome(),
        )
    with pytest.raises(ValueError, match="non-finite float"):
        frozen_json({"limit": float("inf")}, "arguments")
    assert frozen_json([1, "a", None, True, 2.5], "arguments") == (1, "a", None, True, 2.5)


def test_an_operation_outside_a_trace_holds_no_position_and_one_inside_must() -> None:
    assert _operation(position=None).position is None
    with pytest.raises(ValueError, match="an operation's position is at least 1, got 0"):
        _operation(position=0)
    with pytest.raises(ValueError, match="operation op-1 of a trace holds no position"):
        _trace(operations=(_operation(position=None),))
    issued = _operation(origin=HarnessOrigin("full-context-documents"))
    assert isinstance(issued.origin, HarnessOrigin)
    with pytest.raises(ValueError, match="the policy that issued a harness read"):
        HarnessOrigin(" ")


# --- The trace --------------------------------------------------------------------------


def test_ids_are_unique_within_their_kind() -> None:
    with pytest.raises(ValueError, match="model call ids are unique"):
        _trace(calls=(_call(), _call()))
    with pytest.raises(ValueError, match="operation ids are unique"):
        _trace(operations=(_operation(), _operation(position=2)))
    with pytest.raises(ValueError, match="claim ids are unique"):
        _trace(claims=(_claim(), _claim()))
    trace = _trace()
    assert trace.model_call(CALL).role == "investigator"
    assert trace.operation(OperationId("op-1")) is not None
    assert trace.operation(OperationId("op-2")) is None
    assert trace.model_call_or_none(ModelCallId("call-2")) is None
    assert [dispatch.intent_position for dispatch in trace.dispatches] == [10]


def test_reads_and_dispatches_share_one_event_order() -> None:
    with pytest.raises(ValueError, match="operations are held in position order"):
        _trace(operations=(_operation(position=5), _operation("op-2", position=3)))
    with pytest.raises(ValueError, match="in the order of their first intents"):
        _trace(calls=(_call("call-1", "investigator", _dispatch(30)), _call("call-2")))
    with pytest.raises(ValueError, match="no two events of a trace share a position"):
        _trace(operations=(_operation(position=10),))
    with pytest.raises(ValueError, match="no two events of a trace share a position"):
        _trace(operations=(_operation(position=11),))  # the dispatch's outcome
    recovered = _call(
        "call-1",
        "investigator",
        _dispatch(10, NoRecordedOutcome(), AttributionKind.UNRESOLVED),
        _dispatch(14, number=2, segment=2),
    )
    trace = _trace(calls=(recovered, _call("call-2", "investigator", _dispatch(20))))
    assert [dispatch.number for dispatch in trace.dispatches] == [1, 2, 1]


def test_a_model_originated_read_and_the_tool_call_that_asked_for_it_name_each_other() -> None:
    read = _operation("op-2", origin=ModelOrigin(CALL), position=12)
    trace = _trace(calls=(_asking(),), operations=(_operation(), read))
    assert trace.operation(OperationId("op-2")) is read
    with pytest.raises(
        ValueError, match="answers model call 'call-9', which the trace does not hold"
    ):
        _trace(operations=(_operation(origin=ModelOrigin(ModelCallId("call-9"))),))
    with pytest.raises(ValueError, match="whose answer holds no tool call that became it"):
        _trace(operations=(_operation(origin=ModelOrigin(CALL)),))
    with pytest.raises(ValueError, match="became operation op-2, which the trace does not hold"):
        _trace(calls=(_asking(),))
    # The two name one tool: a call of one routed to a read of another is not a history.
    searched = Answer(False, (ToolCall("tu_1", "search", AsOperation(OperationId("op-2"))),), ())
    misrouted = _call(
        "call-1", "investigator",
        _dispatch(observation=CompleteResponse("tool_use", 840, 0)), answer=searched,
    )  # fmt: skip
    with pytest.raises(
        ValueError, match="is a call of 'leave' and the tool call that became it names 'search'"
    ):
        _trace(calls=(misrouted,), operations=(_operation(), read))
    with pytest.raises(ValueError, match="became operation op-1, which no model call asked for"):
        _trace(calls=(_asking("op-1"),))
    twice = Answer(
        False,
        (
            ToolCall("tu_1", "leave", AsOperation(OperationId("op-2"))),
            ToolCall("tu_2", "leave", AsOperation(OperationId("op-2"))),
        ),
        (),
    )
    with pytest.raises(ValueError, match="operation op-2 is the disposition of two tool calls"):
        _trace(
            calls=(
                _call(
                    "call-1", "investigator",
                    _dispatch(observation=CompleteResponse("tool_use", 840, 0)), answer=twice,
                ),
            ),
            operations=(_operation(), read),
        )  # fmt: skip


def test_a_dispatch_was_shown_only_reads_the_trace_holds_logged_before_its_intent() -> None:
    shown = _call("call-1", "investigator", _dispatch(input_reads=("op-1",)))
    assert _trace(calls=(shown,)).dispatches[0].input_reads == ("op-1",)
    with pytest.raises(ValueError, match="was shown operation op-9, which the trace does not"):
        _trace(calls=(_call("call-1", "investigator", _dispatch(input_reads=("op-9",))),))
    with pytest.raises(ValueError, match="was shown operation op-1, which was logged after"):
        _trace(calls=(shown,), operations=(_operation(position=40),))


# --- The record -------------------------------------------------------------------------


def test_a_failure_is_recorded_exactly_when_the_status_is_failed() -> None:
    failure = Failure(FailureCategory.DEFECT, OperationSite(OperationId("op-1")), "no world id")
    with pytest.raises(ValueError, match="exactly when the status is failed"):
        replace(_record(), failure=failure)
    with pytest.raises(ValueError, match="exactly when the status is failed"):
        replace(_record(), status=TerminalStatus.FAILED)
    assert _record(status=TerminalStatus.FAILED, failure=failure).failure is failure


def test_an_approval_follows_the_status_and_not_the_claims() -> None:
    """A completed attempt is approved, an abstention's empty payload included, and so is one
    that reported at its cap. A failed one states the approval as it stood: none, a request
    nobody answered, or one given before the attempt failed."""
    failure = Failure(FailureCategory.DEFECT, OperationSite(OperationId("op-1")), "no world id")
    failed = _record(status=TerminalStatus.FAILED, failure=failure)
    assert failed.approval.state is ApprovalState.NOT_REQUESTED
    waiting = Approval(ApprovalState.REQUESTED_UNAPPROVED, None, DIGEST)
    assert replace(failed, approval=waiting).approval is waiting
    # Approved, resumed, and then the terminal append failed: the export says all three,
    # and its active time leaves out only the wait.
    approved_then_failed = replace(
        failed,
        approval=APPROVED,
        timing=replace(
            TIMING, approval_requested=Stamp(1, 100, 30), approval_resumed=Stamp(1, 200, 31)
        ),
    )
    assert approved_then_failed.approval is APPROVED
    assert evidenced_active_ms(approved_then_failed.timing) == 12_000 - 100
    with pytest.raises(ValueError, match="status completed, approval not_requested"):
        replace(_record(), approval=NOT_REQUESTED)
    with pytest.raises(ValueError, match="status completed, approval requested_unapproved"):
        replace(_record(), approval=waiting)
    at_cap = replace(_record(), status=TerminalStatus.CAP_EXHAUSTED)
    assert at_cap.approval is APPROVED
    stamped = replace(TIMING, approval_requested=Stamp(1, 11_000, 30))
    with pytest.raises(ValueError, match="stamps an approval request the approval does not hold"):
        replace(failed, timing=stamped)
    resumed = replace(stamped, approval_resumed=Stamp(1, 11_004, 31))
    with pytest.raises(ValueError, match="stamps a resume from an approval that was not given"):
        replace(failed, approval=waiting, timing=resumed)
    assert replace(_record(), timing=resumed).timing is resumed
    # An attempt that did not fail ended at a terminal event its worker wrote.
    with pytest.raises(ValueError, match="also stamped its resume"):
        replace(_record(), timing=stamped)
    killed = replace(TIMING, segments=(Segment(1, REVISION, 12_000, False),))
    with pytest.raises(ValueError, match="its last segment's end was recorded"):
        replace(_record(), timing=killed)
    assert replace(failed, timing=killed).timing is killed


def test_an_abandon_command_is_held_at_the_abandoned_site_or_beside_a_defect() -> None:
    abandoned = Failure(
        FailureCategory.INFRASTRUCTURE, HarnessSite(HarnessSiteName.ABANDONED), "no owner"
    )
    at_prefetch = Failure(
        FailureCategory.INFRASTRUCTURE, HarnessSite(HarnessSiteName.PREFETCH), "the store"
    )
    decision = Abandonment("operator", 1, AbandonmentReason.CANCELLED)
    with pytest.raises(ValueError, match="holds the abandon command that closed it"):
        _record(status=TerminalStatus.FAILED, failure=abandoned)
    elsewhere = _record(status=TerminalStatus.FAILED, failure=at_prefetch, reservation=KEPT)
    with pytest.raises(ValueError, match="finalized a recorded defect; the failure is by defect"):
        replace(elsewhere, abandonment=decision)
    kept = replace(elsewhere, failure=abandoned, abandonment=decision)
    assert kept.abandonment is decision
    with pytest.raises(ValueError, match="an abandoned attempt failed by infrastructure"):
        replace(kept, failure=replace(abandoned, category=FailureCategory.DEFECT))
    # The command that closed an attempt whose log already held a defect is who closed, and
    # the ending stays the defect's.
    defect = Failure(FailureCategory.DEFECT, OperationSite(OperationId("op-1")), "malformed")
    finalized = replace(elsewhere, failure=defect, abandonment=decision)
    assert (finalized.failure, finalized.abandonment) == (defect, decision)


def test_the_unhandled_site_is_a_defect() -> None:
    unhandled = Failure(
        FailureCategory.INFRASTRUCTURE, HarnessSite(HarnessSiteName.UNHANDLED), "KeyError"
    )
    with pytest.raises(ValueError, match="a failure at the unhandled site is a defect"):
        _record(status=TerminalStatus.FAILED, failure=unhandled, reservation=KEPT)
    record = _record(
        status=TerminalStatus.FAILED,
        failure=replace(unhandled, category=FailureCategory.DEFECT),
        reservation=KEPT,
    )
    assert record.failure is not None and record.failure.category is FailureCategory.DEFECT


def test_an_attempt_with_no_segment_was_never_claimed() -> None:
    """Zero segments is one history: closed by an abandon command before any worker, fencing
    generation 0, nothing requested; its trace is empty (the event log step's ruling on
    admission)."""
    never = Timing((), ADMITTED, ADMITTED, None, None)
    abandoned = Failure(
        FailureCategory.INFRASTRUCTURE, HarnessSite(HarnessSiteName.ABANDONED), "no claim"
    )
    command = Abandonment("operator", 0, AbandonmentReason.CANCELLED)
    at_prefetch = Failure(
        FailureCategory.INFRASTRUCTURE, HarnessSite(HarnessSiteName.PREFETCH), "the store"
    )
    base = _record(status=TerminalStatus.FAILED, failure=at_prefetch, reservation=KEPT)
    with pytest.raises(ValueError, match="its failure is at the abandoned site"):
        replace(base, timing=never)
    with pytest.raises(ValueError, match="fenced generation 0, got 1"):
        replace(
            base,
            timing=never,
            failure=abandoned,
            abandonment=replace(command, ownership_generation=1),
        )
    record = replace(base, timing=never, failure=abandoned, abandonment=command)
    assert record.timing.segments == ()
    with pytest.raises(ValueError, match="so its trace is empty"):
        _export(record=record)
    empty = RunTrace((), (), (), COMPOSITION, (), None)
    export = _export(record=replace(record, usage=UsageAggregate((), 0, 0), cost=None), trace=empty)
    assert export.trace.counting_operations == ()


def test_a_dispatch_rests_on_a_held_count_and_a_failure_at_the_bound_names_one() -> None:
    orphan = _call("call-1", "investigator", _dispatch(count="count-9"))
    with pytest.raises(ValueError, match="rests on counting operation count-9, which the trace"):
        RunTrace((orphan,), (_operation(),), (_claim(),), COMPOSITION, (_count(),), None)
    with pytest.raises(ValueError, match="counting operation ids are unique"):
        RunTrace((), (), (), COMPOSITION, (_count(), _count()), None)
    with pytest.raises(ValueError, match="held in the order of their starts"):
        RunTrace((), (), (), COMPOSITION, (_count("count-2", 200), _count("count-1", 100)), None)
    with pytest.raises(ValueError, match="no two events of a trace share a position"):
        RunTrace((), (_operation(),), (), COMPOSITION, (_count(start=1),), None)
    with pytest.raises(ValueError, match="no two events of a trace share a position"):
        RunTrace((), (_operation(),), (), COMPOSITION, (), 1)
    refused = CountingOperation(
        CountingOperationId("count-1"),
        METHOD,
        "model-a-base",
        DIGEST,
        1,
        5,
        6,
        CountServiceError(403, "AccessDeniedException", "denied", None, 90),
        CountResult.REFUSED,
    )
    trace = RunTrace((), (_operation(),), (), COMPOSITION, (refused,), None)
    record = _record(
        status=TerminalStatus.FAILED,
        failure=Failure(
            FailureCategory.DEFECT, InputBoundSite(CountingOperationId("count-1")), "denied"
        ),
        reservation=KEPT,
        cost=None,
    )
    record = replace(record, usage=UsageAggregate((), 0, 0))
    at_the_bound = record.failure
    assert at_the_bound is not None
    assert _export(record=record, trace=trace).record.failure is at_the_bound
    infrastructure = replace(
        record, failure=replace(at_the_bound, category=FailureCategory.INFRASTRUCTURE)
    )
    with pytest.raises(ValueError, match="whose last count was refused is by defect"):
        _export(record=infrastructure, trace=trace)
    elsewhere = replace(
        record,
        failure=replace(at_the_bound, site=InputBoundSite(CountingOperationId("count-2"))),
    )
    with pytest.raises(ValueError, match="which the trace does not hold"):
        _export(record=elsewhere, trace=trace)
    counted = RunTrace((), (_operation(),), (), COMPOSITION, (_count(start=5),), None)
    with pytest.raises(ValueError, match="names a counting operation that did not count"):
        _export(record=record, trace=counted)


def test_rules_only_calls_no_model_and_retrieves_nothing() -> None:
    rules_only = System(SystemKind.RULES_ONLY, "frozen")
    with pytest.raises(ValueError, match="records no model configuration"):
        _record(system=rules_only, retrieval=Retrieval(RetrievalKind.NONE, None))
    with pytest.raises(ValueError, match="its retrieval is none"):
        _record(system=rules_only, configurations=())
    record = _record(
        system=rules_only, retrieval=Retrieval(RetrievalKind.NONE, None), configurations=()
    )
    assert record.model_configurations == ()
    assert (record.attribution_table, record.reservation) == (None, None)
    assert SystemKind.FULL_CONTEXT.value == "full_context"


def test_what_only_a_model_system_has_is_recorded_exactly_when_a_role_calls_a_model() -> None:
    with pytest.raises(ValueError, match="an attribution table is named exactly when"):
        replace(_record(), attribution_table=None)
    with pytest.raises(ValueError, match="a reservation is recorded exactly when"):
        replace(_record(), reservation=None)
    with pytest.raises(ValueError, match="the attribution table digest is a SHA-256"):
        replace(_record(), attribution_table="deadbeef")
    with pytest.raises(ValueError, match="the assigned corpus level is a non-empty identifier"):
        replace(_record(), corpus_level="")


def test_role_indexed_provenance_is_unique_by_role_and_held_in_role_order() -> None:
    one = CallConfiguration("eu.model", ())
    with pytest.raises(ValueError, match="a role calls one model configuration"):
        _record(configurations=(("investigator", one), ("investigator", one)))
    record = _record(configurations=(("synthesizer", one), ("investigator", one)))
    assert [role for role, _ in record.model_configurations] == ["investigator", "synthesizer"]
    with pytest.raises(ValueError, match="a role sees one tool surface"):
        replace(record, tool_surface_digests=(("a", DIGEST), ("a", DIGEST)))
    with pytest.raises(ValueError, match="a prompt is digested once per role and name"):
        replace(record, prompt_digests=(("a", "system", DIGEST), ("a", "system", DIGEST)))
    with pytest.raises(ValueError, match="the a system prompt digest is a SHA-256"):
        replace(record, prompt_digests=(("a", "system", "deadbeef"),))


def test_every_role_that_calls_a_model_names_the_rate_it_was_priced_under() -> None:
    one = CallConfiguration("eu.model", ())
    with pytest.raises(ValueError, match=r"configured \['investigator'\], priced \[\]"):
        _record(configurations=(("investigator", one),), selections=())
    with pytest.raises(ValueError, match="a role is priced under one selection"):
        _record(selections=(("investigator", HAIKU), ("investigator", HAIKU)))
    with pytest.raises(ValueError, match="the basis is in USD, got 'EUR'"):
        PricingBasis(DIGEST, "EUR", date(2026, 9, 1), ())
    with pytest.raises(ValueError, match=r"prompted \['investigator', 'other'\]"):
        replace(
            _record(),
            prompt_digests=(("investigator", "system", DIGEST), ("other", "system", DIGEST)),
        )
    with pytest.raises(ValueError, match=r"surfaced \[\]"):
        replace(_record(), tool_surface_digests=())
    record = _record(configurations=(("b", one), ("a", one)))
    assert [role for role, _ in record.pricing_selections] == ["a", "b"]
    unpriced = PricingSelection("model-z", "eu-central-1", "on_demand")
    with pytest.raises(
        ValueError, match="no input_tokens rate for investigator's selection model-z"
    ):
        _record(selections=(("investigator", unpriced),))


def test_the_reserves_sit_inside_the_caps_and_an_embedding_model_names_vector_retrieval() -> None:
    with pytest.raises(ValueError, match="call reserve sits inside the call cap, got 20 of 20"):
        Caps(20, 100_000, 20, 5_000, "input_plus_output_cached_included", METHOD)
    with pytest.raises(ValueError, match="token reserve sits inside the token cap"):
        Caps(20, 100_000, 2, 100_000, "input_plus_output_cached_included", METHOD)
    with pytest.raises(ValueError, match="call_cap is positive"):
        Caps(0, 100_000, 0, 5_000, "input_plus_output_cached_included", METHOD)
    with pytest.raises(ValueError, match="exactly for vector retrieval"):
        Retrieval(RetrievalKind.VECTOR, None)
    assert Retrieval(RetrievalKind.VECTOR, "eu.embedder").embedding_model == "eu.embedder"


def test_pricing_rows_are_unique_by_rate_and_the_commit_is_a_full_sha() -> None:
    row = PricingRow("key", "eu-central-1", "on_demand", "input_tokens", 1_100_000)
    with pytest.raises(ValueError, match="a rate is given once"):
        PricingBasis(DIGEST, "USD", date(2026, 9, 1), (row, row))
    assert PRICING.rate("model-a", "eu-central-1", "on_demand", "input_tokens") == 1_100_000
    assert PRICING.rate("other", "eu-central-1", "on_demand", "input_tokens") is None
    with pytest.raises(ValueError, match="a token class is a usage counter name"):
        PricingRow("key", "eu-central-1", "on_demand", "total_tokens", 1)
    with pytest.raises(ValueError, match="forty-hex git commit"):
        HarnessRevision("abc123", TreeState.CLEAN)


# --- The export -------------------------------------------------------------------------


def test_the_export_is_this_formats_self_identifying_tree() -> None:
    export = _export()
    assert (export.format_version, export.run_id, export.attempt) == (
        EXPORT_FORMAT_VERSION,
        "run-7",
        1,
    )
    assert EXPORT_FORMAT_VERSION == 3
    with pytest.raises(ValueError, match="builds export format 3, got 2"):
        replace(export, format_version=2)
    with pytest.raises(ValueError, match="an attempt is at least 1, got 0"):
        replace(export, attempt=0)
    with pytest.raises(ValueError, match="an attempt is an integer, got 1.5"):
        replace(export, attempt=1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="the format version is an integer, got True"):
        replace(export, format_version=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="a run id is a non-empty identifier"):
        replace(export, run_id=" ")


def test_a_failure_at_an_operation_is_a_defect_at_one_that_returned_something() -> None:
    defect = Failure(FailureCategory.DEFECT, OperationSite(OperationId("op-1")), "no world id")
    faulted = (_faulted(),)
    # A defect is found at an operation that returned something; an unreachable or a
    # refused operation read nothing, an absent answer is evidence, and none anchors one.
    for unread in (
        UnreachableOutcome(Source.FRAPPE, "no answer after the retries"),
        RefusedCallOutcome("LIA-42 is no leave id"),
        AbsentOutcome(),
    ):
        source = None if isinstance(unread, RefusedCallOutcome) else Source.FRAPPE
        with pytest.raises(ValueError, match="could not accept, got defect at 'op-1'"):
            _export(
                record=_failed(defect),
                trace=_trace(faulted, (_operation(source=source, outcome=unread),), ()),
            )
    absent = replace(defect, site=OperationSite(OperationId("op-9")))
    with pytest.raises(ValueError, match="got defect at 'op-9'"):
        _export(record=_failed(absent), trace=_trace(faulted, claims=()))
    malformed = _operation(
        outcome=DefectOutcome(Source.FRAPPE, "Employee/HR-EMP-00017", "no world id")
    )
    export = _export(record=_failed(defect), trace=_trace(faulted, (malformed,), ()))
    assert export.record.failure is defect
    # The harness's own defect: the record came back and the run could not accept it.
    contradicted = replace(defect, reason="the HR system answered with leave_998")
    export = _export(record=_failed(contradicted), trace=_trace(faulted, claims=()))
    assert export.record.failure is contradicted
    misfiled = replace(defect, category=FailureCategory.INFRASTRUCTURE)
    with pytest.raises(ValueError, match="got infrastructure at 'op-1'"):
        _export(record=_failed(misfiled), trace=_trace(faulted, claims=()))


def test_a_failure_at_a_dispatch_names_one_the_trace_holds_and_agrees_with_its_reading() -> None:
    at_send = DispatchSite(CALL, 1, DispatchPhase.SEND)
    infrastructure = Failure(FailureCategory.INFRASTRUCTURE, at_send, "timeout")
    trace = _trace((_faulted(),), claims=())
    assert _export(record=_failed(infrastructure), trace=trace).record.failure is infrastructure
    with pytest.raises(ValueError, match="one no complete response arrived for"):
        _export(record=_failed(infrastructure), trace=_trace(claims=()))  # the call answered
    as_behaviour = _call(
        "call-1", "investigator", _dispatch(10, TIMED_OUT, AttributionKind.BEHAVIOUR)
    )
    with pytest.raises(ValueError, match="by infrastructure at the send of a dispatch read"):
        _export(record=_failed(infrastructure), trace=_trace((as_behaviour,), claims=()))
    with pytest.raises(ValueError, match="by defect at the send of a dispatch read as"):
        _export(
            record=_failed(replace(infrastructure, category=FailureCategory.DEFECT)), trace=trace
        )
    # A failure at the send names the call's last dispatch, one nothing whole arrived for.
    answered_after = _call(
        "call-1",
        "investigator",
        _dispatch(10, TIMED_OUT, AttributionKind.INFRASTRUCTURE),
        _dispatch(14, number=2),
    )
    with pytest.raises(ValueError, match="a failure at the send names a call's last dispatch"):
        _export(record=_failed(infrastructure), trace=_trace((answered_after,), claims=()))
    for phase in (DispatchPhase.PARSE, DispatchPhase.RECORD):
        nothing_arrived = replace(
            infrastructure, category=FailureCategory.DEFECT, site=DispatchSite(CALL, 1, phase)
        )
        with pytest.raises(ValueError, match="names one whose response arrived"):
            _export(record=_failed(nothing_arrived), trace=trace)
    for missing in (DispatchSite(ModelCallId("call-9"), 1, DispatchPhase.SEND),
                    DispatchSite(CALL, 2, DispatchPhase.SEND)):  # fmt: skip
        with pytest.raises(ValueError, match="which the trace does not hold"):
            _export(record=_failed(replace(infrastructure, site=missing)), trace=trace)
    # The re-dispatch bound exhausted on an unresolved history: infrastructure, anchored at
    # the last dispatch.
    unresolved = _call(
        "call-1", "investigator", _dispatch(10, NoRecordedOutcome(), AttributionKind.UNRESOLVED)
    )
    exhausted = _export(record=_failed(infrastructure), trace=_trace((unresolved,), claims=()))
    assert exhausted.trace.model_call(CALL).state.value == "unresolved"


def test_a_dispatch_read_as_a_defect_is_its_calls_last_and_what_the_attempt_failed_at() -> None:
    read_as_defect = _dispatch(10, TIMED_OUT, AttributionKind.DEFECT)
    lost = _call("call-1", "investigator", read_as_defect)
    at_its_send = Failure(
        FailureCategory.DEFECT, DispatchSite(CALL, 1, DispatchPhase.SEND), "the request was ours"
    )
    kept = _export(record=_failed(at_its_send), trace=_trace((lost,), claims=()))
    assert kept.record.failure is at_its_send
    refusal = "is read as a defect; such a dispatch is its call's last"

    # Dispatched again and answered, the attempt completed: the defect recovered from.
    answered_after = _call("call-1", "investigator", read_as_defect, _dispatch(14, number=2))
    with pytest.raises(ValueError, match=f"dispatch 1 of model call call-1 {refusal}"):
        _export(trace=_trace((answered_after,)))
    # Left behind by a later call that answered, the attempt completed.
    with pytest.raises(ValueError, match=refusal):
        _export(trace=_trace((lost, _call("call-2", "investigator", _dispatch(20)))))
    # Behind an infrastructure failure at a later call: an attempt open to a retry.
    elsewhere = Failure(
        FailureCategory.INFRASTRUCTURE,
        DispatchSite(ModelCallId("call-2"), 1, DispatchPhase.SEND),
        "timeout",
    )
    with pytest.raises(ValueError, match=refusal):
        _export(record=_failed(elsewhere), trace=_trace((lost, _faulted("call-2", 20)), claims=()))
    # Failed by defect, and at another place: an operation, or a later dispatch of the call.
    at_a_read = Failure(FailureCategory.DEFECT, OperationSite(OperationId("op-1")), "no world id")
    with pytest.raises(ValueError, match=refusal):
        _export(record=_failed(at_a_read), trace=_trace((lost,), claims=()))
    twice = _call(
        "call-1",
        "investigator",
        read_as_defect,
        _dispatch(14, TIMED_OUT, AttributionKind.DEFECT, number=2),
    )
    at_the_second = replace(at_its_send, site=DispatchSite(CALL, 2, DispatchPhase.SEND))
    with pytest.raises(ValueError, match=f"dispatch 1 of model call call-1 {refusal}"):
        _export(record=_failed(at_the_second), trace=_trace((twice,), claims=()))

    # A defect found while parsing or recording a response that arrived is no reading of a
    # dispatch: the dispatch is read as behaviour and the failure names the phase.
    unparsed = ModelCall(CALL, "investigator", (_dispatch(),), None)
    for phase in (DispatchPhase.PARSE, DispatchPhase.RECORD):
        found = Failure(FailureCategory.DEFECT, DispatchSite(CALL, 1, phase), "raised")
        record = _record(status=TerminalStatus.FAILED, failure=found)
        assert _export(record=record, trace=_trace((unparsed,), claims=())).record.failure is found


def test_a_response_nobody_parsed_is_preserved_only_by_the_failure_that_ended_there() -> None:
    unparsed = ModelCall(CALL, "investigator", (_dispatch(),), None)
    at_parse = Failure(
        FailureCategory.DEFECT, DispatchSite(CALL, 1, DispatchPhase.PARSE), "the parser raised"
    )
    record = _record(status=TerminalStatus.FAILED, failure=at_parse)
    kept = _export(record=record, trace=_trace((unparsed,), claims=()))
    assert kept.trace.model_call(CALL).answer is None
    assert kept.trace.model_call(CALL).stop_reason == "end_turn"
    with pytest.raises(ValueError, match="holds a complete response and no answer"):
        _export(trace=_trace((unparsed,)))
    elsewhere = replace(at_parse, site=HarnessSite(HarnessSiteName.COMPOSITION))
    with pytest.raises(ValueError, match="holds a complete response and no answer"):
        _export(record=replace(record, failure=elsewhere), trace=_trace((unparsed,), claims=()))


def test_every_role_is_configured_and_every_dispatch_ran_in_a_segment_the_record_holds() -> None:
    synthesizer = _call("call-2", "synthesizer", _dispatch(20))
    with pytest.raises(ValueError, match="ran as 'synthesizer', a role with no recorded model"):
        _export(trace=_trace((_call(), synthesizer)))
    later = _call("call-1", "investigator", _dispatch(segment=2))
    with pytest.raises(ValueError, match="ran in segment 2, which the record does not hold"):
        _export(trace=_trace((later,)))
    second = Segment(2, REVISION, 400, True)
    two = replace(_record(), timing=replace(TIMING, segments=(*TIMING.segments, second)))
    assert _export(record=two, trace=_trace((later,))).record.timing.segments[1] is second


def test_a_cumulative_cost_follows_a_priced_dispatch_and_a_reservation_every_priced_send() -> None:
    with pytest.raises(
        ValueError, match="a cumulative cost is recorded exactly when a dispatch was priced"
    ):
        _export(record=_record(cost=None))
    with pytest.raises(
        ValueError, match="a cumulative cost is recorded exactly when a dispatch was priced"
    ):
        _export(trace=_trace((_faulted(),), claims=()))
    with pytest.raises(ValueError, match="reconciled only when every send was priced whole"):
        _export(record=_record(cost=None), trace=_trace((_faulted(),), claims=()))
    unpriced = _export(
        record=_record(cost=None, reservation=KEPT), trace=_trace((_faulted(),), claims=())
    )
    assert unpriced.record.cost is None
    floor = replace(_dispatch(), cost=Cost(132_000_000, False))
    with pytest.raises(ValueError, match="reconciled only when every send was priced whole"):
        _export(trace=_trace((_call("call-1", "investigator", floor),)))
    # The record's own cost says incomplete while every dispatch was priced whole: the
    # evaluator reports the disagreement, and the reservation cannot be reconciled over it.
    with pytest.raises(ValueError, match="incomplete cumulative cost never carries a reconciled"):
        _export(record=_record(cost=Cost(PRICED.pico_usd, False)))


def test_a_rules_only_export_holds_no_model_call() -> None:
    record = _record(
        system=System(SystemKind.RULES_ONLY, "frozen"),
        retrieval=Retrieval(RetrievalKind.NONE, None),
        configurations=(),
        cost=None,
    )
    with pytest.raises(ValueError, match="a rules-only export holds no model call"):
        _export(record=record)
    assert _export(record=record, trace=_trace(calls=())).trace.model_calls == ()
    issued = _operation(origin=HarnessOrigin("full-context-documents"))
    with pytest.raises(ValueError, match="of a rules-only export is not the prefetch's"):
        _export(record=record, trace=_trace(calls=(), operations=(issued,)))
    by_a_model = Composition(ClaimAuthor.MODEL, COMPOSITION.policy, (), ())
    with pytest.raises(ValueError, match="claims were composed by the rules"):
        _export(record=record, trace=RunTrace((), (_operation(),), (), by_a_model, (), None))


def test_the_approvals_stamps_are_events_of_the_same_order_as_reads_and_dispatches() -> None:
    def stamped(requested: Stamp, resumed: Stamp, *segments: Segment) -> RunRecord:
        held = segments if segments else TIMING.segments
        timing = replace(
            TIMING, segments=held, approval_requested=requested, approval_resumed=resumed
        )
        return replace(_record(), timing=timing)

    in_order = stamped(Stamp(1, 11_000, 30), Stamp(1, 11_004, 31))
    assert _export(record=in_order).record.timing.approval_resumed == Stamp(1, 11_004, 31)
    for taken in (1, 10, 11):  # the read, the dispatch's intent, its outcome
        with pytest.raises(ValueError, match=f"stamp at position {taken} shares it"):
            _export(record=stamped(Stamp(1, 11_000, taken), Stamp(1, 11_004, 31)))
    three = (
        Segment(1, REVISION, 12_000, True),
        Segment(2, REVISION, 600, False),
        Segment(3, REVISION, 2_000, True),
    )
    across = stamped(Stamp(1, 11_000, 5), Stamp(3, 50, 6), *three)
    # The dispatch at position 10 ran in segment 1, after the resume of segment 3 at 6.
    with pytest.raises(ValueError, match="position 10 ran in segment 1, after one of segment 3"):
        _export(record=across)
    later = _call("call-1", "investigator", _dispatch(segment=3))
    assert _export(record=across, trace=_trace((later,))).record.timing.segments == three


def test_a_read_the_model_asked_for_is_logged_after_that_calls_answer() -> None:
    early = _operation("op-2", origin=ModelOrigin(CALL), position=5)
    with pytest.raises(ValueError, match="was logged before that call's answer"):
        _trace(calls=(_asking(),), operations=(_operation(), early))


def test_an_attempt_that_did_not_fail_holds_no_unresolved_call() -> None:
    unresolved = _call(
        "call-1", "investigator", _dispatch(10, NoRecordedOutcome(), AttributionKind.UNRESOLVED)
    )
    with pytest.raises(ValueError, match="is unresolved in an attempt that did not fail"):
        _export(record=_record(cost=None, reservation=KEPT), trace=_trace((unresolved,)))
