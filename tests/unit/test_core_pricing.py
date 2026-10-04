"""The price table and the cost arithmetic: a rate loads only as an exact integer, a basis holds
the rows under each selection and refuses a selection with none, a cost is the exact integer
product with its completeness stated, a reported class with no rate refuses, a cumulative
cost is a floor when a send went unpriced, and an aggregate counts only reporting
dispatches. Every rate is integer pico-dollars per token, the unit in which each published
rate the project pays is an integer."""

import json
from collections.abc import Mapping
from datetime import date
from fractions import Fraction

import pytest

from leaveimpact.core import (
    AbsentMeaning,
    Attribution,
    AttributionKind,
    ClientError,
    ClientErrorKind,
    CompleteResponse,
    Cost,
    Dispatch,
    ModelCall,
    ModelCallId,
    NoRecordedOutcome,
    PriceTable,
    PricingBasis,
    PricingRow,
    PricingSelection,
    RefusedBeforeSend,
    ReportedUsage,
    RequestIdentity,
    Usage,
    aggregate_usage,
    basis_for,
    cost_of,
    cost_of_reported,
    cumulative_cost,
    decode_price_table,
    encode_price_table,
    run_cost,
)
from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.model_calls import Observation

HAIKU = PricingSelection("model-a", "eu-central-1", "on_demand")
NOVA = PricingSelection("model-b", "eu-central-1", "on_demand")
TABLE = PriceTable(
    "USD",
    date(2026, 9, 1),
    (
        PricingRow(HAIKU.pricing_key, "eu-central-1", "on_demand", "input_tokens", 1_100_000),
        PricingRow(
            HAIKU.pricing_key, "eu-central-1", "on_demand", "output_tokens", 5_500_000
        ),
        PricingRow(
            HAIKU.pricing_key,
            "eu-central-1",
            "on_demand",
            "cache_read_input_tokens",
            110_000,
            AbsentMeaning.ZERO,
        ),
        PricingRow(
            HAIKU.pricing_key,
            "eu-central-1",
            "on_demand",
            "cache_write_input_tokens",
            1_375_000,
        ),
        PricingRow(NOVA.pricing_key, "eu-central-1", "on_demand", "input_tokens", 60_000),
        PricingRow(NOVA.pricing_key, "eu-central-1", "on_demand", "output_tokens", 240_000),
    ),
)
DIGEST = "c" * 64
RATE = {
    "pricing_key": "k",
    "region": "eu-central-1",
    "billing_mode": "on_demand",
    "token_class": "input_tokens",
    "pico_usd_per_token": 1_100_000,
    "when_absent": "unknown",
}


def _table(*rates: Mapping[str, object], currency: str = "USD") -> object:
    return {"currency": currency, "effective_from": "2026-09-01", "rates": list(rates)}


REQUEST = RequestIdentity(DIGEST, "Converse", "eu.model", "eu-central-1", None)


def _dispatch(
    number: int,
    intent: int,
    observation: Observation,
    read_as: AttributionKind,
    usage: Mapping[str, object] | None = None,
    cost: Cost | None = None,
) -> Dispatch:
    return Dispatch(
        number=number,
        segment=1,
        intent_position=intent,
        outcome_position=None if isinstance(observation, NoRecordedOutcome) else intent + 1,
        request=REQUEST,
        input_reads=(),
        observation=observation,
        attribution=Attribution(read_as, "a-rule"),
        usage=None if usage is None else ReportedUsage(usage),
        cost=cost,
        zero_cost_rule=None,
        allocation=0,
    )


def _call(id: str, intent: int, usage: Mapping[str, object] | None, cost: Cost | None) -> ModelCall:
    """One call of one dispatch: answered with ``usage``, or its send timed out."""
    if usage is None:
        timed_out = ClientError(ClientErrorKind.TIMEOUT, "timeout")
        sent = _dispatch(1, intent, timed_out, AttributionKind.INFRASTRUCTURE)
    else:
        answered = CompleteResponse("end_turn", 10, 0)
        sent = _dispatch(1, intent, answered, AttributionKind.BEHAVIOUR, usage, cost)
    return ModelCall(ModelCallId(id), "investigator", (sent,), None)


