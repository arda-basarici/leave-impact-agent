"""The hand-built exports the export format is accepted on, one per case an earlier format
could not state.

Test infrastructure, built on ``core`` alone so that every later group can import it: the
composer's tests, the evaluator's fact-stage measures and the event log's export reader
all need exports of these shapes before any harness produces one. Each function returns
one whole ``RunExport`` of an agent's attempt on the stated-fact fixture's small world.
The first twelve cases are the contract step's (its ruling on time, answers, tool calls
and approval), the cases format 1 had no value for:

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

Three more are the event log step's, the histories format 2 could not hold:

13. an attempt admitted and never claimed, closed by an abandon command
14. a recorded defect an operator's command finalized
15. a request whose input bound was never established

The provenance around each is inert and the same: one role, one priced selection, the
usage and the cumulative cost summed from the dispatches as a harness sums them, the
reservation settled as a ledger settles it, and every dispatch resting on its call's one
counting operation, a re-dispatch reusing the count. Positions are on a scale of ten: slot
``n`` of a case is position ``10 n``, so a call's count has its two positions just before
its first intent. What a case is about is in its own function.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta

from leaveimpact.agent.fact_entries import refused_by
from leaveimpact.agent.log_events import CountKey
from leaveimpact.agent.log_events import count_id as rendered_count_id
from leaveimpact.core import (
    EXPORT_FORMAT_VERSION,
    UNRESOLVED_RULE,
    Abandonment,
    AbandonmentReason,
    AbsentMeaning,
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
    CountClientError,
    Counted,
    CountingOperation,
    CountingOperationId,
    CountResult,
    CountServiceError,
    DefectOutcome,
    Dispatch,
    Document,
    DocumentKind,
    DocumentSection,
    Entity,
    EstablishedBound,
    FactRefusal,
    Failure,
    FailureCategory,
    HandledAsBatch,
    HarnessRevision,
    HarnessSite,
    HarnessSiteName,
    InputBoundSite,
    KeptReason,
    MalformedBatch,
    ModelCall,
    ModelCallId,
    ModelOrigin,
    NoRecordedOutcome,
    Observed,
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
    RecordOutcome,
    RecordsOutcome,
    Refused,
    RefusedBy,
    RefusedInput,
    RegisteredInputBound,
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
    attribution_table_digest,
    event_ref,
    review_payload_digest,
    run_cost,
)
from leaveimpact.core.attribution import (
    AttributionRow,
    AttributionTable,
    Match,
    ObservationKind,
    RedispatchPolicy,
)
from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion, clause_id, document_id, skill_id
from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.model_calls import FactBatch, Observation
from leaveimpact.core.run_trace import ClientErrorKind
from tests.unit import stated_fixture as f

DIGEST = "a" * 64
COMMIT = "b" * 40
ROLE = "investigator"
SELECTION = PricingSelection("model-a", "eu-central-1", "on_demand")
ZERO = AbsentMeaning.ZERO
"""The cache counters are omitted exactly when a call had no token of the class, as the
spike proved for both supported families; so a usage without them still prices whole."""
BASIS = PricingBasis(
    DIGEST,
    "USD",
    date(2026, 9, 1),
    (
        PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_100_000),
        PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_500_000),
        PricingRow(
            "model-a", "eu-central-1", "on_demand", "cache_read_input_tokens", 110_000, ZERO
        ),
        PricingRow(
            "model-a", "eu-central-1", "on_demand", "cache_write_input_tokens", 1_375_000, ZERO
        ),
    ),
)
"""Every class priced, so the money worst case can be computed over these exports: the
cache write is the dearest input-side rate."""
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
METHOD = RegisteredInputBound("provider_count", 1)
COUNTING_MODEL = "model-a-base"
"""The identifier the count is asked of: the base model behind the ``eu.`` profile."""
INPUT_BOUND = 4_096
OUTPUT_MAXIMUM = 512
ALLOCATION_TOKENS = INPUT_BOUND + OUTPUT_MAXIMUM
"""The worst case one dispatch is counted for against the token cap: its input bound and
its output maximum."""
ALLOCATION = INPUT_BOUND * 1_375_000 + OUTPUT_MAXIMUM * 5_500_000
"""The money worst case of one dispatch: the bound at the dearest input-side rate and the
output maximum at the output rate, 8,448,000,000 pico-dollars."""
LEDGER_REVISION = 7
RULES = Composition(ClaimAuthor.RULES, ComposingPolicy("stated-fact-composer", DIGEST), (), ())
PARSER = refused_by()
"""The fact parser and its schema, as the reader derives a batch under them."""
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


def count_id(call: str) -> CountingOperationId:
    """The identifier of ``call``'s one count: its reuse key rendered, as the log renders it."""
    return rendered_count_id(CountKey(METHOD, COUNTING_MODEL, request_digest(call), 1))


