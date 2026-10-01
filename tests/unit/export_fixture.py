"""A run export around a report, for the evaluator's tests: the provenance a real export carries,
filled with stand-ins, and the three things a test varies (the claims, the reads, how it ended).

Test infrastructure. The grading reads an export's context, its terminal status, the
outcomes of its reads and its claims; everything else in the record block is provenance the
grading does not look at, so it is built once here, valid and inert. The default is a
rules-only export, the smallest valid one, with no model call; an infrastructure failure
needs a model call the provider failed, so that one export is an agent's.
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
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario

DIGEST = "a" * 64
COMMIT = "b" * 40
NORMAL = RunCondition.all_reachable()


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


def provider_failed_export(world: SealedWorld, scenario: Scenario) -> RunExport:
    """An agent's export of a run the provider failed on its first model call."""
    call = ModelCallRecord(
        ModelCallId("call-1"),
        "investigator",
        ModelCallOutcome.PROVIDER_FAULT,
        None,
        None,
        DIGEST,
        None,
        None,
        "timeout",
    )
    selection = PricingSelection("model-a", "eu-central-1", "on_demand")
    record = RunRecord(
        observed_condition=NORMAL,
        outage=OutageAssignment(frozenset(), DIGEST),
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        model_configurations=(
            ("investigator", ModelConfiguration("eu.model", (Setting("temperature", 0),))),
        ),
        pricing_selections=(("investigator", selection),),
        prompt_digests=(("investigator", "system", DIGEST),),
        tool_surface_digests=(("investigator", DIGEST),),
        system=System(SystemKind.AGENT, "reference"),
        retrieval=Retrieval(RetrievalKind.FULL_TEXT, None),
        prefetch_rule=PrefetchRule("prefetch-v1", DIGEST),
        caps=Caps(20, 100_000, 2, 5_000, "input_output"),
        status=TerminalStatus.FAILED,
        failure=Failure(FailureCategory.INFRASTRUCTURE, call.id, "the provider timed out"),
        usage=UsageAggregate((), 1, 1_200),
        cost=None,
        pricing=PricingBasis(
            DIGEST,
            "USD",
            date(2026, 9, 1),
            (
                PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_100),
                PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_500),
            ),
        ),
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        "run-8",
        1,
        world.context_of(scenario),
        record,
        RunTrace((call,), (), ()),
    )


__all__ = [
    "NORMAL",
    "answered",
    "malformed",
    "provider_failed_export",
    "reads",
    "run_export",
    "unreachable",
]