def test_a_table_round_trips_and_its_digest_is_of_the_canonical_encoding() -> None:
    encoded = encode_price_table(TABLE)
    decoded = decode_price_table(json.loads(canonical_json(encoded)))
    assert decoded == TABLE
    assert decoded.digest == TABLE.digest
    reordered = PriceTable(TABLE.currency, TABLE.effective_from, tuple(reversed(TABLE.rows)))
    assert reordered.digest == TABLE.digest


def test_a_rate_loads_only_as_an_exact_integer_in_dollars() -> None:
    with pytest.raises(ValueError, match="pico_usd_per_token is an integer, got 1100000.0"):
        decode_price_table(_table({**RATE, "pico_usd_per_token": 1100000.0}))
    with pytest.raises(ValueError, match="pico_usd_per_token is an integer, got True"):
        decode_price_table(_table({**RATE, "pico_usd_per_token": True}))
    with pytest.raises(ValueError, match="the table is in USD, got 'EUR'"):
        decode_price_table(_table(RATE, currency="EUR"))
    with pytest.raises(ValueError, match=r"a rate has fields .*surplus \['note'\]"):
        decode_price_table(_table({**RATE, "note": "x"}))
    with pytest.raises(ValueError, match="maybe"):
        decode_price_table(_table({**RATE, "when_absent": "maybe"}))
    loaded = decode_price_table(_table(RATE))
    assert loaded.rows[0].when_absent is AbsentMeaning.UNKNOWN
    with pytest.raises(ValueError, match="a rate is given once"):
        decode_price_table(_table(RATE, RATE))


def test_a_basis_holds_the_rows_under_each_selection_and_refuses_one_with_none() -> None:
    basis = basis_for(TABLE, [HAIKU, HAIKU])
    assert [row.token_class for row in basis.rows] == [
        "cache_read_input_tokens",
        "cache_write_input_tokens",
        "input_tokens",
        "output_tokens",
    ]
    assert basis.table_digest == TABLE.digest
    assert len(basis_for(TABLE, [NOVA, HAIKU]).rows) == 6
    with pytest.raises(ValueError, match="no rate for model-b in us-east-1 on_demand"):
        basis_for(TABLE, [PricingSelection(NOVA.pricing_key, "us-east-1", "on_demand")])


def test_a_cost_is_the_exact_integer_product_with_its_completeness() -> None:
    """Under model-a the cache-read row says absence is zero and the cache-write row
    says unknown, so a call reporting neither is incomplete, and one reporting the
    write counter alone is complete; under model-b, with no cache rows, input and
    output suffice."""
    basis = basis_for(TABLE, [HAIKU, NOVA])
    both = cost_of(Usage((("input_tokens", 120), ("output_tokens", 30))), HAIKU, basis)
    assert both == Cost(120 * 1_100_000 + 30 * 5_500_000, False)
    written = cost_of(
        Usage((("input_tokens", 120), ("output_tokens", 30), ("cache_write_input_tokens", 0))),
        HAIKU,
        basis,
    )
    assert written == Cost(120 * 1_100_000 + 30 * 5_500_000, True)
    assert cost_of(Usage((("input_tokens", 120), ("output_tokens", 30))), NOVA, basis) == Cost(
        120 * 60_000 + 30 * 240_000, True
    )
    cached = cost_of(
        Usage((("input_tokens", 1), ("output_tokens", 1), ("cache_read_input_tokens", 1_000))),
        HAIKU,
        basis,
    )
    assert cached == Cost(1_100_000 + 5_500_000 + 1_000 * 110_000, False)
    assert cost_of(Usage((("output_tokens", 30),)), HAIKU, basis) == Cost(30 * 5_500_000, False)
    assert cost_of(Usage(()), HAIKU, basis) == Cost(0, False)


