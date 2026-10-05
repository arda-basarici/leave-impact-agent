"""The counting rules: the registry is closed and a cap refuses a name outside it; the one
rule sums every reported class; a count is established only when every class is accounted
for and the usage was read whole; and which absences are proven comes from the price
table's rows for the selection, never from a price."""

from datetime import date

import pytest

from leaveimpact.core.input_bound import RegisteredInputBound
from leaveimpact.core.pricing import absent_as_zero
from leaveimpact.core.run_record import (
    AbsentMeaning,
    Caps,
    PricingBasis,
    PricingRow,
    PricingSelection,
)
from leaveimpact.core.run_trace import USAGE_COUNTER_NAMES
from leaveimpact.core.token_counting import (
    COUNTING_RULES,
    INPUT_PLUS_OUTPUT_CACHED_INCLUDED,
    TokenCount,
    count_tokens,
    require_counting_rule,
)
from leaveimpact.core.usage import ReportedUsage

METHOD = RegisteredInputBound("provider_count", 1)

RULE = INPUT_PLUS_OUTPUT_CACHED_INCLUDED
CACHE = frozenset({"cache_read_input_tokens", "cache_write_input_tokens"})
ALL_FOUR = {
    "inputTokens": 100,
    "outputTokens": 20,
    "cacheReadInputTokens": 7,
    "cacheWriteInputTokens": 3,
    "totalTokens": 130,
}


def test_the_registry_holds_one_rule_summing_every_reported_class() -> None:
    assert dict(COUNTING_RULES) == {RULE: USAGE_COUNTER_NAMES}


def test_the_registry_cannot_be_changed_by_a_caller() -> None:
    with pytest.raises(TypeError):
        COUNTING_RULES["input_output"] = ("input_tokens", "output_tokens")  # type: ignore[index]


def test_a_cap_refuses_a_rule_the_registry_lacks() -> None:
    assert Caps(20, 100_000, 2, 5_000, RULE, METHOD).counting_rule == RULE
    with pytest.raises(ValueError, match="the counting rule is a registered one"):
        Caps(20, 100_000, 2, 5_000, "input_output", METHOD)


def test_counting_under_an_unregistered_rule_is_refused() -> None:
    with pytest.raises(ValueError, match="a counting rule is a registered one"):
        count_tokens("input_output", ReportedUsage(ALL_FOUR), frozenset())
    assert require_counting_rule(RULE, "the counting rule") == RULE


def test_every_class_reported_is_an_established_sum() -> None:
    assert count_tokens(RULE, ReportedUsage(ALL_FOUR), frozenset()) == TokenCount(130, True)


def test_an_absent_class_leaves_a_floor_unless_its_absence_is_proven_zero() -> None:
    usage = ReportedUsage({"inputTokens": 100, "outputTokens": 20, "totalTokens": 120})
    assert count_tokens(RULE, usage, frozenset()) == TokenCount(120, False)
    assert count_tokens(RULE, usage, CACHE) == TokenCount(120, True)
    one_proven = frozenset({"cache_read_input_tokens"})
    assert count_tokens(RULE, usage, one_proven) == TokenCount(120, False)


def test_a_reported_zero_is_reported_and_needs_no_proof() -> None:
    usage = ReportedUsage(
        {"inputTokens": 5, "outputTokens": 1, "cacheReadInputTokens": 0, "cacheWriteInputTokens": 0}
    )
    assert count_tokens(RULE, usage, frozenset()) == TokenCount(6, True)


def test_absence_of_the_input_or_output_counter_is_never_established_by_a_cache_proof() -> None:
    usage = ReportedUsage({"outputTokens": 20})
    assert count_tokens(RULE, usage, CACHE) == TokenCount(20, False)


@pytest.mark.parametrize(
    "raw",
    [
        {**ALL_FOUR, "reasoningTokens": 40},
        {**ALL_FOUR, "totalTokens": 131},
        {**ALL_FOUR, "cacheReadInputTokenCount": 8},
        {**ALL_FOUR, "serverToolUsage": {"webSearchRequests": 1}},
    ],
    ids=["undeclared field", "total not the sum", "twin disagrees", "server tool usage"],
)
def test_an_anomaly_in_the_usage_leaves_a_floor(raw: dict[str, object]) -> None:
    counted = count_tokens(RULE, ReportedUsage(raw), CACHE)
    assert counted == TokenCount(130, False)


def test_a_counter_that_is_not_a_count_is_neither_summed_nor_established() -> None:
    usage = ReportedUsage({"inputTokens": 100, "outputTokens": "20"})
    assert count_tokens(RULE, usage, CACHE) == TokenCount(100, False)


def test_a_token_count_is_never_negative() -> None:
    with pytest.raises(ValueError, match="a token count is at least 0"):
        TokenCount(-1, True)


def _basis(*rows: PricingRow) -> PricingBasis:
    return PricingBasis("0" * 64, "USD", date(2026, 9, 1), rows)


def test_proven_absences_are_the_selections_rows_marked_zero() -> None:
    selection = PricingSelection("model-a", "eu-central-1", "on_demand")
    basis = _basis(
        PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_000_000),
        PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_000_000),
        PricingRow(
            "model-a",
            "eu-central-1",
            "on_demand",
            "cache_read_input_tokens",
            100_000,
            AbsentMeaning.ZERO,
        ),
        PricingRow("model-a", "eu-central-1", "on_demand", "cache_write_input_tokens", 1_250_000),
        PricingRow(
            "model-b",
            "eu-central-1",
            "on_demand",
            "cache_write_input_tokens",
            1_250_000,
            AbsentMeaning.ZERO,
        ),
    )
    assert absent_as_zero(selection, basis) == frozenset({"cache_read_input_tokens"})


def test_a_zero_rate_proves_nothing_about_tokens() -> None:
    selection = PricingSelection("model-a", "eu-central-1", "on_demand")
    basis = _basis(
        PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_000_000),
        PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_000_000),
        PricingRow("model-a", "eu-central-1", "on_demand", "cache_read_input_tokens", 0),
    )
    assert absent_as_zero(selection, basis) == frozenset()
    usage = ReportedUsage({"inputTokens": 100, "outputTokens": 20})
    assert not count_tokens(RULE, usage, absent_as_zero(selection, basis)).established
