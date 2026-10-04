"""The twelve hand-built exports export format 2 is accepted on, one per case format 1 could
not state.

Test infrastructure, built on ``core`` alone so that every later group can import it: the
composer's tests, the evaluator's fact-stage measures and the event log's export reader
all need exports of these shapes before any harness produces one. Each function returns
one whole ``RunExport`` of an agent's attempt on the stated-fact fixture's small world.
The cases are the contract step's (its ruling on time, answers, tool calls and approval):

1. facts beside tools in one answer
2. a malformed fact batch
3. a refused fact that cannot construct a value
4. a call cut at the output limit
5. a fact-submission tool handled by the harness
6. an unresolved dispatch followed by an answered one
7. the Nova signature beside another model error
8. recovered and abandoned attempts (a paused attempt has no export)
9. an approval wait across a restart
10. a wrong scope beside an unplaced one
11. a multi-tool answer whose first call ends the attempt
12. a tool call whose result was lost before it was logged

The provenance around each is inert and the same: one role, one priced selection, the
usage and the cumulative cost summed from the dispatches as a harness sums them, and the
reservation settled as a ledger settles it. What a case is about is in its own function.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta

from leaveimpact.core import (
    EXPORT_FORMAT_VERSION,
    Abandonment,
    AbsentOutcome,
    Admitted,
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
    Claim,
    ClaimAuthor,
    CompleteResponse,
    ComposingPolicy,
    Composition,
    Cost,
    DefectOutcome,
    Dispatch,
    FactRefusal,
    Failure,
    FailureCategory,
    HandledAsBatch,
    HarnessRevision,
    HarnessSite,
    HarnessSiteName,
    KeptReason,
    MalformedBatch,
    ModelCall,
    ModelCallId,
    ModelOrigin,
    NoRecordedOutcome,
    Operation,
    OperationId,
    OperationSite,
    OutageAssignment,
    ParsedBatch,
    PlacementState,
    PredicateName,
    PrefetchOrigin,
    PrefetchRule,
    PricingBasis,
    PricingRow,
    PricingSelection,
    RecordsOutcome,
    Refused,
    RefusedBy,
    RefusedInput,
    ReportedUsage,
    RequestIdentity,
    Requirement,
    RequirementPlacement,
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
    Sends,
    ServiceError,
    SkillCriterion,
    Source,
    SpanPlacement,
    Stamp,
    StatedFact,
    System,
    SystemKind,
    TerminalStatus,
    Timing,
    ToolCall,
    TreeState,
    Undispatched,
    UndispatchedReason,
    UnresolvedToolCall,
    aggregate_usage,
    event_ref,
    review_payload_digest,
    run_cost,
)
from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion, skill_id
from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.model_calls import FactBatch, Observation
from tests.unit import stated_fixture as f

DIGEST = "a" * 64
COMMIT = "b" * 40
ROLE = "investigator"
SELECTION = PricingSelection("model-a", "eu-central-1", "on_demand")
BASIS = PricingBasis(
    DIGEST,
    "USD",
    date(2026, 9, 1),
    (
        PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_100_000),
        PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_500_000),
    ),
)
CONTEXT = RunContext(
    ScenarioId("scenario_003"),
    WorldVersion("7b806ed6"),
    LeaveId("leave_005"),
    datetime(2026, 3, 2, 9, 0, tzinfo=UTC),
    "Europe/Istanbul",
)
REQUEST = RequestIdentity(DIGEST, "Converse", "eu.model", "eu-central-1", None)
REVISION = HarnessRevision(COMMIT, TreeState.CLEAN)
ADMITTED = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)
REPORTED = {"inputTokens": 120, "outputTokens": 30, "totalTokens": 150}
PRICED = Cost(120 * 1_100_000 + 30 * 5_500_000, True)
ALLOCATION = 5_000_000_000
ALLOCATION_TOKENS = 4_608
"""The worst case one dispatch is counted for against the token cap: its input and
its output limit."""
RULES = Composition(ClaimAuthor.RULES, ComposingPolicy("stated-fact-composer", DIGEST), (), ())
PARSER = RefusedBy("fact-batch-parser-v1", "c" * 64)
ARGUMENT_PARSER = RefusedBy("tool-argument-parser-v1", "d" * 64)

SKILL = StatedFact(PredicateName.HAS_SKILL, f.DENIZ_REF, "kafka", f.COMMENT_REF, f.REMARK)
"""Deniz's comment, read as stating that Deniz has the Kafka skill."""


