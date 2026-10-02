"""A run export around a report, for the evaluator's tests: the provenance a real export carries,
filled with stand-ins, and the three things a test varies (the claims, the reads, how it ended).

Test infrastructure. The grading reads an export's context, its terminal status, the
outcomes of its reads and its claims; everything else in the record block is provenance the
grading does not look at, so it is built once here, valid and inert. The default is a
rules-only export, the smallest valid one, with no model call. An agent's export holds the
model calls a test gives it, priced under one selection, its record's usage and cumulative
cost summed from them the way a harness sums them; an infrastructure failure is one of
those, its one call failed by the provider.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from leaveimpact.core import (
    EXPORT_FORMAT_VERSION,
    Caps,
    Claim,
    DefectOutcome,
    Failure,
    FailureCategory,
    HarnessRevision,
    ModelCallId,
    ModelCallOutcome,
    ModelCallRecord,
    ModelConfiguration,
    Operation,
    OperationId,
    OutageAssignment,
    Outcome,
    PrefetchOrigin,
    PrefetchRule,
    PricingBasis,
    PricingRow,
    PricingSelection,
    RecordsOutcome,
    Retrieval,
    RetrievalKind,
    RunCondition,
    RunContext,
    RunExport,
    RunRecord,
    RunTrace,
    Setting,
    Source,
    System,
    SystemKind,
    TerminalStatus,
    TreeState,
    UnreachableOutcome,
    UsageAggregate,
    aggregate_usage,
    cumulative_cost,
)
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
        PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_100),
        PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_500),
    ),
)


def reads(*outcomes: tuple[Source | None, Outcome]) -> tuple[Operation, ...]:
    """Prefetch reads in the order given, one operation per (source, outcome)."""
    return tuple(
        Operation(OperationId(f"op-{number}"), PrefetchOrigin(), "a_tool", source, {}, outcome)
        for number, (source, outcome) in enumerate(outcomes, start=1)
    )


def answered(source: Source) -> tuple[Source, Outcome]:
    return (source, RecordsOutcome(()))


def unreachable(source: Source) -> tuple[Source, Outcome]:
    return (source, UnreachableOutcome(source, "no answer after the retries"))


def malformed(source: Source) -> tuple[Source, Outcome]:
    return (source, DefectOutcome(source, "a record locator", "a field of the wrong shape"))


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
        failure = Failure(FailureCategory.DEFECT, at, "a malformed record")
    record = RunRecord(
        observed_condition=recorded,
        outage=OutageAssignment(frozenset(), DIGEST),
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        model_configurations=(),
        pricing_selections=(),
        prompt_digests=(),
        tool_surface_digests=(),
        system=System(SystemKind.RULES_ONLY, "reference"),
        retrieval=Retrieval(RetrievalKind.NONE, None),
        prefetch_rule=PrefetchRule("prefetch-v1", DIGEST),
        caps=Caps(20, 100_000, 2, 5_000, "input_output"),
        status=status,
        failure=failure,
        usage=UsageAggregate((), 0, 1_200),
        cost=None,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-7",
        1,
        context if context is not None else world.context_of(scenario),
        record,
        RunTrace((), tuple(operations), tuple(claims)),
    )


def agent_export(
    world: SealedWorld,
    scenario: Scenario,
    calls: Sequence[ModelCallRecord],
    *,
    claims: Sequence[Claim] = (),
    operations: Sequence[Operation] = (),
    failure: Failure | None = None,
    basis: PricingBasis = BASIS,
) -> RunExport:
    """An agent's export of a run of ``scenario`` that made ``calls`` as the investigator.

    The record's usage and cumulative cost are summed from ``calls`` as a harness sums
    them, so the export states nothing its trace does not; a test of the verification
    replaces the part it wants wrong. The run completed unless ``failure`` says how it
    failed.
    """
    record = RunRecord(
        observed_condition=NORMAL,
        outage=OutageAssignment(frozenset(), DIGEST),
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        model_configurations=(
            (ROLE, ModelConfiguration("eu.model", (Setting("temperature", 0),))),
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
        usage=aggregate_usage(calls, 1_200),
        cost=cumulative_cost(call.cost for call in calls),
        pricing=basis,
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-8",
        1,
        world.context_of(scenario),
        record,
        RunTrace(tuple(calls), tuple(operations), tuple(claims)),
    )


def provider_failed_export(world: SealedWorld, scenario: Scenario) -> RunExport:
    """An agent's export of a run the provider failed on its first model call."""
    call = ModelCallRecord(
        ModelCallId("call-1"),
        ROLE,
        ModelCallOutcome.PROVIDER_FAULT,
        None,
        None,
        DIGEST,
        None,
        None,
        "timeout",
    )
    failure = Failure(FailureCategory.INFRASTRUCTURE, call.id, "the provider timed out")
    return agent_export(world, scenario, (call,), failure=failure)


__all__ = [
    "BASIS",
    "NORMAL",
    "ROLE",
    "SELECTION",
    "agent_export",
    "answered",
    "malformed",
    "provider_failed_export",
    "reads",
    "run_export",
    "unreachable",
]
