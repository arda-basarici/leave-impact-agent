"""The record's usage and cost are recomputed from the trace in three layers, and each layer
finds exactly its own disagreement: the usage aggregate, a call's cost, the cumulative cost,
the last summed from the recomputed costs so that a harness wrong the same way twice does not
agree with itself. Rates the record does not embed and a call left unpriced are pricing
findings; nothing the record states raises."""

from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.core import (
    AbsentMeaning,
    Cost,
    ModelCallId,
    ModelCallOutcome,
    ModelCallRecord,
    PricingBasis,
    PricingRow,
    RunExport,
    Usage,
    UsageAggregate,
    cost_of,
)
from leaveimpact.evaluator.cost_check import CostFinding, CostFindingKind, check_cost
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit.export_fixture import (
    BASIS,
    DIGEST,
    ROLE,
    SELECTION,
    agent_export,
    provider_failed_export,
    run_export,
)
from tests.unit.throwaway_world import loaded_world

KINDS = CostFindingKind
CACHE_READ = PricingRow("model-a", "eu-central-1", "on_demand", "cache_read_input_tokens", 110)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def usage(input_tokens: int, output_tokens: int | None, cache_read: int | None = None) -> Usage:
    counters = (
        ("input_tokens", input_tokens),
        ("output_tokens", output_tokens),
        ("cache_read_input_tokens", cache_read),
    )
    return Usage(tuple((name, value) for name, value in counters if value is not None))


def answered(
    id: str, reported: Usage | None, basis: PricingBasis = BASIS, *, priced: bool = True
) -> ModelCallRecord:
    """A model call that answered, priced as a harness prices it unless ``priced`` says not."""
    cost = cost_of(reported, SELECTION, basis) if reported is not None and priced else None
    return ModelCallRecord(
        ModelCallId(id),
        ROLE,
        ModelCallOutcome.TOOL_CALLS,
        "tool_use",
        40,
        DIGEST,
        reported,
        cost,
        None,
    )


def faulted(id: str) -> ModelCallRecord:
    return ModelCallRecord(
        ModelCallId(id),
        ROLE,
        ModelCallOutcome.PROVIDER_FAULT,
        None,
        None,
        DIGEST,
        None,
        None,
        "timeout",
    )


def three_calls(world: SealedWorld) -> RunExport:
    """Two priced calls and one the provider failed: 300 and 500 input tokens, 40 and 60 out."""
    calls = (
        answered("call-1", usage(300, 40)),
        faulted("call-2"),
        answered("call-3", usage(500, 60)),
    )
    return agent_export(world, world.scenarios[0], calls)


def test_a_record_summed_from_its_own_trace_verifies_clean(world: SealedWorld) -> None:
    export = three_calls(world)
    check = check_cost(export)
    assert check.findings == ()
    assert check.usage == export.record.usage
    assert check.usage == UsageAggregate(
        (("input_tokens", 800, 2), ("output_tokens", 100, 2)), 3, export.record.usage.duration_ms
    )
    # 800 input tokens at 1,100 and 100 output tokens at 5,500 nano-dollars each.
    assert check.cost == export.record.cost == Cost(800 * 1_100 + 100 * 5_500, complete=False)
    assert check.call_costs == (
        (ModelCallId("call-1"), Cost(300 * 1_100 + 40 * 5_500, True)),
        (ModelCallId("call-2"), None),  # no usage arrived with a fault: a floor, not a zero
        (ModelCallId("call-3"), Cost(500 * 1_100 + 60 * 5_500, True)),
    )