SCOPED_QUOTE = (
    f"The {f.TITLE} release needs one Kafka person; raise it at the Release review, as the "
    "Ledger cutover did."
)
"""A sentence naming three things: the ticket the requirement is about, a meeting, and work
the run never read."""


def requirement(span: str) -> StatedFact:
    """A clause read as requiring a Kafka person, with ``span`` as what it applies to."""
    return StatedFact(
        PredicateName.REQUIRES,
        f.CLAUSE_REF,
        Requirement(1, (SkillCriterion(skill_id("kafka")),)),
        f.CLAUSE_REF,
        SCOPED_QUOTE,
        span,
    )


def dispatch(
    intent: int,
    observation: Observation,
    read_as: AttributionKind,
    *,
    rule: str = "registered-stop-reason",
    number: int = 1,
    segment: int = 1,
    shown: Sequence[str] = (),
) -> Dispatch:
    """One dispatch logged at ``intent``; usage and cost are the priced ones exactly when a
    complete response arrived, and its outcome follows its intent unless none was recorded."""
    answered = isinstance(observation, CompleteResponse)
    return Dispatch(
        number=number,
        segment=segment,
        intent_position=intent,
        outcome_position=None if isinstance(observation, NoRecordedOutcome) else intent + 1,
        request=REQUEST,
        input_reads=tuple(OperationId(read) for read in shown),
        observation=observation,
        attribution=Attribution(read_as, rule),
        usage=ReportedUsage(REPORTED) if answered else None,
        cost=PRICED if answered else None,
        zero_cost_rule=None,
        allocation=ALLOCATION,
        allocation_tokens=ALLOCATION_TOKENS,
    )


def answered(
    call: str,
    intent: int,
    answer: Answer,
    *,
    stop_reason: str = "end_turn",
    segment: int = 1,
    shown: Sequence[str] = (),
) -> ModelCall:
    """A call answered on its first dispatch, carrying ``answer``."""
    sent = dispatch(
        intent,
        CompleteResponse(stop_reason, 840, 0),
        AttributionKind.BEHAVIOUR,
        segment=segment,
        shown=shown,
    )
    return ModelCall(ModelCallId(call), ROLE, (sent,), answer)


def prefetched(position: int = 1) -> Operation:
    """The prefetch's read of the tickets, which came back empty."""
    return Operation(
        OperationId(f"op-{position}"),
        PrefetchOrigin(),
        "work_items",
        Source.JIRA,
        {},
        RecordsOutcome(()),
        position,
    )


def asked(operation: str, call: str, position: int, outcome: object = None) -> Operation:
    """A ticket read the model call ``call`` asked for, logged at ``position``."""
    return Operation(
        OperationId(operation),
        ModelOrigin(ModelCallId(call)),
        "work_item",
        Source.JIRA,
        {"id": "ticket_042"},
        AbsentOutcome() if outcome is None else outcome,  # type: ignore[arg-type]
        position,
    )


def one_segment(last_offset_ms: int = 9_000) -> Timing:
    return Timing(
        (Segment(1, REVISION, last_offset_ms, True),),
        ADMITTED,
        ADMITTED + timedelta(milliseconds=last_offset_ms),
        None,
        None,
    )


def settled(calls: Sequence[ModelCall]) -> Reservation:
    """The reservation as a ledger settles it: reconciled when every send was priced whole,
    kept with the reason otherwise."""
    dispatches = [d for call in calls for d in call.dispatches]
    amount = ALLOCATION * len(dispatches)
    sent = [d for d in dispatches if d.sends is not Sends.NONE]
    if any(d.sends is Sends.UNRESOLVED for d in sent):
        return Reservation(amount, ReservationState.KEPT, KeptReason.UNRESOLVED_DISPATCH, 7)
    if any(d.cost is None or not d.cost.complete for d in sent):
        return Reservation(amount, ReservationState.KEPT, KeptReason.USAGE_INCOMPLETE, 7)
    return Reservation(amount, ReservationState.RECONCILED, None, 7)


def automatic(claims: Sequence[Claim], composition: Composition) -> Approval:
    """The automatic policy's approval over the review payload of ``claims``."""
    return Approval(
        ApprovalState.APPROVED, Approver.AUTOMATIC, review_payload_digest(claims, composition)
    )