def test_a_selection_the_basis_cannot_price_refuses_even_for_an_empty_usage() -> None:
    """A basis with no input and output rates under the selection prices nothing, so an
    empty usage must not come back as a complete zero cost."""
    empty = PricingBasis(DIGEST, "USD", date(2026, 9, 1), ())
    with pytest.raises(
        ValueError, match="no input_tokens rate under model-a .*nothing can be priced"
    ):
        cost_of(Usage(()), HAIKU, empty)
    half = PricingBasis(
        DIGEST,
        "USD",
        date(2026, 9, 1),
        (
            PricingRow(
                HAIKU.pricing_key, "eu-central-1", "on_demand", "input_tokens", 1_100_000
            ),
        ),
    )
    with pytest.raises(ValueError, match="no output_tokens rate under model-a"):
        cost_of(Usage((("input_tokens", 1),)), HAIKU, half)


def test_a_reported_class_with_no_rate_refuses_instead_of_pricing_at_zero() -> None:
    basis = basis_for(TABLE, [NOVA])
    with pytest.raises(
        ValueError, match="cache_read_input_tokens was reported but the basis holds"
    ):
        cost_of(Usage((("input_tokens", 1), ("cache_read_input_tokens", 1))), NOVA, basis)
    with pytest.raises(
        ValueError, match="no input_tokens rate under model-a .*nothing can be priced"
    ):
        cost_of(Usage((("input_tokens", 1),)), HAIKU, basis)


def test_a_cumulative_cost_is_a_floor_when_a_call_went_unpriced() -> None:
    assert cumulative_cost([]) is None
    assert cumulative_cost([None, None]) is None
    assert cumulative_cost([Cost(100, True), Cost(50, True)]) == Cost(150, True)
    assert cumulative_cost([Cost(100, True), Cost(50, False)]) == Cost(150, False)
    assert cumulative_cost([Cost(100, True), None]) == Cost(100, False)


def test_a_usage_the_reading_could_not_take_as_declared_is_never_priced_complete() -> None:
    """The rates cover both counters, so the arithmetic alone would call the cost complete;
    the raw object holds a field nobody declared, which may be a class that was billed."""
    basis = basis_for(TABLE, [NOVA])
    clean = ReportedUsage({"inputTokens": 120, "outputTokens": 30, "totalTokens": 150})
    assert cost_of_reported(clean, NOVA, basis) == Cost(120 * 60_000 + 30 * 240_000, True)
    odd = ReportedUsage({"inputTokens": 120, "outputTokens": 30, "reasoningTokens": 9})
    assert cost_of_reported(odd, NOVA, basis) == Cost(120 * 60_000 + 30 * 240_000, False)


def test_a_runs_cost_is_over_its_sends_and_a_refusal_before_sending_is_none() -> None:
    usage = {"inputTokens": 100, "outputTokens": 10}
    answered = _call("c1", 10, usage, Cost(1_000, True))
    assert run_cost((answered,)) == Cost(1_000, True)
    assert run_cost((answered, _call("c2", 20, None, None))) == Cost(1_000, False)
    refused = _dispatch(
        1, 30, RefusedBeforeSend("ParamValidationError"), AttributionKind.DEFECT
    )
    retried = _dispatch(
        2, 32, CompleteResponse("end_turn", 10, 0), AttributionKind.BEHAVIOUR, usage,
        Cost(500, True),
    )  # fmt: skip
    after_a_refusal = ModelCall(ModelCallId("c3"), "investigator", (refused, retried), None)
    assert run_cost((answered, after_a_refusal)) == Cost(1_500, True)
    lost = _dispatch(1, 40, NoRecordedOutcome(), AttributionKind.UNRESOLVED)
    recovered = _dispatch(
        2, 42, CompleteResponse("end_turn", 10, 0), AttributionKind.BEHAVIOUR, usage,
        Cost(500, True),
    )  # fmt: skip
    after_a_kill = ModelCall(ModelCallId("c4"), "investigator", (lost, recovered), None)
    assert run_cost((after_a_kill,)) == Cost(500, False)
    assert run_cost(()) is None
    assert run_cost((_call("c5", 50, None, None),)) is None