def test_a_run_that_called_no_model_or_priced_nothing_has_no_cost_and_no_finding(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    for export in (run_export(world, scenario), provider_failed_export(world, scenario)):
        check = check_cost(export)
        assert (check.cost, check.findings) == (None, ())
        assert check.usage == export.record.usage


def test_the_usage_layer_finds_a_counter_or_a_call_count_that_is_not_the_traces(
    world: SealedWorld,
) -> None:
    export = three_calls(world)
    stated = export.record.usage

    def with_usage(aggregate: UsageAggregate) -> tuple[CostFinding, ...]:
        record = replace(export.record, usage=aggregate)
        return check_cost(replace(export, record=record)).findings

    a_sum_off = replace(stated, counters=(("input_tokens", 801, 2), ("output_tokens", 100, 2)))
    assert with_usage(a_sum_off) == (CostFinding(KINDS.USAGE_DIFFERS, "input_tokens"),)
    # The sum right and the number of calls that reported it wrong: a total passed off as partial.
    coverage_off = replace(stated, counters=(("input_tokens", 800, 2), ("output_tokens", 100, 1)))
    assert with_usage(coverage_off) == (CostFinding(KINDS.USAGE_DIFFERS, "output_tokens"),)
    a_counter_dropped = replace(stated, counters=(("input_tokens", 800, 2),))
    assert with_usage(a_counter_dropped) == (CostFinding(KINDS.USAGE_DIFFERS, "output_tokens"),)
    a_call_more = replace(stated, model_calls=4)
    assert with_usage(a_call_more) == (CostFinding(KINDS.CALL_COUNT_DIFFERS),)
    # The duration is the harness's own and nothing in the trace checks it.
    assert with_usage(replace(stated, duration_ms=9)) == ()


def test_the_call_layer_finds_a_cost_that_is_not_the_usage_at_the_embedded_rates(
    world: SealedWorld,
) -> None:
    export = three_calls(world)
    first, fault, last = export.trace.model_calls
    assert first.cost is not None
    overpriced = replace(first, cost=replace(first.cost, nano_usd=first.cost.nano_usd + 1))
    trace = replace(export.trace, model_calls=(overpriced, fault, last))
    # Only the call is wrong: the record's cumulative cost is still the right sum.
    assert check_cost(replace(export, trace=trace)).findings == (
        CostFinding(KINDS.CALL_COST_DIFFERS, "call-1"),
    )
    # A complete price recorded as a floor is a different cost.
    floored = replace(first, cost=replace(first.cost, complete=False))
    trace = replace(export.trace, model_calls=(floored, fault, last))
    assert check_cost(replace(export, trace=trace)).findings == (
        CostFinding(KINDS.CALL_COST_DIFFERS, "call-1"),
    )


def test_a_harness_wrong_the_same_way_twice_does_not_agree_with_itself(
    world: SealedWorld,
) -> None:
    export = three_calls(world)
    first, fault, last = export.trace.model_calls
    assert first.cost is not None and export.record.cost is not None
    overpriced = replace(first, cost=replace(first.cost, nano_usd=first.cost.nano_usd + 7))
    summed_from_it = replace(export.record.cost, nano_usd=export.record.cost.nano_usd + 7)
    coordinated = replace(
        export,
        trace=replace(export.trace, model_calls=(overpriced, fault, last)),
        record=replace(export.record, cost=summed_from_it),
    )
    check = check_cost(coordinated)
    assert check.findings == (
        CostFinding(KINDS.CALL_COST_DIFFERS, "call-1"),
        CostFinding(KINDS.CUMULATIVE_COST_DIFFERS),
    )
    # What is kept is the recomputed cost, the one a table reads.
    assert check.cost == export.record.cost


def test_the_cumulative_layer_finds_a_sum_that_is_not_the_calls(world: SealedWorld) -> None:
    export = three_calls(world)
    assert export.record.cost is not None
    for wrong in (
        replace(export.record.cost, nano_usd=export.record.cost.nano_usd - 1),
        # One call was never priced, so the sum is a floor; recorded as a total it differs.
        replace(export.record.cost, complete=True),
    ):
        mutated = replace(export, record=replace(export.record, cost=wrong))
        assert check_cost(mutated).findings == (CostFinding(KINDS.CUMULATIVE_COST_DIFFERS),)


def test_a_reported_class_the_basis_holds_no_rate_for_is_a_pricing_finding_and_no_crash(
    world: SealedWorld,
) -> None:
    cached = ModelCallRecord(
        ModelCallId("call-2"),
        ROLE,
        ModelCallOutcome.CLAIMS,
        "end_turn",
        40,
        DIGEST,
        usage(500, 60, cache_read=2_000),
        None,  # the harness could not price it either
        None,
    )
    export = agent_export(world, world.scenarios[0], (answered("call-1", usage(300, 40)), cached))
    check = check_cost(export)
    assert check.findings == (CostFinding(KINDS.RATE_MISSING, "call-2"),)
    assert check.findings[0].kind.is_pricing
    # The call it could price stands, and the run's cost is a floor.
    assert check.cost == Cost(300 * 1_100 + 40 * 5_500, complete=False)
    # A cost recorded for a call the embedded rates cannot price is also not reproducible.
    invented = replace(cached, cost=Cost(1, True))
    trace = replace(export.trace, model_calls=(export.trace.model_calls[0], invented))
    assert check_cost(replace(export, trace=trace)).findings == (
        CostFinding(KINDS.RATE_MISSING, "call-2"),
        CostFinding(KINDS.CALL_COST_DIFFERS, "call-2"),
    )


def test_a_call_that_reported_usage_and_records_no_cost_is_a_pricing_finding(
    world: SealedWorld,
) -> None:
    calls = (answered("call-1", usage(300, 40)), answered("call-2", usage(500, 60), priced=False))
    check = check_cost(agent_export(world, world.scenarios[0], calls))
    # The fixture's record sums the recorded costs, so its cumulative cost misses the call too.
    assert check.findings == (
        CostFinding(KINDS.CALL_NOT_PRICED, "call-2"),
        CostFinding(KINDS.CUMULATIVE_COST_DIFFERS),
    )
    assert check.cost == Cost(800 * 1_100 + 100 * 5_500, complete=True)


def test_a_counter_not_reported_keeps_the_cost_a_floor_unless_the_rate_says_absent_is_zero(
    world: SealedWorld,
) -> None:
    def basis(cache: PricingRow) -> PricingBasis:
        return PricingBasis(DIGEST, "USD", date(2026, 9, 1), (*BASIS.rows, cache))

    for when_absent, complete in ((AbsentMeaning.UNKNOWN, False), (AbsentMeaning.ZERO, True)):
        rates = basis(replace(CACHE_READ, when_absent=when_absent))
        calls = (answered("call-1", usage(300, 40), rates),)
        check = check_cost(agent_export(world, world.scenarios[0], calls, basis=rates))
        assert check.findings == ()
        assert check.cost == Cost(300 * 1_100 + 40 * 5_500, complete)
    # An output counter the provider did not report: priced on what it did, never as zero.
    partial = (answered("call-1", usage(300, None)),)
    check = check_cost(agent_export(world, world.scenarios[0], partial))
    assert (check.cost, check.findings) == (Cost(300 * 1_100, complete=False), ())