NOT_REQUESTED = Approval(ApprovalState.NOT_REQUESTED, None, None)


def export(
    calls: Sequence[ModelCall],
    operations: Sequence[Operation] = (),
    *,
    claims: Sequence[Claim] = (),
    composition: Composition = RULES,
    failure: Failure | None = None,
    abandonment: Abandonment | None = None,
    timing: Timing | None = None,
    approval: Approval | None = None,
) -> RunExport:
    """An agent's export around ``calls``. The attempt completed unless ``failure`` says how
    it failed; it is approved automatically when it completed and requested no approval when
    it failed, unless ``approval`` says otherwise."""
    if approval is None:
        approval = NOT_REQUESTED if failure is not None else automatic(claims, composition)
    record = RunRecord(
        observed_condition=RunCondition.all_reachable(),
        outage=OutageAssignment(frozenset(), DIGEST),
        corpus_level="base",
        preregistration_commit=COMMIT,
        attribution_table=DIGEST,
        model_configurations=(
            (ROLE, CallConfiguration("eu.model", (CallSetting("temperature", 0),))),
        ),
        pricing_selections=((ROLE, SELECTION),),
        prompt_digests=((ROLE, "system", DIGEST),),
        tool_surface_digests=((ROLE, DIGEST),),
        system=System(SystemKind.AGENT, "reference"),
        retrieval=Retrieval(RetrievalKind.FULL_TEXT, None),
        prefetch_rule=PrefetchRule("prefetch-v1", DIGEST),
        caps=Caps(20, 100_000, 2, 5_000, "input_output"),
        status=TerminalStatus.COMPLETED if failure is None else TerminalStatus.FAILED,
        failure=failure,
        abandonment=abandonment,
        timing=timing if timing is not None else one_segment(),
        usage=aggregate_usage(calls),
        cost=run_cost(calls),
        reservation=settled(calls),
        approval=approval,
        pricing=BASIS,
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-12",
        1,
        CONTEXT,
        record,
        RunTrace(tuple(calls), tuple(operations), tuple(claims), composition),
    )


def batch(*entries: Admitted | Refused | RefusedInput) -> FactBatch:
    return ParsedBatch(tuple(entries))


# --- The twelve ------------------------------------------------------------------------------


def facts_beside_tools() -> RunExport:
    """One answer holding text, a tool call that became a read, and a fact batch in its own
    content: the shape format 1's one outcome per call had no value for."""
    answer = Answer(
        True,
        (ToolCall("tu_1", "work_item", AsOperation(OperationId("op-2"))),),
        (batch(Admitted(SKILL)),),
    )
    call = answered("call-1", 2, answer, stop_reason="tool_use", shown=("op-1",))
    return export((call,), (prefetched(), asked("op-2", "call-1", 4)))


def malformed_batch() -> RunExport:
    """A fact payload the parser could not read: kept as it arrived, beside who refused it."""
    payload = '{"facts": [{"predicate": "has_skill", "subject": "emp_023", "va'
    call = answered("call-1", 2, Answer(False, (), (MalformedBatch(payload, PARSER),)))
    return export((call,), (prefetched(),))


def refused_fact() -> RunExport:
    """A parsed batch of three entries: an input no stated fact can be made of, kept as raw
    text and never as the fact; a fact a gate refused; a fact admitted."""
    entry = {"predicate": "has_skill", "subject": "emp_023", "value": 7, "carrier": "comment_001"}
    unreadable = RefusedInput(
        canonical_json(entry), FactRefusal.UNDECODABLE, "has_skill: a skill id, got 7"
    )
    misquoted = StatedFact(
        PredicateName.HAS_SKILL, f.DENIZ_REF, "kafka", f.COMMENT_REF, "I led the Kafka migration"
    )
    refused = Refused(misquoted, FactRefusal.QUOTE_NOT_IN_CARRIER, "the comment says 'ran'")
    call = answered("call-1", 2, Answer(False, (), (batch(unreadable, refused, Admitted(SKILL)),)))
    return export((call,), (prefetched(),))