def request_digest(call: str) -> str:
    """The digest of ``call``'s request: one per call, since two calls never ask the same
    request and a count is reused under the digest."""
    return hashlib.sha256(call.encode()).hexdigest()


def request_of(call: str) -> RequestIdentity:
    return RequestIdentity(request_digest(call), "Converse", "eu.model", "eu-central-1", None)


def bound_of(call: str) -> EstablishedBound:
    """The bound every dispatch of ``call`` rests on: the provider's count of its request."""
    return EstablishedBound(
        METHOD, COUNTING_MODEL, request_digest(call), INPUT_BOUND, count_id(call)
    )


def counted(call: str, position: int, *, segment: int = 1) -> CountingOperation:
    """The one successful count of ``call``'s request, in the two positions before
    ``position``, where its first intent is logged."""
    return CountingOperation(
        count_id(call),
        METHOD,
        COUNTING_MODEL,
        request_digest(call),
        segment,
        position - 2,
        position - 1,
        Counted(INPUT_BOUND, f"req-{count_id(call)}", 100),
        CountResult.COUNTED,
    )


def counts_of(calls: Sequence[ModelCall]) -> tuple[CountingOperation, ...]:
    """One count per call, each just before the call's first intent."""
    return tuple(
        counted(call.id, first.intent_position, segment=first.segment)
        for call in calls
        for first in (call.dispatches[0],)
    )


def dispatch(
    position: int,
    observation: Observation,
    read_as: AttributionKind,
    *,
    rule: str = "registered-stop-reason",
    number: int = 1,
    segment: int = 1,
    shown: Sequence[str] = (),
    call: str = "call-1",
) -> Dispatch:
    """One dispatch of ``call`` whose intent is logged at ``position``; usage and cost are
    the priced ones exactly when a complete response arrived, and its outcome follows its
    intent unless none was recorded."""
    answered = isinstance(observation, CompleteResponse)
    return Dispatch(
        number=number,
        segment=segment,
        intent_position=position,
        outcome_position=None if isinstance(observation, NoRecordedOutcome) else position + 1,
        request=request_of(call),
        input_reads=tuple(OperationId(read) for read in shown),
        observation=observation,
        attribution=Attribution(read_as, rule),
        usage=ReportedUsage(REPORTED) if answered else None,
        cost=PRICED if answered else None,
        zero_cost_rule=None,
        allocation=ALLOCATION,
        allocation_tokens=ALLOCATION_TOKENS,
        bound=bound_of(call),
        output_maximum=OUTPUT_MAXIMUM,
    )


def answered(
    call: str,
    position: int,
    answer: Answer,
    *,
    stop_reason: str = "end_turn",
    segment: int = 1,
    shown: Sequence[str] = (),
) -> ModelCall:
    """A call answered on its first dispatch, logged at ``position``, carrying ``answer``."""
    sent = dispatch(
        position,
        CompleteResponse(stop_reason, 840, 0),
        AttributionKind.BEHAVIOUR,
        segment=segment,
        shown=shown,
        call=call,
    )
    return ModelCall(ModelCallId(call), ROLE, (sent,), answer)


