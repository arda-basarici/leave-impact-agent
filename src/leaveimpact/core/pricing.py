"""The price table and the cost arithmetic: exact integers from a committed table, verifiable later.

Cost is a reported metric, so the evaluator checks it rather than copying it (the
investigator milestone's second build step, ruling 5), and the arithmetic lives here in
``core`` so the harness that prices a call and the evaluator that verifies the price run
the same function. The table states every rate as integer pico-dollars per token (a
rate of $1.10 per million tokens is 1,100,000; $0.0002625 per thousand is 262,500), so a
per-dispatch product is an integer and no rounding point exists anywhere; a table whose
rate is not
an integer refuses at load, since a rate that needs rounding would make the sum of the
per-call costs differ from the cost of the aggregate. A rate is named by its pricing
key, region and billing mode together, because a model id alone does not fix a Bedrock
rate (the ``eu.`` profile and on-demand are their own keys); a role's calls are priced
under the selection the run record holds for that role.

Completeness is stated, never assumed away. A counter the provider did not report is
unavailable, never a zero, so a cost is complete only when every rate row under the
selection either was reported or carries the table's recorded policy that absence
means nothing billed (``AbsentMeaning.ZERO``). That policy is data in the table, per
rate, unknown by default: a provider that omits a cache counter exactly when no cached
token was billed earns the ``zero`` entry only once the acceptance spike (build step 7)
shows it on that configuration, and until then a missing cache counter makes the cost
incomplete. A reported class the basis holds no rate for is a configuration error and
refuses, never a silent zero. A usage object the reading could not take as declared
(``usage.read_usage``) is never priced complete either, since a field nobody understood
may be a class that was billed. A cumulative cost sums the priced dispatches and is
complete only when every send was priced and every price complete, so an error that
reported no usage, or a dispatch nobody can prove was not sent, leaves the run's cost a
floor; a dispatch the client refused before sending was no send and costs nothing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    canonical_bytes,
    expect_fields,
    field_of,
    string_field,
)
from leaveimpact.core.model_calls import Dispatch, ModelCall, Sends
from leaveimpact.core.run_record import (
    BILLED_ON_EVERY_CALL,
    AbsentMeaning,
    PricingBasis,
    PricingRow,
    PricingSelection,
    UsageAggregate,
)
from leaveimpact.core.run_trace import USAGE_COUNTER_NAMES, Cost, Usage, require_integer
from leaveimpact.core.timeshape import decode_date, encode_date
from leaveimpact.core.usage import ReportedUsage


@dataclass(frozen=True, slots=True)
class PriceTable:
    """The committed table whole: its currency, the date its rates took effect, every rate.

    The basis a record embeds is a selection of these rows under this table's digest;
    the digest is of the canonical encoding, so two spellings of one table are one table.
    """

    currency: str
    effective_from: date
    rows: tuple[PricingRow, ...]

    def __post_init__(self) -> None:
        if self.currency != "USD":
            raise ValueError(
                f"rates are pico-dollars, so the table is in USD, got {self.currency!r}"
            )
        keys = [row.key for row in self.rows]
        if len(set(keys)) != len(keys):
            raise ValueError("a rate is given once per pricing key, region, billing mode and class")
        object.__setattr__(self, "rows", tuple(sorted(self.rows, key=lambda row: row.key)))

    @property
    def digest(self) -> str:
        """SHA-256 of the table's canonical encoding."""
        return hashlib.sha256(canonical_bytes(encode_price_table(self))).hexdigest()


def encode_price_table(table: PriceTable) -> JsonObject:
    """The JSON object of a table: currency, effective date, rates in key order."""
    return {
        "currency": table.currency,
        "effective_from": encode_date(table.effective_from),
        "rates": [encode_rate(row) for row in table.rows],
    }


def encode_rate(row: PricingRow) -> JsonObject:
    """The JSON object of one rate, the shape a table and a record's basis share."""
    return {
        "pricing_key": row.pricing_key,
        "region": row.region,
        "billing_mode": row.billing_mode,
        "token_class": row.token_class,
        "pico_usd_per_token": row.pico_usd_per_token,
        "when_absent": row.when_absent.value,
    }


def decode_price_table(value: object) -> PriceTable:
    """The table ``value`` encodes; a rate that is not an integer refuses here, at load.

    >>> decode_price_table({"currency": "USD", "effective_from": "2026-09-01", "rates": [
    ...     {"pricing_key": "k", "region": "eu-central-1", "billing_mode": "on_demand",
    ...      "token_class": "input_tokens", "pico_usd_per_token": 1100000.0,
    ...      "when_absent": "unknown"}]})
    Traceback (most recent call last):
    ...
    ValueError: pico_usd_per_token is an integer, got 1100000.0
    """
    data = as_object(value, "a price table")
    expect_fields(data, ("currency", "effective_from", "rates"), "a price table")
    return PriceTable(
        string_field(data, "currency"),
        decode_date(string_field(data, "effective_from"), "effective_from"),
        tuple(decode_rate(item) for item in array_field(data, "rates")),
    )


def decode_rate(item: object) -> PricingRow:
    """The rate ``item`` encodes; an integer rate and a known policy, or ``ValueError``."""
    data = as_object(item, "a rate")
    expect_fields(
        data,
        (
            "pricing_key",
            "region",
            "billing_mode",
            "token_class",
            "pico_usd_per_token",
            "when_absent",
        ),
        "a rate",
    )
    return PricingRow(
        string_field(data, "pricing_key"),
        string_field(data, "region"),
        string_field(data, "billing_mode"),
        string_field(data, "token_class"),
        require_integer(field_of(data, "pico_usd_per_token"), "pico_usd_per_token"),
        AbsentMeaning(string_field(data, "when_absent")),
    )


