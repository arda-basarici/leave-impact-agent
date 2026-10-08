"""The rules-only baseline graded end to end: the real run, its real export, the real evaluator,
on every scenario of the throwaway world under the normal condition and the two gradable
outages. Ruling 6's construction gate: every claim reproduced by the replay, no finding of
any kind, every citation resolving, retrieved and used, identical bytes on a repeat. And the
forecast the step's rulings were measured on, met by the real thing: 810, 270 and 540 claims,
24, 6 and 18 plan findings against the oracle, the structured tier graded correct whole and
the other tiers never under the normal condition, some of them under an outage. The
degraded states as the evaluator sees them, and a failed run excluded by its defect."""

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.agent.export import RunProvenance
from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import Abstention, RulesOnlyRun, investigate
from leaveimpact.core import (
    Component,
    HarnessRevision,
    MalformedRecord,
    Observed,
    PricingBasis,
    RunCondition,
    RunExport,
    Source,
    TerminalStatus,
    TreeState,
    condition_id,
    decode_registration_bytes,
    export_bytes,
    prefetch_rule,
)
from leaveimpact.evaluator.grading import (
    Excluded,
    ExcludedReason,
    Graded,
    Limited,
    LimitedReason,
    correct_whole,
)
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from tests.unit.export_fixture import export_baseline
from tests.unit.in_memory_ports import InMemoryWork
from tests.unit.reads_fixture import Systems, systems_holding
from tests.unit.throwaway_world import loaded_world

DIGEST = "a" * 64
COMMIT = "b" * 40
NORMAL = RunCondition.all_reachable()
OUTAGES: tuple[tuple[Source, ...], ...] = ((), (Source.JIRA,), (Source.CALENDAR,))
FORECAST: dict[tuple[Source, ...], tuple[int, int]] = {
    (): (810, 22),
    (Source.JIRA,): (270, 6),
    (Source.CALENDAR,): (540, 16),
}

# Scenarios graded correct whole, per tier. Under the normal condition a system that reads no
# prose is right on the structured tier and nowhere else. Under an outage the oracle expects
# less, and a report that states little is right more often: with the tracker down every
# adversarial scenario and two fragmented ones, with the calendar down three fragmented ones.
CORRECT_WHOLE: dict[tuple[Source, ...], dict[str, int]] = {
    (): {"structured": 10, "fragmented": 0, "adversarial": 0},
    (Source.JIRA,): {"structured": 10, "fragmented": 2, "adversarial": 10},
    (Source.CALENDAR,): {"structured": 10, "fragmented": 3, "adversarial": 0},
}

REGISTRATION = decode_registration_bytes(
    (Path(__file__).resolve().parents[2] / "preregistration" / "registration.json").read_bytes()
)