def prefetched(
    position: int = 3,
    ordinal: int = 1,
    tool: str = "work_items",
    source: Source = Source.JIRA,
    records: Sequence[Observed[Entity]] = (),
) -> Operation:
    """The prefetch's ``ordinal``-th read, of ``tool``, returning ``records``, logged at
    ``position``; by default the read of the tickets, which came back empty."""
    return Operation(
        OperationId(f"prefetch/{ordinal}"),
        PrefetchOrigin(),
        tool,
        source,
        {},
        RecordsOutcome(tuple(records)),
        position,
    )


PEOPLE: tuple[Observed[Entity], ...] = (
    Observed[Entity](f.ALICE, Source.FRAPPE),
    Observed[Entity](f.DENIZ, Source.FRAPPE),
)
TICKETS: tuple[Observed[Entity], ...] = (Observed[Entity](f.TICKET, Source.JIRA),)
"""The reads behind an admitted skill statement: the people, and the ticket holding Deniz's
comment the statement is read from. A fact is admitted over the reads logged before its
answer, so a history whose answer admits the statement holds these."""

SCOPED_RUNBOOK = Document(
    document_id(3),
    "Payments runbook",
    DocumentKind.RUNBOOK,
    date(2026, 1, 1),
    (DocumentSection(clause_id(11), SCOPED_QUOTE),),
)
"""The runbook whose one section is the scoped sentence, so a requirement quoting it is
admitted on its carrier."""


def read_document(position: int, ordinal: int, document: Document) -> Operation:
    """The prefetch's read of ``document`` by its id, logged at ``position``."""
    held = Observed[Entity](document, Source.CORPUS)
    return Operation(
        OperationId(f"prefetch/{ordinal}"),
        PrefetchOrigin(),
        "document",
        Source.CORPUS,
        {"id": document.id},
        RecordOutcome(held),
        position,
    )


def asked(tool_call: str, call: str, position: int, outcome: object = None) -> Operation:
    """A ticket read the model call ``call`` asked for in ``tool_call``, logged at
    ``position``."""
    return Operation(
        OperationId(f"{call}/{tool_call}"),
        ModelOrigin(ModelCallId(call)),
        "work_item",
        Source.JIRA,
        {"id": "ticket_042"},
        AbsentOutcome() if outcome is None else outcome,  # type: ignore[arg-type]
        position,
    )


def stamps(
    request: int, *, segment: int = 1, last_offset_ms: int = 9_000
) -> tuple[Stamp, Stamp]:
    """The worker's two approval stamps of a completed attempt: the request at ``request``
    and the resume two positions later (the approval sits between), both inside the segment's
    last 300 ms."""
    return (
        Stamp(segment, last_offset_ms - 300, request),
        Stamp(segment, last_offset_ms - 200, request + 2),
    )


def one_segment(last_offset_ms: int = 9_000, request: int | None = None) -> Timing:
    """One segment with its end recorded; with ``request`` the approval's two stamps."""
    requested, resumed = (
        (None, None) if request is None else stamps(request, last_offset_ms=last_offset_ms)
    )
    return Timing(
        (Segment(1, REVISION, last_offset_ms, True),),
        ADMITTED,
        ADMITTED + timedelta(milliseconds=last_offset_ms),
        requested,
        resumed,
    )