def basis_for(table: PriceTable, selections: Iterable[PricingSelection]) -> PricingBasis:
    """The rows of ``table`` under each selection, as a record embeds them; none is refused."""
    rows: list[PricingRow] = []
    for selection in sorted(
        set(selections), key=lambda s: (s.pricing_key, s.region, s.billing_mode)
    ):
        matching = [row for row in table.rows if _under(row, selection)]
        if not matching:
            raise ValueError(
                f"the price table has no rate for {selection.pricing_key} in {selection.region} "
                f"{selection.billing_mode}"
            )
        rows.extend(matching)
    return PricingBasis(table.digest, table.currency, table.effective_from, tuple(rows))


def _under(row: PricingRow, selection: PricingSelection) -> bool:
    return (row.pricing_key, row.region, row.billing_mode) == (
        selection.pricing_key,
        selection.region,
        selection.billing_mode,
    )


def cost_of(usage: Usage, selection: PricingSelection, basis: PricingBasis) -> Cost:
    """What ``usage`` cost under ``selection``'s rates in ``basis``: exact, with its completeness.

    >>> from datetime import date
    >>> basis = PricingBasis("0" * 64, "USD", date(2026, 9, 1), (
    ...     PricingRow("model-a", "eu-central-1", "on_demand", "input_tokens", 1_100_000),
    ...     PricingRow("model-a", "eu-central-1", "on_demand", "output_tokens", 5_500_000)))
    >>> model_a = PricingSelection("model-a", "eu-central-1", "on_demand")
    >>> cost_of(Usage((("input_tokens", 120), ("output_tokens", 30))), model_a, basis)
    Cost(pico_usd=297000000, complete=True)
    >>> cost_of(Usage((("input_tokens", 120),)), model_a, basis)
    Cost(pico_usd=132000000, complete=False)
    """
    for token_class in BILLED_ON_EVERY_CALL:
        if basis.rate(
            selection.pricing_key, selection.region, selection.billing_mode, token_class
        ) is None:
            raise ValueError(
                f"the basis holds no {token_class} rate under {selection.pricing_key} in "
                f"{selection.region} {selection.billing_mode}; nothing can be priced"
            )
    total = 0
    for token_class, tokens in usage.counters:
        rate = basis.rate(
            selection.pricing_key, selection.region, selection.billing_mode, token_class
        )
        if rate is None:
            raise ValueError(
                f"{token_class} was reported but the basis holds no rate for it under "
                f"{selection.pricing_key} in {selection.region} {selection.billing_mode}"
            )
        total += tokens * rate
    complete = all(
        usage.value(row.token_class) is not None or row.when_absent is AbsentMeaning.ZERO
        for row in basis.rows
        if _under(row, selection)
    )
    return Cost(total, complete)


def cost_of_reported(
    reported: ReportedUsage, selection: PricingSelection, basis: PricingBasis
) -> Cost:
    """What a send's reported usage cost: its counters under ``selection``'s rates, complete
    only if the rates covered them and the raw object was read whole as declared."""
    cost = cost_of(reported.counters, selection, basis)
    return Cost(cost.pico_usd, cost.complete and reported.complete)


def cumulative_cost(costs: Iterable[Cost | None]) -> Cost | None:
    """A cost over several: the priced ones summed, complete only if every one was priced whole.

    ``None`` when none was priced, since a sum over nothing is not a zero cost.

    >>> cumulative_cost([Cost(100, True), None, Cost(50, True)])
    Cost(pico_usd=150, complete=False)
    >>> cumulative_cost([None]) is None
    True
    """
    listed = list(costs)
    priced = [cost for cost in listed if cost is not None]
    if not priced:
        return None
    complete = len(priced) == len(listed) and all(cost.complete for cost in priced)
    return Cost(sum(cost.pico_usd for cost in priced), complete)


def billed_dispatches(calls: Iterable[ModelCall]) -> tuple[Dispatch, ...]:
    """The dispatches of ``calls`` that stand for a send or may: every one but those the
    client refused before sending, in order."""
    return tuple(
        dispatch
        for call in calls
        for dispatch in call.dispatches
        if dispatch.sends is not Sends.NONE
    )


def run_cost(calls: Iterable[ModelCall]) -> Cost | None:
    """The cumulative cost of a run's model calls as their dispatches record it: a floor
    when a send reported no usage under no zero-cost rule, or was never resolved."""
    return cumulative_cost(dispatch.cost for dispatch in billed_dispatches(calls))


def aggregate_usage(calls: Iterable[ModelCall]) -> UsageAggregate:
    """The run's usage summed per counter over the dispatches that reported it, with the coverage.

    A counter no dispatch reported is no row (never a zero), per the aggregate's own rule.
    """
    listed = list(calls)
    dispatches = [dispatch for call in listed for dispatch in call.dispatches]
    counters: list[tuple[str, int, int]] = []
    for name in USAGE_COUNTER_NAMES:
        values = [
            value
            for dispatch in dispatches
            if dispatch.usage is not None
            and (value := dispatch.usage.counters.value(name)) is not None
        ]
        if values:
            counters.append((name, sum(values), len(values)))
    return UsageAggregate(tuple(counters), len(listed), len(dispatches))