def cut_call() -> RunExport:
    """A response cut at the output limit arrives holding a tool call with empty arguments;
    only its stop reason says the call was never made whole, and it is not dispatched."""
    cut = ToolCall("tu_1", "employee", Undispatched(UndispatchedReason.STOP_REASON_NOT_TOOL_USE))
    call = answered("call-1", 2, Answer(False, (cut,), ()), stop_reason="max_tokens")
    return export((call,), (prefetched(),))


def handled_fact_tool() -> RunExport:
    """A fact-submission tool: the harness handles the call itself, as a fact batch, and no
    source is asked, so no operation exists for it."""
    answer = Answer(
        False,
        (ToolCall("tu_1", "state_facts", HandledAsBatch(0)),),
        (batch(Admitted(SKILL)),),
    )
    call = answered("call-1", 2, answer, stop_reason="tool_use")
    return export((call,), (prefetched(),))


def unresolved_then_answered() -> RunExport:
    """A process killed after a dispatch's intent was logged, and the recovery's second
    dispatch that answered: one logical call, two dispatches, the first zero sends or one."""
    lost = dispatch(2, NoRecordedOutcome(), AttributionKind.UNRESOLVED, rule="no-outcome")
    again = dispatch(
        4, CompleteResponse("end_turn", 840, 0), AttributionKind.BEHAVIOUR, number=2, segment=2
    )
    call = ModelCall(ModelCallId("call-1"), ROLE, (lost, again), Answer(True, (), ()))
    timing = Timing(
        (Segment(1, REVISION, 3_000, False), Segment(2, REVISION, 2_500, True)),
        ADMITTED,
        ADMITTED + timedelta(minutes=4),
        None,
        None,
    )
    return export((call,), (prefetched(),), timing=timing)


NOVA_CUT = "Model produced invalid sequence as part of ToolUse"


def nova_signature_beside_another() -> RunExport:
    """Two model errors of one service code. The first carries the evidenced signature of a
    tool call cut at the output limit and is read as the model's behaviour; the second
    matches no rule and is infrastructure, then re-dispatched by the harness and answered."""
    cut = ModelCall(
        ModelCallId("call-1"),
        ROLE,
        (
            dispatch(
                2,
                ServiceError(424, "ModelErrorException", None, NOVA_CUT, 0, "req-nova-1"),
                AttributionKind.BEHAVIOUR,
                rule="nova-cut-tool-use",
            ),
        ),
        None,
    )
    other = ModelCall(
        ModelCallId("call-2"),
        ROLE,
        (
            dispatch(
                4,
                ServiceError(
                    424,
                    "ModelErrorException",
                    None,
                    "Model timed out mid-generation",
                    0,
                    "req-nova-2",
                ),
                AttributionKind.INFRASTRUCTURE,
                rule="unmatched",
            ),
            dispatch(6, CompleteResponse("end_turn", 840, 0), AttributionKind.BEHAVIOUR, number=2),
        ),
        Answer(True, (), ()),
    )
    return export((cut, other), (prefetched(),))


def recovered_attempt() -> RunExport:
    """An attempt whose first process was killed after the prefetch and whose second finished
    it: two segments, the first with an unknown tail."""
    call = answered("call-1", 2, Answer(True, (), ()), segment=2, shown=("op-1",))
    timing = Timing(
        (Segment(1, REVISION, 1_200, False), Segment(2, REVISION, 6_000, True)),
        ADMITTED,
        ADMITTED + timedelta(minutes=10),
        None,
        None,
    )
    return export((call,), (prefetched(),), timing=timing)


def abandoned_attempt() -> RunExport:
    """An attempt that requested an approval nobody delivered and that an operator then
    abandoned: a decision with its authority and the ownership generation it fenced."""
    call = answered("call-1", 2, Answer(True, (), ()))
    failure = Failure(
        FailureCategory.INFRASTRUCTURE,
        HarnessSite(HarnessSiteName.ABANDONED),
        "no worker resumed the attempt",
    )
    timing = Timing(
        (Segment(1, REVISION, 5_000, False),),
        ADMITTED,
        ADMITTED + timedelta(days=2),
        Stamp(1, 4_800, 4),
        None,
    )
    waiting = Approval(ApprovalState.REQUESTED_UNAPPROVED, None, review_payload_digest((), RULES))
    return export(
        (call,),
        (prefetched(),),
        failure=failure,
        abandonment=Abandonment("operator", 3),
        timing=timing,
        approval=waiting,
    )