def settled(calls: Sequence[ModelCall]) -> Reservation:
    """The reservation as a ledger settles it: reconciled when every send was priced whole,
    kept with the reason otherwise; charged the observed cost of every dispatch priced whole
    and the allocation of every other one that was sent."""
    dispatches = [d for call in calls for d in call.dispatches]
    amount = ALLOCATION * len(dispatches)
    sent = [d for d in dispatches if d.sends is not Sends.NONE]
    charged = sum(
        d.cost.pico_usd if d.cost is not None and d.cost.complete else ALLOCATION for d in sent
    )
    if any(d.sends is Sends.UNRESOLVED for d in sent):
        reason = KeptReason.UNRESOLVED_DISPATCH
    elif any(d.cost is None or not d.cost.complete for d in sent):
        reason = KeptReason.USAGE_INCOMPLETE
    else:
        return Reservation(amount, ReservationState.RECONCILED, None, LEDGER_REVISION, charged)
    return Reservation(amount, ReservationState.KEPT, reason, LEDGER_REVISION, charged)


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
    request: int | None = None,
    approval: Approval | None = None,
    counting_operations: Sequence[CountingOperation] | None = None,
    reservation: Reservation | None = None,
) -> RunExport:
    """An agent's export around ``calls``. The attempt completed unless ``failure`` says how
    it failed; it is approved automatically when it completed, its request stamped at
    position ``request`` and its resume two later, and requested no approval when it
    failed, unless ``approval`` says otherwise. Each call rests on one successful count
    unless ``counting_operations`` says otherwise, and the reservation is settled over the
    calls unless ``reservation`` says otherwise."""
    if approval is None:
        approval = NOT_REQUESTED if failure is not None else automatic(claims, composition)
    record = RunRecord(
        observed_condition=RunCondition.all_reachable(),
        outage=OutageAssignment(frozenset(), DIGEST),
        corpus_level="base",
        preregistration_commit=COMMIT,
        attribution_table=TABLE_DIGEST,
        model_configurations=(
            (
                ROLE,
                CallConfiguration(
                    "eu.model",
                    (CallSetting("max_tokens", OUTPUT_MAXIMUM), CallSetting("temperature", 0)),
                ),
            ),
        ),
        pricing_selections=((ROLE, SELECTION),),
        prompt_digests=((ROLE, "system", DIGEST),),
        tool_surface_digests=((ROLE, DIGEST),),
        system=System(SystemKind.AGENT, "reference"),
        retrieval=Retrieval(RetrievalKind.FULL_TEXT, None),
        prefetch_rule=PrefetchRule("prefetch-v1", DIGEST),
        caps=Caps(20, 100_000, 2, 5_000, "input_plus_output_cached_included", METHOD),
        status=TerminalStatus.COMPLETED if failure is None else TerminalStatus.FAILED,
        failure=failure,
        abandonment=abandonment,
        timing=timing if timing is not None else one_segment(request=request),
        usage=aggregate_usage(calls),
        cost=run_cost(calls),
        reservation=settled(calls) if reservation is None else reservation,
        approval=approval,
        pricing=BASIS,
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-12",
        1,
        CONTEXT,
        record,
        RunTrace(
            tuple(calls),
            tuple(operations),
            tuple(claims),
            composition,
            counts_of(calls) if counting_operations is None else tuple(counting_operations),
            None,
        ),
    )


def batch(*entries: Admitted | Refused | RefusedInput) -> FactBatch:
    return ParsedBatch(tuple(entries))


def evidence(*, document: Document | None = None) -> tuple[Operation, ...]:
    """The prefetch reads of a history whose answer admits a statement: the ticket read every
    fixture opens with, here returning the ticket, the people, the ticket again with Deniz's
    comment, and ``document`` when a requirement is read from it; at positions 3 to 6. The
    second ticket read is a history no prefetch produces, kept so the other fixtures' first
    read stayed as it was; the two agree, since the transition now stops a run at an
    enumeration that omits a record another read returned (the graph step, amendment 1)."""
    reads = [
        prefetched(3, records=TICKETS),
        prefetched(4, 2, "employees", Source.FRAPPE, PEOPLE),
        prefetched(5, 3, "work_items", Source.JIRA, TICKETS),
    ]
    if document is not None:
        reads.append(read_document(6, 4, document))
    return tuple(reads)


# --- The contract step's twelve ---------------------------------------------------------------


def facts_beside_tools() -> RunExport:
    """One answer holding text, a tool call that became a read, and a fact batch in its own
    content: the shape format 1's one outcome per call had no value for."""
    answer = Answer(
        True,
        (ToolCall("tu_1", "work_item", AsOperation(OperationId("call-1/tu_1"))),),
        (batch(Admitted(SKILL)),),
    )
    call = answered("call-1", 8, answer, stop_reason="tool_use", shown=("prefetch/1",))
    # The read returns the ticket the enumeration returned: an absent answer would be the
    # source contradicting itself, a stop since the graph step (amendment 1).
    read = asked("tu_1", "call-1", 10, RecordOutcome(TICKETS[0]))
    return export((call,), (*evidence(), read), request=11)


