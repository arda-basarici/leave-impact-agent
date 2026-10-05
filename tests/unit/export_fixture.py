"""A run export around a report, for the evaluator's tests: the provenance a real export carries,
filled with stand-ins, and the three things a test varies (the claims, the reads, how it ended).

Test infrastructure. The grading reads an export's context, its terminal status, the
outcomes of its reads and its claims; everything else in the record block is provenance the
grading does not look at, so it is built once here, valid and inert. The default is a
rules-only export, the smallest valid one, with no model call. An agent's export holds the
model calls a test gives it, priced under one selection, its record's usage and cumulative
cost summed from them the way a harness sums them; an infrastructure failure is one of
those, its one call's send timed out.

A model call here is one dispatch unless a test builds its own: ``answered_call`` is a
complete response with the raw usage and the cost a test gives it, ``failed_call`` a send
the client gave up on. Positions are spread so a test's calls (from 1,000) and its reads
(from 10,001) never collide, the reads after the calls since a read a model asked for is
logged after that call's answer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from leaveimpact.agent.approval import approve_rules_only_run
from leaveimpact.agent.export import RunProvenance, export_rules_only_run
from leaveimpact.agent.rules_only import RulesOnlyRun
from leaveimpact.core import (
    EXPORT_FORMAT_VERSION,
    UNRESOLVED_RULE,
    Approval,
    ApprovalState,
    Approver,
    Attribution,
    AttributionKind,
    CallConfiguration,
    CallSetting,
    Caps,
    Claim,
    ClaimAuthor,
    ClientError,
    ClientErrorKind,
    CompleteResponse,
    ComposingPolicy,
    Composition,
    Cost,
    DefectOutcome,
    Dispatch,
    DispatchPhase,
    DispatchSite,
    Failure,
    FailureCategory,
    HarnessRevision,
    KeptReason,
    ModelCall,
    ModelCallId,
    Operation,
    OperationId,
    OperationSite,
    OutageAssignment,
    Outcome,
    PrefetchOrigin,
    PrefetchRule,
    PricingBasis,
    PricingRow,
    PricingSelection,
    RecordsOutcome,
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
    Sends,
    Source,
    System,
    SystemKind,
    TerminalStatus,
    Timing,
    TreeState,
    UnreachableOutcome,
    UsageAggregate,
    aggregate_usage,
    review_payload_digest,
    run_cost,
)
from leaveimpact.core.model_calls import Answer, Observation
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario

DIGEST = "a" * 64
COMMIT = "b" * 40
NORMAL = RunCondition.all_reachable()
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
COMPOSITION = Composition(ClaimAuthor.RULES, ComposingPolicy("rules-only-report", DIGEST), (), ())
ADMITTED = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)
DURATION_MS = 1_200
REQUEST = RequestIdentity(DIGEST, "Converse", "eu.model", "eu-central-1", None)
ALLOCATION = 5_000_000_000
ALLOCATION_TOKENS = 4_608
"""The worst case one dispatch is counted for against the token cap: its input and
its output limit."""
FIRST_READ = 10_001
"""Where the fixture logs its first read."""


def timing(duration_ms: int = DURATION_MS) -> Timing:
    """One recorded segment of ``duration_ms`` on a clean harness, no approval stamp."""
    return Timing(
        (Segment(1, HarnessRevision(COMMIT, TreeState.CLEAN), duration_ms, True),),
        ADMITTED,
        ADMITTED + timedelta(milliseconds=duration_ms),
        None,
        None,
    )


def approval(claims: Sequence[Claim], *, failed: bool) -> Approval:
    """What the automatic policy decides: approved over the review payload, or not requested
    for a failed run."""
    if failed:
        return Approval(ApprovalState.NOT_REQUESTED, None, None)
    return Approval(
        ApprovalState.APPROVED, Approver.AUTOMATIC, review_payload_digest(claims, COMPOSITION)
    )


def reads(*outcomes: tuple[Source | None, Outcome]) -> tuple[Operation, ...]:
    """Prefetch reads in the order given, one operation per (source, outcome)."""
    return tuple(
        Operation(
            OperationId(f"op-{number}"), PrefetchOrigin(), "a_tool", source, {}, outcome, number
        )
        for number, (source, outcome) in enumerate(outcomes, start=1)
    )


def logged_in_order(operations: Sequence[Operation]) -> tuple[Operation, ...]:
    """``operations`` with their positions set to the order given, after every call of the
    fixture: a test that rearranges, repeats or joins the reads of real runs is describing
    the order a harness logged them in, and a trace holds its operations in position order."""
    return tuple(
        replace(operation, position=FIRST_READ + number)
        for number, operation in enumerate(operations)
    )


def answered(source: Source) -> tuple[Source, Outcome]:
    return (source, RecordsOutcome(()))


def unreachable(source: Source) -> tuple[Source, Outcome]:
    return (source, UnreachableOutcome(source, "no answer after the retries"))


def malformed(source: Source) -> tuple[Source, Outcome]:
    return (source, DefectOutcome(source, "a record locator", "a field of the wrong shape"))


def dispatch(
    call: int,
    observation: Observation,
    attribution: AttributionKind,
    *,
    usage: Mapping[str, object] | None = None,
    cost: Cost | None = None,
    number: int = 1,
) -> Dispatch:
    """Dispatch ``number`` of the ``call``-th model call, logged at the call's own positions."""
    intent = 1_000 + 100 * call + 2 * number
    recorded = attribution is not AttributionKind.UNRESOLVED
    return Dispatch(
        number=number,
        segment=1,
        intent_position=intent,
        outcome_position=intent + 1 if recorded else None,
        request=REQUEST,
        input_reads=(),
        observation=observation,
        attribution=Attribution(attribution, "a-rule" if recorded else UNRESOLVED_RULE),
        usage=None if usage is None else ReportedUsage(usage),
        cost=cost,
        zero_cost_rule=None,
        allocation=ALLOCATION,
        allocation_tokens=ALLOCATION_TOKENS,
    )


