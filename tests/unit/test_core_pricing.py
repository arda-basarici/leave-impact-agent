"""The price table and the cost arithmetic: a rate loads only as an exact integer, a basis holds
the rows under each selection and refuses a selection with none, a cost is the exact integer
product with its completeness stated, a reported class with no rate refuses, a cumulative
cost is a floor when a call went unpriced, and an aggregate counts only reporting calls."""

import json
from collections.abc import Mapping
from datetime import date

import pytest

from leaveimpact.core import (
    Cost,
    ModelCallId,
    ModelCallOutcome,
    ModelCallRecord,
    PriceTable,
    PricingBasis,
    PricingRow,
    PricingSelection,
    Usage,
    aggregate_usage,
    basis_for,
    cost_of,
    cumulative_cost,
    decode_price_table,
    encode_price_table,
)
from leaveimpact.core.jsonshape import canonical_json

HAIKU = PricingSelection("eu.anthropic.claude-haiku-4-5", "eu-central-1", "on_demand")
NOVA = PricingSelection("eu.amazon.nova-lite", "eu-central-1", "on_demand")
TABLE = PriceTable(
    "USD",
    date(2026, 9, 1),
    (
        PricingRow(HAIKU.pricing_key, "eu-central-1", "on_demand", "input_tokens", 1_100),
        PricingRow(HAIKU.pricing_key, "eu-central-1", "on_demand", "output_tokens", 5_500),
        PricingRow(HAIKU.pricing_key, "eu-central-1", "on_demand", "cache_read_input_tokens", 110),
        PricingRow(NOVA.pricing_key, "eu-central-1", "on_demand", "input_tokens", 60),
        PricingRow(NOVA.pricing_key, "eu-central-1", "on_demand", "output_tokens", 240),
    ),
)
DIGEST = "c" * 64
RATE = {
    "pricing_key": "k",
    "region": "eu-central-1",
    "billing_mode": "on_demand",
    "token_class": "input_tokens",
    "nano_usd_per_token": 1_100,
}


def _table(*rates: Mapping[str, object], currency: str = "USD") -> object:
    return {"currency": currency, "effective_from": "2026-09-01", "rates": list(rates)}


def _call(id: str, usage: Usage | None, cost: Cost | None) -> ModelCallRecord:
    if usage is None:
        return ModelCallRecord(
            ModelCallId(id),
            "investigator",
            ModelCallOutcome.PROVIDER_FAULT,
            None,
            None,
            DIGEST,
            None,
            None,
            "timeout",
        )
    return ModelCallRecord(
        ModelCallId(id),
        "investigator",
        ModelCallOutcome.CLAIMS,
        "end_turn",
        10,
        DIGEST,
        usage,
        cost,
        None,
    )


def test_a_table_round_trips_and_its_digest_is_of_the_canonical_encoding() -> None:
    encoded = encode_price_table(TABLE)
    decoded = decode_price_table(json.loads(canonical_json(encoded)))
    assert decoded == TABLE
    assert decoded.digest == TABLE.digest
    reordered = PriceTable(TABLE.currency, TABLE.effective_from, tuple(reversed(TABLE.rows)))
    assert reordered.digest == TABLE.digest


def test_a_rate_loads_only_as_an_exact_integer_in_dollars() -> None:
    with pytest.raises(ValueError, match="nano_usd_per_token is an integer, got 1100.0"):
        decode_price_table(_table({**RATE, "nano_usd_per_token": 1100.0}))
    with pytest.raises(ValueError, match="nano_usd_per_token is an integer, got True"):
        decode_price_table(_table({**RATE, "nano_usd_per_token": True}))
    with pytest.raises(ValueError, match="the table is in USD, got 'EUR'"):
        decode_price_table(_table(RATE, currency="EUR"))
    with pytest.raises(ValueError, match=r"a rate has fields .*surplus \['note'\]"):
        decode_price_table(_table({**RATE, "note": "x"}))
    with pytest.raises(ValueError, match="a rate is given once"):
        decode_price_table(_table(RATE, RATE))


def test_a_basis_holds_the_rows_under_each_selection_and_refuses_one_with_none() -> None:
    basis = basis_for(TABLE, [HAIKU, HAIKU])
    assert [row.token_class for row in basis.rows] == [
        "cache_read_input_tokens",
        "input_tokens",
        "output_tokens",
    ]
    assert basis.table_digest == TABLE.digest
    assert len(basis_for(TABLE, [NOVA, HAIKU]).rows) == 5
    with pytest.raises(ValueError, match="no rate for eu.amazon.nova-lite in us-east-1 on_demand"):
        basis_for(TABLE, [PricingSelection(NOVA.pricing_key, "us-east-1", "on_demand")])


def test_a_cost_is_the_exact_integer_product_with_its_completeness() -> None:
    basis = basis_for(TABLE, [HAIKU])
    both = cost_of(Usage((("input_tokens", 120), ("output_tokens", 30))), HAIKU, basis)
    assert both == Cost(120 * 1_100 + 30 * 5_500, True)
    cached = cost_of(
        Usage((("input_tokens", 1), ("output_tokens", 1), ("cache_read_input_tokens", 1_000))),
        HAIKU,
        basis,
    )
    assert cached == Cost(1_100 + 5_500 + 110_000, True)
    assert cost_of(Usage((("output_tokens", 30),)), HAIKU, basis) == Cost(165_000, False)
    assert cost_of(Usage(()), HAIKU, basis) == Cost(0, False)


def test_a_reported_class_with_no_rate_refuses_instead_of_pricing_at_zero() -> None:
    basis = basis_for(TABLE, [NOVA])
    with pytest.raises(
        ValueError, match="cache_read_input_tokens was reported but the basis holds"
    ):
        cost_of(Usage((("input_tokens", 1), ("cache_read_input_tokens", 1))), NOVA, basis)
    with pytest.raises(ValueError, match="input_tokens was reported but the basis holds no rate"):
        cost_of(Usage((("input_tokens", 1),)), HAIKU, basis)


def test_a_cumulative_cost_is_a_floor_when_a_call_went_unpriced() -> None:
    assert cumulative_cost([]) is None
    assert cumulative_cost([None, None]) is None
    assert cumulative_cost([Cost(100, True), Cost(50, True)]) == Cost(150, True)
    assert cumulative_cost([Cost(100, True), Cost(50, False)]) == Cost(150, False)
    assert cumulative_cost([Cost(100, True), None]) == Cost(100, False)


def test_an_aggregate_counts_only_the_calls_that_reported_each_counter() -> None:
    calls = (
        _call("c1", Usage((("input_tokens", 100), ("output_tokens", 10))), Cost(1, True)),
        _call(
            "c2", Usage((("input_tokens", 50), ("cache_read_input_tokens", 400))), Cost(1, False)
        ),
        _call("c3", None, None),
    )
    aggregate = aggregate_usage(calls, 9_000)
    assert aggregate.model_calls == 3
    assert aggregate.counters == (
        ("input_tokens", 150, 2),
        ("output_tokens", 10, 1),
        ("cache_read_input_tokens", 400, 1),
    )
    assert aggregate.value("cache_write_input_tokens") is None
    assert aggregate_usage((), 0).counters == ()
    basis = PricingBasis(DIGEST, "USD", date(2026, 9, 1), ())
    assert basis.rate("k", "r", "m", "input_tokens") is None