def malformed_batch() -> RunExport:
    """A fact payload the parser could not read: kept as it arrived, beside who refused it."""
    payload = '{"facts": [{"predicate": "has_skill", "subject": "emp_023", "va'
    call = answered("call-1", 6, Answer(False, (), (MalformedBatch(payload, PARSER),)))
    return export((call,), (prefetched(),), request=8)


def refused_fact() -> RunExport:
    """A parsed batch of three entries: an input no stated fact can be made of, kept as raw
    text and never as the fact; a fact a gate refused; a fact admitted."""
    entry = {
        "predicate": "has_skill",
        "subject": f.DENIZ_REF.id,
        "value": 7,
        "carrier": f.COMMENT_REF.id,
        "quote": f.REMARK,
    }
    unreadable = RefusedInput(
        canonical_json(entry), FactRefusal.UNDECODABLE, "value is text, got int"
    )
    misquoted = StatedFact(
        PredicateName.HAS_SKILL, f.DENIZ_REF, "kafka", f.COMMENT_REF, "I led the Kafka migration"
    )
    refused = Refused(
        misquoted,
        FactRefusal.QUOTE_NOT_IN_CARRIER,
        f"the quote is not a substring of {f.COMMENT_REF.id} as read",
    )
    call = answered("call-1", 8, Answer(False, (), (batch(unreadable, refused, Admitted(SKILL)),)))
    return export((call,), evidence(), request=10)


def cut_call() -> RunExport:
    """A response cut at the output limit arrives holding a tool call with empty arguments;
    only its stop reason says the call was never made whole, and it is not dispatched."""
    cut = ToolCall("tu_1", "employee", Undispatched(UndispatchedReason.STOP_REASON_NOT_TOOL_USE))
    call = answered("call-1", 6, Answer(False, (cut,), ()), stop_reason="max_tokens")
    return export((call,), (prefetched(),), request=8)


def handled_fact_tool() -> RunExport:
    """A fact-submission tool: the harness handles the call itself, as a fact batch, and no
    source is asked, so no operation exists for it."""
    answer = Answer(
        False,
        (ToolCall("tu_1", "state_facts", HandledAsBatch(0)),),
        (batch(Admitted(SKILL)),),
    )
    call = answered("call-1", 8, answer, stop_reason="tool_use")
    return export((call,), evidence(), request=10)


def unresolved_then_answered() -> RunExport:
    """A process killed after a dispatch's intent was logged, and the recovery's second
    dispatch that answered: one logical call, two dispatches, the first zero sends or one."""
    lost = dispatch(6, NoRecordedOutcome(), AttributionKind.UNRESOLVED, rule=UNRESOLVED_RULE)
    # The same request asked again: its count is durable and reused, nothing is counted.
    again = dispatch(
        8, CompleteResponse("end_turn", 840, 0), AttributionKind.BEHAVIOUR, number=2, segment=2
    )
    call = ModelCall(ModelCallId("call-1"), ROLE, (lost, again), Answer(True, (), ()))
    timing = Timing(
        (Segment(1, REVISION, 3_000, False), Segment(2, REVISION, 2_500, True)),
        ADMITTED,
        ADMITTED + timedelta(minutes=4),
        *stamps(10, segment=2, last_offset_ms=2_500),
    )
    return export((call,), (prefetched(),), timing=timing)


NOVA_CUT = "Model produced invalid sequence as part of ToolUse"