def answered_call(
    call: int,
    usage: Mapping[str, object] | None,
    cost: Cost | None,
    *,
    stop_reason: str = "end_turn",
    answer: Answer | None = None,
) -> ModelCall:
    """The ``call``-th model call, answered on its first dispatch with ``usage`` as the raw
    object the response carried and ``cost`` as the harness priced it."""
    sent = dispatch(
        call,
        CompleteResponse(stop_reason, 840, 0),
        AttributionKind.BEHAVIOUR,
        usage=usage,
        cost=cost,
    )
    return ModelCall(
        ModelCallId(f"call-{call}"),
        ROLE,
        (sent,),
        answer if answer is not None else Answer(True, (), ()),
    )


def failed_call(call: int) -> ModelCall:
    """The ``call``-th model call, its one send timed out: an infrastructure fault with no
    usage and so no cost."""
    sent = dispatch(
        call, ClientError(ClientErrorKind.TIMEOUT, "timeout"), AttributionKind.INFRASTRUCTURE
    )
    return ModelCall(ModelCallId(f"call-{call}"), ROLE, (sent,), None)


def reservation(calls: Sequence[ModelCall]) -> Reservation:
    """The reservation as a ledger would settle it over ``calls``: reconciled when every send
    was priced whole, kept otherwise."""
    amount = ALLOCATION * sum(len(call.dispatches) for call in calls)
    sent = [d for call in calls for d in call.dispatches if d.sends is not Sends.NONE]
    if any(d.sends is Sends.UNRESOLVED for d in sent):
        return Reservation(amount, ReservationState.KEPT, KeptReason.UNRESOLVED_DISPATCH, 1)
    if any(d.cost is None or not d.cost.complete for d in sent):
        return Reservation(amount, ReservationState.KEPT, KeptReason.USAGE_INCOMPLETE, 1)
    return Reservation(amount, ReservationState.RECONCILED, None, 1)


def export_baseline(
    run: RulesOnlyRun,
    context: RunContext,
    provenance: RunProvenance,
    *,
    run_id: str,
    attempt: int,
    duration_ms: int = DURATION_MS,
) -> RunExport:
    """A real rules-only run exported the way a composition root does it: the automatic
    approval decided first, the two instants read around the run."""
    return export_rules_only_run(
        run,
        context,
        provenance,
        run_id=run_id,
        attempt=attempt,
        approval=approve_rules_only_run(run),
        admitted_at=ADMITTED,
        terminal_at=ADMITTED + timedelta(milliseconds=duration_ms),
        duration_ms=duration_ms,
    )


