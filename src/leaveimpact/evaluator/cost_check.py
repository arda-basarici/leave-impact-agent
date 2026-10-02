"""The record's usage and cost, verified against the trace: three layers, each from what the
one below recomputed.

Cost is a reported metric, and a run record states it three times over: each model call
holds the usage its provider reported and the cost the harness priced it at, and the
record block holds the usage summed and the cost summed. The harness wrote all of it. The
evaluator copies none of it (the investigator milestone's fourth build step, ruling 5):

1. *Usage.* The counters and the number of calls are summed again from the trace's model
   calls and compared with the record's aggregate, counter by counter, the count of calls
   that reported each included.
2. *Each call's cost.* Every call that reported usage is priced again, from the pricing
   selection the record holds for its role and the rates the record embeds, through the
   function the harness priced it with (``core``'s ``cost_of``), and compared with the
   cost the call records.
3. *The cumulative cost.* Summed from the costs layer 2 *recomputed*, never from the
   recorded ones, and compared with the record's. A harness that priced every call wrong
   and summed its own numbers right agrees with itself; it does not agree with this.

What is kept is the recomputed usage and costs, which a cost table reads, and the
findings. A finding is one of two kinds. A *harness* finding says the record's reading of
its own trace is not the trace's: a counter, the call count, a call's cost, the cumulative
cost. A *pricing* finding says the embedded rates could not price what was reported: a
reported token class the basis holds no rate for, or a call that reported usage and
records no cost. Neither raises, and neither removes the run: the recomputed numbers
stand, and a call that cannot be priced leaves the run's cost a floor, as a call that
reported no usage does (``Cost.complete``).

Two limits. The run's duration is the harness's own and is taken as recorded: the trace
holds no run-level timestamps to check it against. And this verifies arithmetic against
the rates the record embeds, not that those rates are the committed price table's; that
is a digest check, owed when the table is an asset.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.pricing import aggregate_usage, cost_of, cumulative_cost
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import UsageAggregate
from leaveimpact.core.run_trace import USAGE_COUNTER_NAMES, Cost, ModelCallId


class CostFindingKind(StrEnum):
    """What the verification can find; a member is the wire format."""

    USAGE_DIFFERS = "usage_differs"
    CALL_COUNT_DIFFERS = "call_count_differs"
    CALL_COST_DIFFERS = "call_cost_differs"
    CUMULATIVE_COST_DIFFERS = "cumulative_cost_differs"
    RATE_MISSING = "rate_missing"
    CALL_NOT_PRICED = "call_not_priced"

    @property
    def is_pricing(self) -> bool:
        """Whether the embedded rates could not price what was reported; the other kinds are
        the harness's reading of its own trace differing from the trace."""
        return self in (CostFindingKind.RATE_MISSING, CostFindingKind.CALL_NOT_PRICED)


@dataclass(frozen=True, slots=True)
class CostFinding:
    """One disagreement, by kind and where: the usage counter's name, the model call's id, or
    nothing for the two that are about the run as a whole."""

    kind: CostFindingKind
    at: str | None = None


@dataclass(frozen=True, slots=True)
class CostCheck:
    """A run's usage and cost as the trace gives them, and where the record says otherwise.

    ``usage`` is summed from the trace's model calls, with the record's duration.
    ``call_costs`` holds each model call's recomputed cost in the trace's order, ``None``
    for a call that reported no usage or that the embedded rates cannot price. ``cost`` is
    their sum, ``None`` when none could be priced, complete only when every call was.
    """

    usage: UsageAggregate
    call_costs: tuple[tuple[ModelCallId, Cost | None], ...]
    cost: Cost | None
    findings: tuple[CostFinding, ...]


def check_cost(export: RunExport) -> CostCheck:
    """The usage and the cost of the run ``export`` records, recomputed, with every
    disagreement between them and the record. Raises nothing for what the record states."""
    record, calls = export.record, export.trace.model_calls
    findings: list[CostFinding] = []

    usage = aggregate_usage(calls, record.usage.duration_ms)
    if usage.model_calls != record.usage.model_calls:
        findings.append(CostFinding(CostFindingKind.CALL_COUNT_DIFFERS))
    findings.extend(
        CostFinding(CostFindingKind.USAGE_DIFFERS, name)
        for name in USAGE_COUNTER_NAMES
        if usage.value(name) != record.usage.value(name)
    )

    selections = dict(record.pricing_selections)
    call_costs: list[tuple[ModelCallId, Cost | None]] = []
    for call in calls:
        recomputed: Cost | None = None
        if call.usage is not None:
            try:
                recomputed = cost_of(call.usage, selections[call.role], record.pricing)
            except ValueError:
                findings.append(CostFinding(CostFindingKind.RATE_MISSING, call.id))
        if recomputed is not None and call.cost is None:
            findings.append(CostFinding(CostFindingKind.CALL_NOT_PRICED, call.id))
        elif call.cost != recomputed:
            findings.append(CostFinding(CostFindingKind.CALL_COST_DIFFERS, call.id))
        call_costs.append((call.id, recomputed))

    cost = cumulative_cost(cost for _, cost in call_costs)
    if cost != record.cost:
        findings.append(CostFinding(CostFindingKind.CUMULATIVE_COST_DIFFERS))
    return CostCheck(usage, tuple(call_costs), cost, tuple(findings))


__all__ = ["CostCheck", "CostFinding", "CostFindingKind", "check_cost"]