TABLE = AttributionTable(
    (
        AttributionRow(
            "registered-stop-reason",
            Match(ObservationKind.COMPLETE_RESPONSE),
            AttributionKind.BEHAVIOUR,
        ),
        AttributionRow(
            "stream", Match(ObservationKind.BROKEN_STREAM), AttributionKind.INFRASTRUCTURE
        ),
        AttributionRow(
            "nova-cut-tool-use",
            Match(ObservationKind.SERVICE_ERROR, message_signatures=frozenset({NOVA_CUT})),
            AttributionKind.BEHAVIOUR,
        ),
        AttributionRow(
            "unmatched",
            Match(ObservationKind.SERVICE_ERROR),
            AttributionKind.INFRASTRUCTURE,
            redispatch=True,
            unmatched=True,
        ),
        AttributionRow(
            "gave_up", Match(ObservationKind.CLIENT_ERROR), AttributionKind.INFRASTRUCTURE
        ),
        AttributionRow(
            "never_sent",
            Match(ObservationKind.REFUSED_BEFORE_SEND),
            AttributionKind.INFRASTRUCTURE,
        ),
    )
)
"""A table holding every rule the fixtures' dispatches name, so a check that needs the
registered table can read them."""

TABLE_DIGEST = attribution_table_digest(TABLE)
"""What every fixture's record names its attributions' table by: the table above, as a
history's admission freezes it."""

POLICY = RedispatchPolicy(3, 0)
"""A re-dispatch policy every fixture conforms to: no call takes more than two dispatches,
and the input-bound fixture's three counting requests consume exactly this maximum."""


def nova_signature_beside_another() -> RunExport:
    """Two model errors of one service code. The first carries the evidenced signature of a
    tool call cut at the output limit and is read as the model's behaviour; the second
    matches no rule and is infrastructure, then re-dispatched by the harness and answered."""
    cut = ModelCall(
        ModelCallId("call-1"),
        ROLE,
        (
            dispatch(
                6,
                ServiceError(424, "ModelErrorException", None, NOVA_CUT, 0, "req-nova-1"),
                AttributionKind.BEHAVIOUR,
                rule="nova-cut-tool-use",
                call="call-1",
            ),
        ),
        None,
    )
    other = ModelCall(
        ModelCallId("call-2"),
        ROLE,
        (
            dispatch(
                10,
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
                call="call-2",
            ),
            dispatch(
                12,
                CompleteResponse("end_turn", 840, 0),
                AttributionKind.BEHAVIOUR,
                number=2,
                call="call-2",
            ),
        ),
        Answer(True, (), ()),
    )
    return export((cut, other), (prefetched(),), request=14)


def recovered_attempt() -> RunExport:
    """An attempt whose first process was killed after the prefetch and whose second finished
    it: two segments, the first with an unknown tail."""
    call = answered("call-1", 7, Answer(True, (), ()), segment=2, shown=("prefetch/1",))
    timing = Timing(
        (Segment(1, REVISION, 1_200, False), Segment(2, REVISION, 6_000, True)),
        ADMITTED,
        ADMITTED + timedelta(minutes=10),
        *stamps(9, segment=2, last_offset_ms=6_000),
    )
    return export((call,), (prefetched(),), timing=timing)


def abandoned_attempt() -> RunExport:
    """An attempt that requested an approval nobody delivered and that an operator then
    abandoned: a decision with its authority and the ownership generation it fenced. The
    request is the segment's last durable event, so its offset is the segment's last."""
    call = answered("call-1", 6, Answer(True, (), ()))
    failure = Failure(
        FailureCategory.INFRASTRUCTURE,
        HarnessSite(HarnessSiteName.ABANDONED),
        "no worker resumed the attempt",
    )
    timing = Timing(
        (Segment(1, REVISION, 4_800, False),),
        ADMITTED,
        ADMITTED + timedelta(days=2),
        Stamp(1, 4_800, 8),
        None,
    )
    waiting = Approval(ApprovalState.REQUESTED_UNAPPROVED, None, review_payload_digest((), RULES))
    return export(
        (call,),
        (prefetched(),),
        failure=failure,
        abandonment=Abandonment("operator", 1, AbandonmentReason.CANCELLED),
        timing=timing,
        approval=waiting,
    )


