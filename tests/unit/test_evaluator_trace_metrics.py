"""Every export that decodes gets its trace metrics beside its outcome, each part evaluated
where what it needs exists and recorded as not evaluated elsewhere. The group's gate is here:
a truthful report over a full read carries no finding, asked and was answered by every source
that was up, has every target retrieved and concluded, and every completed read is either
contributing or extra. A failed attempt keeps its tallies, its cost and what it retrieved; a
run of another context keeps its tallies and is compared with nothing."""

from dataclasses import replace
from datetime import timedelta

import pytest

from leaveimpact.core import (
    Answer,
    AsOperation,
    AttributionKind,
    CallState,
    Cost,
    ModelCallId,
    ModelOrigin,
    ReportedUsage,
    RunCondition,
    Source,
    TerminalStatus,
    ToolCall,
    cost_of_reported,
    is_completed_read,
)
from leaveimpact.core.attribution import RedispatchPolicy, attribution_table_digest
from leaveimpact.core.registration import RetryRule
from leaveimpact.core.run_record import FailureCategory
from leaveimpact.evaluator.call_check import CallCheck
from leaveimpact.evaluator.eligibility_check import EndingKind
from leaveimpact.evaluator.grading import Excluded, ExcludedReason, Graded, Limited, LimitedReason
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.source_discipline import OriginCount
from leaveimpact.evaluator.trace_metrics import evaluate_run
from leaveimpact.world import Scenario
from tests.unit.export_fixture import (
    BASIS,
    COUNTING_MODEL,
    ROLE,
    SELECTION,
    agent_export,
    answered_call,
    malformed,
    provider_failed_export,
    reads,
    run_export,
)
from tests.unit.reads_fixture import reads_of_everything
from tests.unit.registration_fixture import TABLE
from tests.unit.report_fixture import renumbered, truthful_report
from tests.unit.throwaway_world import loaded_world

NORMAL = RunCondition.all_reachable()


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def answer(world: SealedWorld, scenario: Scenario, condition: RunCondition = NORMAL) -> Answerable:
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return oracle


@pytest.mark.parametrize("down", [(), (Source.JIRA,), (Source.CALENDAR,)], ids=str)
def test_a_truthful_report_over_a_full_read_has_no_finding_and_every_target_retrieved(
    world: SealedWorld, down: tuple[Source, ...]
) -> None:
    condition = NORMAL.without(*down)
    for scenario in world.scenarios:
        operations = reads_of_everything(world, scenario, *down)
        export = run_export(
            world,
            scenario,
            truthful_report(answer(world, scenario, condition)),
            operations=operations,
            recorded=condition,
        )
        evaluation = evaluate_run(world, export)
        metrics = evaluation.metrics
        assert isinstance(evaluation.outcome, Graded), scenario.spec.id
        assert (metrics.discipline.findings, metrics.cost.findings) == ((), ())
        assert metrics.cost.cost is None  # rules-only: no model call, no cost, never a zero

        # Every source the answer depends on was asked, and answered unless it was down.
        assert metrics.required_sources is not None
        assert [use.source for use in metrics.required_sources] == list(
            scenario.key.required_sources
        )
        for use in metrics.required_sources:
            assert (use.attempted, use.succeeded) == (True, use.source not in down)

        # The tally accounts for every operation of the trace.
        tallies = [metrics.discipline.tally(source) for source in Source]
        counted = sum(t.completed.total + t.unreachable.total + t.defect.total for t in tallies)
        assert counted == len(operations)

        completed = [op.id for op in operations if is_completed_read(op.outcome)]
        assert metrics.contribution is not None
        assert sorted((*metrics.contribution.contributing, *metrics.contribution.extra)) == sorted(
            completed
        )

        assert metrics.retrieval is not None
        for found in metrics.retrieval.targets:
            assert found.retrieved
            assert found.concluded is (True if found.target.moves_a_required_key else None)