def provenance(*down: Source) -> RunProvenance:
    return rules_only_provenance(
        REGISTRATION,
        condition_id(down),
        "base",
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def scenario(world: SealedWorld) -> Scenario:
    return world.scenarios[0]


def run_and_export(
    world: SealedWorld, scenario: Scenario, systems: Systems, *down: Source
) -> tuple[RulesOnlyRun, RunExport]:
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    context = world.context_of(scenario)
    result = investigate(context, systems.ports)
    export = export_baseline(
        result, context, provenance(*down), run_id="run-1", attempt=1, duration_ms=1_200
    )
    return result, export


def graded(evaluation: Evaluation) -> Graded:
    assert isinstance(evaluation.outcome, Graded), type(evaluation.outcome).__name__
    return evaluation.outcome


# --- Ruling 6's construction gate, and the forecast -------------------------------------------


@pytest.mark.parametrize("down", OUTAGES, ids=str)
def test_the_baseline_is_grounded_whole_and_right_exactly_where_no_prose_is_needed(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    claims = plan_findings = citations = 0
    whole: Counter[str] = Counter()
    for scenario in world.scenarios:
        result, export = run_and_export(world, scenario, systems_holding(world), *down)
        assert result.abstention is None and result.failure is None
        outcome = graded(evaluate_run(world, export))
        assert outcome.condition == NORMAL.without(*down)
        assert outcome.rows.structural_problems == ()
        assert outcome.report_findings == () and outcome.coverage == ()
        assert outcome.integrity == () and outcome.harness_findings == ()
        grounding = outcome.grounding
        assert grounding is not None
        assert all(g.standing is Standing.REPRODUCED for g in grounding.claims), scenario.spec.id
        assert len(grounding.claims) == len(export.trace.claims)
        # A scenario whose impacts the structured reads do not ground states nothing.
        assert all(c.resolves and c.retrieved and c.used for c in grounding.citations), (
            scenario.spec.id
        )
        citations += len(grounding.citations)
        claims += len(export.trace.claims)
        assert outcome.oracle_findings is not None
        plan_findings += len(outcome.oracle_findings)
        whole[scenario.key.tier.value] += correct_whole(outcome)
    assert (claims, plan_findings) == FORECAST[down]
    assert citations > claims
    assert whole == CORRECT_WHOLE[down]


def test_a_repeated_run_exports_identical_bytes(world: SealedWorld, scenario: Scenario) -> None:
    _, first = run_and_export(world, scenario, systems_holding(world))
    _, second = run_and_export(world, scenario, systems_holding(world))
    assert export_bytes(first) == export_bytes(second)
    assert first.record.prefetch_rule == prefetch_rule()
    assert first.record.status is TerminalStatus.COMPLETED
    assert first.trace.model_calls == () and first.record.cost is None


# --- The degraded states, and a failed run -----------------------------------------------------


def test_with_the_hr_system_down_every_run_abstains_and_is_limited_as_an_unreadable_leave(
    world: SealedWorld,
) -> None:
    for scenario in world.scenarios:
        result, export = run_and_export(world, scenario, systems_holding(world), Source.FRAPPE)
        assert result.abstention is Abstention.LEAVE_NOT_RETURNED
        assert export.record.status is TerminalStatus.COMPLETED and export.trace.claims == ()
        outcome = evaluate_run(world, export).outcome
        assert isinstance(outcome, Limited)
        assert outcome.reason is LimitedReason.UNREADABLE_LEAVE
        assert outcome.harness_findings == ()


def test_with_the_corpus_down_the_baseline_reads_nothing_there_and_is_graded_whole(
    world: SealedWorld,
) -> None:
    # Its empty constraint list is a premise the record declares, not a degraded state:
    # no corpus read is made, so the trace shows the normal condition.
    claims = 0
    for scenario in world.scenarios:
        result, export = run_and_export(world, scenario, systems_holding(world), Source.CORPUS)
        assert result.condition.condition == NORMAL
        outcome = graded(evaluate_run(world, export))
        assert outcome.harness_findings == ()
        claims += len(export.trace.claims)
    assert claims == FORECAST[()][0]


@dataclass
class _WorkWithBrokenComponents(InMemoryWork):
    def components(self) -> tuple[Observed[Component], ...]:
        self._reach()
        raise MalformedRecord(self.source, "Component/all", "a member id of the wrong shape")


def test_a_run_failed_by_defect_exports_its_failure_and_is_excluded(
    world: SealedWorld, scenario: Scenario
) -> None:
    systems = systems_holding(world)
    work = _WorkWithBrokenComponents(
        tickets=systems.work.tickets, components_by_id=systems.work.components_by_id
    )
    context = world.context_of(scenario)
    result = investigate(context, replace(systems.ports, work=work))
    export = export_baseline(
        result, context, provenance(), run_id="run-1", attempt=1, duration_ms=900
    )
    assert export.record.status is TerminalStatus.FAILED
    assert export.record.failure == result.failure and result.failure is not None
    outcome = evaluate_run(world, export).outcome
    assert isinstance(outcome, Excluded)
    assert outcome.reason is ExcludedReason.FAILED_BY_DEFECT