def approval_wait_across_restart() -> RunExport:
    """The approval requested at 7,000 ms of a first segment that lasted to 7,900; a second
    segment that began and was killed inside the wait, its start its only event, so its
    last offset is 0; the resume at 50 ms of the third, which ran to 2,050."""
    call = answered("call-1", 6, Answer(True, (), ()))
    timing = Timing(
        (
            Segment(1, REVISION, 7_900, True),
            Segment(2, REVISION, 0, False),
            Segment(3, REVISION, 2_050, True),
        ),
        ADMITTED,
        ADMITTED + timedelta(hours=2),
        Stamp(1, 7_000, 8),
        Stamp(3, 50, 13),
    )
    return export((call,), (prefetched(),), timing=timing)


def wrong_scope_beside_unplaced() -> RunExport:
    """One requirement stated twice with two target spans. The sentence is about the ticket;
    the first statement names the meeting instead, a title the run read, and is placed on
    the meeting: a binding can be wrong and is still a binding. The second names work the
    run never read and stays unplaced."""
    on_the_meeting, unread = requirement(f.MEETING.title), requirement("Ledger cutover")
    call = answered(
        "call-1", 9, Answer(False, (), (batch(Admitted(on_the_meeting), Admitted(unread)),))
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
    return export(
        (call,), evidence(document=SCOPED_RUNBOOK), composition=composition, request=11
    )


def first_tool_call_ends_the_attempt() -> RunExport:
    """An answer asking for two reads. The first returned a record the adapter could not
    translate, a defect that ended the attempt there; under sequential dispatch the second
    was never reached, and the terminal event anchored at the first is the evidence."""
    answer = Answer(
        False,
        (
            ToolCall("tu_1", "work_item", AsOperation(OperationId("call-1/tu_1"))),
            ToolCall("tu_2", "employee", Undispatched(UndispatchedReason.ATTEMPT_ENDED_FIRST)),
        ),
        (),
    )
    call = answered("call-1", 6, answer, stop_reason="tool_use")
    malformed = asked("tu_1", "call-1", 8, DefectOutcome(Source.JIRA, "LIA-42", "no world id"))
    failure = Failure(
        FailureCategory.DEFECT, OperationSite(OperationId("call-1/tu_1")), "a malformed record"
    )
    return export((call,), (prefetched(), malformed), failure=failure)


def tool_result_lost() -> RunExport:
    """A read the model asked for, in an attempt killed before any result was logged and then
    abandoned: nothing shows the read never ran, so it is unresolved, not undispatched."""
    answer = Answer(False, (ToolCall("tu_1", "work_item", UnresolvedToolCall()),), ())
    call = answered("call-1", 6, answer, stop_reason="tool_use")
    failure = Failure(
        FailureCategory.INFRASTRUCTURE,
        HarnessSite(HarnessSiteName.ABANDONED),
        "no worker resumed the attempt",
    )
    timing = Timing(
        (Segment(1, REVISION, 2_000, False),), ADMITTED, ADMITTED + timedelta(hours=1), None, None
    )
    return export(
        (call,),
        (prefetched(),),
        failure=failure,
        abandonment=Abandonment("recovery", 1, AbandonmentReason.INTERRUPTED),
        timing=timing,
    )


# --- The event log step's three ---------------------------------------------------------------


def never_claimed() -> RunExport:
    """Admitted at noon, claimed by nobody, closed by an operator's abandon command two hours
    later: no segment, so no active time and a complete timing; an empty trace; the
    reservation reconciled with nothing charged; the command fenced generation 0."""
    failure = Failure(
        FailureCategory.INFRASTRUCTURE,
        HarnessSite(HarnessSiteName.ABANDONED),
        "no worker claimed the attempt",
    )
    timing = Timing((), ADMITTED, ADMITTED + timedelta(hours=2), None, None)
    return export(
        (),
        failure=failure,
        abandonment=Abandonment("operator", 0, AbandonmentReason.CANCELLED),
        timing=timing,
        reservation=Reservation(
            ALLOCATION, ReservationState.RECONCILED, None, LEDGER_REVISION, 0
        ),
    )


def defect_finalized_by_operator() -> RunExport:
    """The first of two reads returned a record the adapter could not translate, a recorded
    defect; the worker died before writing the terminal event; an operator's abandon command
    closed the attempt the next day. The ending is the defect's, at the operation, and the
    command is who closed: an abandonment beside a failure at another site."""
    answer = Answer(
        False,
        (
            ToolCall("tu_1", "work_item", AsOperation(OperationId("call-1/tu_1"))),
            ToolCall("tu_2", "employee", Undispatched(UndispatchedReason.ATTEMPT_ENDED_FIRST)),
        ),
        (),
    )
    call = answered("call-1", 6, answer, stop_reason="tool_use")
    malformed = asked("tu_1", "call-1", 8, DefectOutcome(Source.JIRA, "LIA-42", "no world id"))
    failure = Failure(
        FailureCategory.DEFECT, OperationSite(OperationId("call-1/tu_1")), "a malformed record"
    )
    timing = Timing(
        (Segment(1, REVISION, 1_600, False),), ADMITTED, ADMITTED + timedelta(days=1), None, None
    )
    return export(
        (call,),
        (prefetched(), malformed),
        failure=failure,
        abandonment=Abandonment("operator", 1, AbandonmentReason.INTERRUPTED),
        timing=timing,
    )


def exhausted_count_id(ordinal: int) -> CountingOperationId:
    """The identifier of the ``ordinal``-th counting request for the one request the
    input-bound fixture never bounds."""
    return rendered_count_id(CountKey(METHOD, COUNTING_MODEL, DIGEST, ordinal))


def input_bound_exhausted() -> RunExport:
    """Three counting requests for the first model request, none a count: throttled, a
    client timeout, and one the worker died inside, which consumed the maximum all the same.
    A third segment found the maximum reached and wrote the failure, so the second's end
    was never recorded and the third's was. No dispatch was ever authorized; the attempt
    ended by infrastructure at the input bound, naming the last counting operation, and a
    new attempt is permitted after it."""
    throttled = CountingOperation(
        exhausted_count_id(1),
        METHOD,
        COUNTING_MODEL,
        DIGEST,
        1,
        4,
        5,
        CountServiceError(429, "ThrottlingException", "rate exceeded", "req-count-1", 80),
        CountResult.FAILED,
    )
    timed_out = CountingOperation(
        exhausted_count_id(2),
        METHOD,
        COUNTING_MODEL,
        DIGEST,
        1,
        6,
        7,
        CountClientError(ClientErrorKind.TIMEOUT, 30_000),
        CountResult.FAILED,
    )
    died_inside = CountingOperation(
        exhausted_count_id(3),
        METHOD,
        COUNTING_MODEL,
        DIGEST,
        2,
        9,
        None,
        NoRecordedOutcome(),
        CountResult.UNRESOLVED,
    )
    failure = Failure(
        FailureCategory.INFRASTRUCTURE,
        InputBoundSite(exhausted_count_id(3)),
        "the counting requests were exhausted without a count",
    )
    timing = Timing(
        (
            Segment(1, REVISION, 31_000, False),
            Segment(2, REVISION, 900, False),
            Segment(3, REVISION, 100, True),
        ),
        ADMITTED,
        ADMITTED + timedelta(minutes=5),
        None,
        None,
    )
    return export(
        (),
        (prefetched(),),
        failure=failure,
        timing=timing,
        counting_operations=(throttled, timed_out, died_inside),
        reservation=Reservation(
            ALLOCATION, ReservationState.RECONCILED, None, LEDGER_REVISION, 0
        ),
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
    "an attempt admitted and never claimed": never_claimed,
    "a recorded defect an operator finalized": defect_finalized_by_operator,
    "a request whose input bound was never established": input_bound_exhausted,
}
"""Each case by its name in the ruling; the eighth is two exports, a paused attempt having
none."""