def test_a_run_of_another_context_keeps_its_tallies_and_is_compared_with_nothing(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    elsewhen = replace(
        world.context_of(scenario), now=world.context_of(scenario).now + timedelta(days=1)
    )
    export = run_export(
        world, scenario, operations=reads_of_everything(world, scenario), context=elsewhen
    )
    evaluation = evaluate_run(world, export)
    assert isinstance(evaluation.outcome, Excluded)
    assert evaluation.outcome.reason is ExcludedReason.CONTEXT_MISMATCH
    metrics = evaluation.metrics
    assert metrics.discipline.tally(Source.FRAPPE).succeeded
    assert metrics.cost.findings == ()
    assert (metrics.required_sources, metrics.contribution, metrics.retrieval) == (None, None, None)


def test_a_failed_attempt_keeps_its_tallies_its_cost_and_what_it_retrieved(
    world: SealedWorld,
) -> None:
    scenario = next(
        scenario for scenario in world.scenarios if Source.CORPUS in scenario.key.required_sources
    )
    # The provider failed the first call: nothing was read, and the attempt is still counted.
    by_the_provider = evaluate_run(world, provider_failed_export(world, scenario))
    assert isinstance(by_the_provider.outcome, Excluded)
    metrics = by_the_provider.metrics
    counted = {(state, read): count for state, read, count in metrics.discipline.model_calls}
    assert counted[(CallState.FAILED, AttributionKind.INFRASTRUCTURE)] == 1
    assert sum(counted.values()) == 1
    assert (metrics.cost.cost, metrics.cost.findings) == (None, ())
    assert metrics.required_sources is not None
    assert not any(use.attempted for use in metrics.required_sources)
    assert metrics.contribution is None  # no report was replayed
    assert metrics.retrieval is not None and metrics.retrieval.targets
    assert not any(found.retrieved for found in metrics.retrieval.targets)
    assert all(found.concluded is None for found in metrics.retrieval.targets)

    # A malformed record ended this one after it had read everything.
    (broken,) = reads(malformed(Source.JIRA))
    operations = (*reads_of_everything(world, scenario), replace(broken, id="op-broken"))
    by_a_defect = evaluate_run(
        world, run_export(world, scenario, operations=operations, status=TerminalStatus.FAILED)
    )
    assert isinstance(by_a_defect.outcome, Excluded)
    metrics = by_a_defect.metrics
    assert metrics.discipline.tally(Source.JIRA).defect == OriginCount(1, 0, 0)
    assert metrics.contribution is None
    assert metrics.retrieval is not None
    assert all(found.retrieved for found in metrics.retrieval.targets)
    assert all(found.concluded is None for found in metrics.retrieval.targets)


def test_a_run_with_no_answer_has_no_targets_to_speak_of_and_its_reads_are_still_judged(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    claims = truthful_report(answer(world, scenario))
    # The HR system down: no leave, no expected answer. The report is replayed all the same.
    hr_down = evaluate_run(
        world,
        run_export(
            world,
            scenario,
            claims,
            operations=reads_of_everything(world, scenario, Source.FRAPPE),
            recorded=NORMAL.without(Source.FRAPPE),
        ),
    )
    assert isinstance(hr_down.outcome, Limited)
    assert hr_down.outcome.reason is LimitedReason.UNREADABLE_LEAVE
    assert hr_down.metrics.retrieval is None  # not an empty set of targets
    assert hr_down.metrics.contribution is not None
    assert hr_down.metrics.required_sources is not None

    # A source that both answered and failed: no answer is derivable from the sealed world.
    everything = reads_of_everything(world, scenario)
    then_down = reads_of_everything(world, scenario, Source.JIRA)
    failed = [
        replace(op, id=f"late-{op.id}") for op in then_down if not is_completed_read(op.outcome)
    ]
    mixed = evaluate_run(
        world, run_export(world, scenario, claims, operations=(*everything, *failed))
    )
    assert isinstance(mixed.outcome, Limited)
    assert mixed.outcome.reason is LimitedReason.MIXED_CONDITION
    assert mixed.metrics.retrieval is None
    assert mixed.metrics.contribution is not None


def test_a_structurally_invalid_report_has_no_contribution_and_concludes_no_target(
    world: SealedWorld,
) -> None:
    scenario = next(
        scenario for scenario in world.scenarios if Source.CORPUS in scenario.key.required_sources
    )
    claims = truthful_report(answer(world, scenario))
    export = run_export(
        world,
        scenario,
        (*claims, renumbered(claims[0], 9_999)),
        operations=reads_of_everything(world, scenario),
    )
    evaluation = evaluate_run(world, export)
    assert isinstance(evaluation.outcome, Graded)
    assert not evaluation.outcome.rows.structurally_valid
    assert evaluation.metrics.contribution is None  # nothing was replayed
    retrieval = evaluation.metrics.retrieval
    assert retrieval is not None and retrieval.targets
    # Graded with zero credit: retrieved, and no required row of it reported correctly.
    for found in retrieval.targets:
        assert found.retrieved
        assert found.concluded is (False if found.target.moves_a_required_key else None)


def test_an_agents_run_is_measured_by_who_asked_and_what_it_cost(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    first = ModelCallId("call-1")

    def priced(input_tokens: int, output_tokens: int) -> tuple[dict[str, object], Cost]:
        usage: dict[str, object] = {"inputTokens": input_tokens, "outputTokens": output_tokens}
        return usage, cost_of_reported(ReportedUsage(usage), SELECTION, BASIS)

    # The leave is the prefetch's; everything after it the model asked for in its first call.
    prefetched, *asked = reads_of_everything(world, scenario)
    operations = (prefetched, *(replace(op, origin=ModelOrigin(first)) for op in asked))
    tool_calls = tuple(
        ToolCall(f"tu_{number}", op.tool, AsOperation(op.id))
        for number, op in enumerate(asked, start=1)
    )
    calls = (
        answered_call(
            1, *priced(900, 80), stop_reason="tool_use", answer=Answer(False, tool_calls, ())
        ),
        answered_call(2, *priced(4_000, 600)),
    )
    export = agent_export(
        world,
        scenario,
        calls,
        claims=truthful_report(answer(world, scenario)),
        operations=operations,
    )
    evaluation = evaluate_run(world, export)
    assert isinstance(evaluation.outcome, Graded)
    metrics = evaluation.metrics
    assert (metrics.discipline.findings, metrics.cost.findings) == ((), ())
    assert metrics.discipline.tally(Source.FRAPPE).completed.prefetch == 1
    assert (metrics.discipline.model_operations, metrics.discipline.refused_by_the_wrapper) == (
        len(asked),
        0,
    )
    assert metrics.cost.cost == export.record.cost
    assert metrics.cost.cost is not None and metrics.cost.cost.complete
    assert metrics.cost.cost.pico_usd == 4_900 * 1_100_000 + 680 * 5_500_000


def test_the_four_audits_are_evaluated_where_their_registration_values_are_given(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    export = agent_export(world, scenario, (answered_call(1, None, None),))
    tabled = replace(
        export, record=replace(export.record, attribution_table=attribution_table_digest(TABLE))
    )
    held = evaluate_run(
        world,
        tabled,
        table=TABLE,
        redispatch=RedispatchPolicy(2, 0),
        retry=RetryRule(FailureCategory.INFRASTRUCTURE, 3),
        counting_identifiers={ROLE: COUNTING_MODEL},
    ).metrics
    assert held.account is not None and held.account.findings == ()
    assert (held.counts.registration_evaluated, held.counts.findings) == (True, ())
    # The fixture's rule is none the table holds, so the call gets no standing.
    assert held.calls is not None and held.calls == CallCheck((), ())
    assert held.eligibility is not None and held.eligibility.ending.kind is EndingKind.COMPLETED

    unheld = evaluate_run(world, export).metrics
    assert unheld.account is not None
    assert (unheld.counts.registration_evaluated, unheld.calls, unheld.eligibility) == (
        False,
        None,
        None,
    )
    # A rules-only record holds no reservation: no account to read.
    rules_only = evaluate_run(world, run_export(world, scenario)).metrics
    assert (rules_only.account, rules_only.counts.operations) == (None, 0)