def approval_wait_across_restart() -> RunExport:
    """The approval requested at 7,000 ms of a first segment that lasted to 7,900; a second
    segment that began and was killed inside the wait; the resume at 50 ms of the third, which
    ran to 2,050."""
    call = answered("call-1", 2, Answer(True, (), ()))
    timing = Timing(
        (
            Segment(1, REVISION, 7_900, True),
            Segment(2, REVISION, 600, False),
            Segment(3, REVISION, 2_050, True),
        ),
        ADMITTED,
        ADMITTED + timedelta(hours=2),
        Stamp(1, 7_000, 4),
        Stamp(3, 50, 5),
    )
    return export((call,), (prefetched(),), timing=timing)


def wrong_scope_beside_unplaced() -> RunExport:
    """One requirement stated twice with two target spans. The sentence is about the ticket;
    the first statement names the meeting instead, a title the run read, and is placed on
    the meeting: a binding can be wrong and is still a binding. The second names work the
    run never read and stays unplaced."""
    on_the_meeting, unread = requirement(f.MEETING.title), requirement("Ledger cutover")
    call = answered(
        "call-1", 2, Answer(False, (), (batch(Admitted(on_the_meeting), Admitted(unread)),))
    )
    composition = Composition(
        ClaimAuthor.RULES,
        RULES.policy,
        (
            RequirementPlacement(
                on_the_meeting,
                SpanPlacement(PlacementState.PLACED, artifact=event_ref(f.MEETING.id)),
            ),
            RequirementPlacement(unread, SpanPlacement(PlacementState.UNPLACED)),
        ),
        (),
    )
    return export((call,), (prefetched(),), composition=composition)


def first_tool_call_ends_the_attempt() -> RunExport:
    """An answer asking for two reads. The first returned a record the adapter could not
    translate, a defect that ended the attempt there; under sequential dispatch the second
    was never reached, and the terminal event anchored at the first is the evidence."""
    answer = Answer(
        False,
        (
            ToolCall("tu_1", "work_item", AsOperation(OperationId("op-2"))),
            ToolCall("tu_2", "employee", Undispatched(UndispatchedReason.ATTEMPT_ENDED_FIRST)),
        ),
        (),
    )
    call = answered("call-1", 2, answer, stop_reason="tool_use")
    malformed = asked("op-2", "call-1", 4, DefectOutcome(Source.JIRA, "LIA-42", "no world id"))
    failure = Failure(
        FailureCategory.DEFECT, OperationSite(OperationId("op-2")), "a malformed record"
    )
    return export((call,), (prefetched(), malformed), failure=failure)


def tool_result_lost() -> RunExport:
    """A read the model asked for, in an attempt killed before any result was logged and then
    abandoned: nothing shows the read never ran, so it is unresolved, not undispatched."""
    answer = Answer(False, (ToolCall("tu_1", "work_item", UnresolvedToolCall()),), ())
    call = answered("call-1", 2, answer, stop_reason="tool_use")
    failure = Failure(
        FailureCategory.INFRASTRUCTURE,
        HarnessSite(HarnessSiteName.ABANDONED),
        "the worker died and the attempt was abandoned",
    )
    timing = Timing(
        (Segment(1, REVISION, 2_000, False),), ADMITTED, ADMITTED + timedelta(hours=1), None, None
    )
    return export(
        (call,),
        (prefetched(),),
        failure=failure,
        abandonment=Abandonment("recovery", 2),
        timing=timing,
    )


FIXTURES: dict[str, Callable[[], RunExport]] = {
    "facts beside tools in one answer": facts_beside_tools,
    "a malformed batch": malformed_batch,
    "a refused fact that cannot construct a value": refused_fact,
    "a cut call": cut_call,
    "a handled fact-submission tool": handled_fact_tool,
    "an unresolved dispatch followed by an answered one": unresolved_then_answered,
    "the Nova signature beside another model error": nova_signature_beside_another,
    "a recovered attempt": recovered_attempt,
    "an abandoned attempt": abandoned_attempt,
    "an approval wait across a restart": approval_wait_across_restart,
    "a wrong scope beside an unplaced one": wrong_scope_beside_unplaced,
    "a multi-tool answer whose first call ends the attempt": first_tool_call_ends_the_attempt,
    "a tool call whose result was lost before it was logged": tool_result_lost,
}
"""Each case by its name in the ruling; the eighth is two exports, a paused attempt having
none."""