def test_an_aggregate_counts_only_the_dispatches_that_reported_each_counter() -> None:
    lost = _dispatch(1, 30, NoRecordedOutcome(), AttributionKind.UNRESOLVED)
    recovered = _dispatch(
        2, 32, CompleteResponse("end_turn", 10, 0), AttributionKind.BEHAVIOUR,
        {"inputTokens": 50, "cacheReadInputTokens": 400}, Cost(1, False),
    )  # fmt: skip
    calls = (
        _call("c1", 10, {"inputTokens": 100, "outputTokens": 10}, Cost(1, True)),
        ModelCall(ModelCallId("c2"), "investigator", (lost, recovered), None),
        _call("c3", 40, None, None),
    )
    aggregate = aggregate_usage(calls)
    assert (aggregate.model_calls, aggregate.dispatches) == (3, 4)
    assert aggregate.counters == (
        ("input_tokens", 150, 2),
        ("output_tokens", 10, 1),
        ("cache_read_input_tokens", 400, 1),
    )
    assert aggregate.value("cache_write_input_tokens") is None
    assert aggregate_usage(()).counters == ()
    basis = PricingBasis(DIGEST, "USD", date(2026, 9, 1), ())
    assert basis.rate("k", "r", "m", "input_tokens") is None


PUBLISHED = (
    # (model and class, the rate as published, the tokens it is published per): AWS's public
    # price list for eu-central-1 as read on 2026-10-04, standard on-demand rows, the Claude
    # rows the regional series.
    ("haiku-4.5 input", "1.10", 1_000_000),
    ("haiku-4.5 output", "5.50", 1_000_000),
    ("haiku-4.5 cache write 5m", "1.375", 1_000_000),
    ("haiku-4.5 cache write 1h", "2.20", 1_000_000),
    ("haiku-4.5 cache read", "0.11", 1_000_000),
    ("sonnet-4.6 input", "3.30", 1_000_000),
    ("sonnet-4.6 output", "16.50", 1_000_000),
    ("sonnet-4.6 cache write 5m", "4.125", 1_000_000),
    ("sonnet-4.6 cache write 1h", "6.60", 1_000_000),
    ("sonnet-4.6 cache read", "0.33", 1_000_000),
    ("nova-pro input", "0.00105", 1_000),
    ("nova-pro output", "0.0042", 1_000),
    ("nova-pro cache read", "0.0002625", 1_000),
    ("nova-lite input", "0.000078", 1_000),
    ("nova-lite output", "0.000312", 1_000),
    ("nova-lite cache read", "0.0000195", 1_000),
    ("nova-micro input", "0.000046", 1_000),
    ("nova-micro output", "0.000184", 1_000),
    ("nova-micro cache read", "0.0000115", 1_000),
    ("titan-embed-v2 input", "0.0002", 1_000),
)


def test_every_published_rate_is_an_integer_in_pico_dollars_and_three_are_not_in_nano() -> None:
    """The evidence the unit was ruled on, as exact arithmetic: pico-dollars per token state
    every rate on the project's model list, and nano-dollars, format 1's unit, cannot state
    three of them."""
    pico = {name: Fraction(rate) / per * 10**12 for name, rate, per in PUBLISHED}
    assert all(value.denominator == 1 for value in pico.values())
    assert pico["haiku-4.5 cache write 5m"] == 1_375_000
    assert pico["nova-pro cache read"] == 262_500
    assert pico["nova-micro cache read"] == 11_500
    fractional_in_nano = {name for name, value in pico.items() if value % 1_000}
    assert fractional_in_nano == {
        "nova-pro cache read",
        "nova-lite cache read",
        "nova-micro cache read",
    }
    assert pico["nova-pro cache read"] / 1_000 == Fraction(525, 2)
