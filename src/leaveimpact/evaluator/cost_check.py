"""The record's usage and cost, verified against the trace: three layers, each from what the
one below recomputed.

Cost is a reported metric, and a run record states it three times over: each dispatch of
a model call holds the usage its provider reported and the cost the harness priced it at,
and the record block holds the usage summed and the cost summed. The harness wrote all of
it. The evaluator copies none of it (the investigator milestone's fourth build step,
ruling 5; the contract step's rulings for the dispatch):

1. *Usage.* The counters, the number of calls and the number of dispatches are summed
   again from the trace and compared with the record's aggregate, counter by counter, the
   count of dispatches that reported each included. A dispatch's counters are read again
   from its raw usage object by the function the harness read them with.
2. *Each dispatch's cost.* Every dispatch that reported usage is priced again, from the
   pricing selection the record holds for its call's role and the rates the record embeds,
   through the function the harness priced it with (``core``'s ``cost_of_reported``), and
   compared with the cost the dispatch records. A dispatch the client refused before
   sending was no send and has no cost to check.
3. *The cumulative cost.* Summed from the costs layer 2 *recomputed*, never from the
   recorded ones, and compared with the record's. A harness that priced every dispatch
   wrong and summed its own numbers right agrees with itself; it does not agree with this.

What is kept is the recomputed usage and costs, which a cost table reads, and the
findings. A finding is one of two kinds. A *harness* finding says the record's reading of
its own trace is not the trace's: a counter, the call count, a call's cost, the cumulative
cost. A *pricing* finding says the embedded rates could not price what was reported: a
reported token class the basis holds no rate for, or a call that reported usage and
records no cost. Neither raises, and neither removes the run: the recomputed numbers
stand, and a dispatch that cannot be priced leaves the run's cost a floor, as one that
reported no usage or was never resolved does (``Cost.complete``).

Three limits. The run's duration is its evidenced active time, computed from the segments
the record holds, which are the harness's own and are taken as recorded. A zero-cost rule
a dispatch names is taken as recorded too: whether the rule is evidenced for the
configuration is the price table's to say, owed when the table is an asset. And this
verifies arithmetic against the rates the record embeds, not that those rates are the
committed table's; that is the same debt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.pricing import (
    aggregate_usage,
    billed_dispatches,
    cost_of_reported,
    cumulative_cost,
)
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import UsageAggregate
from leaveimpact.core.run_timing import evidenced_active_ms
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

    ``usage`` is summed from the trace's dispatches. ``duration_ms`` is the run's evidenced
    active time, from the record's segments. ``call_costs`` holds each model call's
    recomputed cost in the trace's order, the sum over its dispatches that stand for a
    send, ``None`` for a call none of whose sends could be priced. ``cost`` is the sum over
    every such dispatch of the run, ``None`` when none could be priced, complete only when
    every one was. ``possible_sends`` is how many dispatches stand for a send or may, which
    is what tells the two meanings of an absent cost apart: with none, nothing was sent and
    nothing is owed (no model called, or every request refused before sending); with some,
    a send went unpriced and the cost is unknown.
    """

    usage: UsageAggregate
    possible_sends: int
    duration_ms: int
    call_costs: tuple[tuple[ModelCallId, Cost | None], ...]
    cost: Cost | None
    findings: tuple[CostFinding, ...]


def check_cost(export: RunExport) -> CostCheck:
    """The usage and the cost of the run ``export`` records, recomputed, with every
    disagreement between them and the record. Raises nothing for what the record states."""
    record, calls = export.record, export.trace.model_calls
    findings: list[CostFinding] = []

    usage = aggregate_usage(calls)
    if (usage.model_calls, usage.dispatches) != (
        record.usage.model_calls,
        record.usage.dispatches,
    ):
        findings.append(CostFinding(CostFindingKind.CALL_COUNT_DIFFERS))
    findings.extend(
        CostFinding(CostFindingKind.USAGE_DIFFERS, name)
        for name in USAGE_COUNTER_NAMES
        if usage.value(name) != record.usage.value(name)
    )

    selections = dict(record.pricing_selections)
    call_costs: list[tuple[ModelCallId, Cost | None]] = []
    recomputed_costs: list[Cost | None] = []
    for call in calls:
        of_call: list[Cost | None] = []
        for dispatch in billed_dispatches((call,)):
            recomputed: Cost | None = None
            if dispatch.usage is not None:
                try:
                    recomputed = cost_of_reported(
                        dispatch.usage, selections[call.role], record.pricing
                    )
                except ValueError:
                    findings.append(CostFinding(CostFindingKind.RATE_MISSING, call.id))
            elif dispatch.zero_cost_rule is not None:
                recomputed = Cost(0, True)
            if recomputed is not None and dispatch.cost is None:
                findings.append(CostFinding(CostFindingKind.CALL_NOT_PRICED, call.id))
            elif dispatch.cost != recomputed:
                findings.append(CostFinding(CostFindingKind.CALL_COST_DIFFERS, call.id))
            of_call.append(recomputed)
        call_costs.append((call.id, cumulative_cost(of_call)))
        recomputed_costs.extend(of_call)

    cost = cumulative_cost(recomputed_costs)
    if cost != record.cost:
        findings.append(CostFinding(CostFindingKind.CUMULATIVE_COST_DIFFERS))
    return CostCheck(
        usage,
        len(recomputed_costs),
        evidenced_active_ms(record.timing),
        tuple(call_costs),
        cost,
        tuple(findings),
    )


__all__ = ["CostCheck", "CostFinding", "CostFindingKind", "check_cost"]