def run_export(
    world: SealedWorld,
    scenario: Scenario,
    claims: Sequence[Claim] = (),
    *,
    operations: Sequence[Operation] = (),
    status: TerminalStatus = TerminalStatus.COMPLETED,
    context: RunContext | None = None,
    recorded: RunCondition = NORMAL,
) -> RunExport:
    """A rules-only export of a run of ``scenario`` that ended as ``status`` with ``claims``.

    A failed status records a defect at the first read that returned a malformed record,
    which ``operations`` must then hold. ``context`` defaults to the one the sealed
    scenario gives; ``recorded`` is the condition the record block states, which the
    grading checks against the reads and does not trust.
    """
    failure = None
    if status is TerminalStatus.FAILED:
        at = next(op.id for op in operations if isinstance(op.outcome, DefectOutcome))
        failure = Failure(FailureCategory.DEFECT, OperationSite(at), "a malformed record")
    record = RunRecord(
        observed_condition=recorded,
        outage=OutageAssignment(frozenset(), DIGEST),
        corpus_level="base",
        preregistration_commit=COMMIT,
        attribution_table=None,
        model_configurations=(),
        pricing_selections=(),
        prompt_digests=(),
        tool_surface_digests=(),
        system=System(SystemKind.RULES_ONLY, "reference"),
        retrieval=Retrieval(RetrievalKind.NONE, None),
        prefetch_rule=PrefetchRule("prefetch-v1", DIGEST),
        caps=Caps(20, 100_000, 2, 5_000, "input_plus_output_cached_included"),
        status=status,
        failure=failure,
        abandonment=None,
        timing=timing(),
        usage=UsageAggregate((), 0, 0),
        cost=None,
        reservation=None,
        approval=approval(claims, failed=failure is not None),
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-7",
        1,
        context if context is not None else world.context_of(scenario),
        record,
        RunTrace((), logged_in_order(operations), tuple(claims), COMPOSITION),
    )


def agent_export(
    world: SealedWorld,
    scenario: Scenario,
    calls: Sequence[ModelCall],
    *,
    claims: Sequence[Claim] = (),
    operations: Sequence[Operation] = (),
    failure: Failure | None = None,
    basis: PricingBasis = BASIS,
) -> RunExport:
    """An agent's export of a run of ``scenario`` that made ``calls`` as the investigator.

    The record's usage and cumulative cost are summed from ``calls`` as a harness sums
    them and the reservation settled as a ledger settles it, so the export states nothing
    its trace does not; a test of the verification replaces the part it wants wrong. The
    run completed unless ``failure`` says how it failed.
    """
    record = RunRecord(
        observed_condition=NORMAL,
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
        caps=Caps(20, 100_000, 2, 5_000, "input_plus_output_cached_included"),
        status=TerminalStatus.COMPLETED if failure is None else TerminalStatus.FAILED,
        failure=failure,
        abandonment=None,
        timing=timing(),
        usage=aggregate_usage(calls),
        cost=run_cost(calls),
        reservation=reservation(calls),
        approval=approval(claims, failed=failure is not None),
        pricing=basis,
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-8",
        1,
        world.context_of(scenario),
        record,
        RunTrace(tuple(calls), logged_in_order(operations), tuple(claims), COMPOSITION),
    )


def provider_failed_export(world: SealedWorld, scenario: Scenario) -> RunExport:
    """An agent's export of a run whose first model call's send timed out."""
    call = failed_call(1)
    failure = Failure(
        FailureCategory.INFRASTRUCTURE,
        DispatchSite(call.id, 1, DispatchPhase.SEND),
        "the provider timed out",
    )
    return agent_export(world, scenario, (call,), failure=failure)


__all__ = [
    "BASIS",
    "COMPOSITION",
    "NORMAL",
    "ROLE",
    "SELECTION",
    "agent_export",
    "answered",
    "answered_call",
    "approval",
    "dispatch",
    "export_baseline",
    "failed_call",
    "logged_in_order",
    "malformed",
    "provider_failed_export",
    "reads",
    "reservation",
    "run_export",
    "timing",
    "unreachable",
]
