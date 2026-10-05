"""The within-call decision: how a logical model call stands after the dispatches it has taken.

Nothing retries beneath a dispatch, so asking a call again is the harness's own decision,
and it is made in one place (the event log step's ruling on re-dispatch): this function,
from the call's dispatches as the log holds them, the registered attribution table and the
registered re-dispatch policy. The worker runs it after each outcome and again on recovery,
when the last dispatch may have no outcome at all. The evaluator runs it over an exported
call to check that the run did what the registration allowed.

A call stands in one of five ways, decided by its last dispatch alone:

- *answered*: a complete response the table reads as behaviour;
- *ended as behaviour*: something other than a complete response that the table reads as
  behaviour, a service error relaying the model's own refusal for one. The call has no
  answer and nothing failed; what the loop does next is the loop's;
- *dispatch again*: an infrastructure reading whose row allows another dispatch, or a
  dispatch with no recorded outcome, while the policy's maximum is not reached;
- *failed by infrastructure*: an infrastructure reading whose row allows no other
  dispatch, or the maximum reached on a dispatch that was not a stopping one;
- *failed by defect*: the table read a defect, which is never asked again.

A stopping observation is read before the maximum is counted, so a call whose last
permitted dispatch is answered, or ends as behaviour, fails nothing.

*Permitted is not authorized.* "Dispatch again" says the table and the policy allow one
more. Whether it is sent is decided under the attempt's lock, with the worker's ownership,
the attempt's state and the room left in the run's account (``run_account.authorize``).

The standing keeps what the question after a failure needs: the row that read the last
dispatch, whether that dispatch was unresolved, and whether the maximum was reached
(``eligibility``). A dispatch's attribution names a row of the table by its identifier; a
name the table does not hold, or a reading that is not the row's, is refused here as the
caller's error, since the evaluator reports that difference itself before it asks this.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.attribution import AttributionRow, AttributionTable, RedispatchPolicy
from leaveimpact.core.model_calls import (
    Attribution,
    AttributionKind,
    CompleteResponse,
    NoRecordedOutcome,
    Observation,
)


class CallDecision(StrEnum):
    """How a logical call stands; a member is the wire format."""

    ANSWERED = "answered"
    ENDED_AS_BEHAVIOUR = "ended_as_behaviour"
    DISPATCH_AGAIN = "dispatch_again"
    FAILED_BY_INFRASTRUCTURE = "failed_by_infrastructure"
    FAILED_BY_DEFECT = "failed_by_defect"


@dataclass(frozen=True, slots=True)
class CallStanding:
    """The decision on one call, with what decided it.

    ``dispatches`` is how many the call has taken, so its next is numbered one more.
    ``row`` is the table's row that read the last dispatch, ``None`` when the call has no
    dispatch yet or its last has no recorded outcome, which no row reads.
    ``last_unresolved`` says the last dispatch has no recorded outcome and
    ``maximum_reached`` that the policy allows the call no further dispatch.
    """

    decision: CallDecision
    dispatches: int
    row: AttributionRow | None
    last_unresolved: bool
    maximum_reached: bool

    @property
    def next_dispatch(self) -> int:
        """The number a further dispatch of the call would take."""
        return self.dispatches + 1


def decide_call(
    dispatches: Sequence[tuple[Observation, Attribution]],
    table: AttributionTable,
    policy: RedispatchPolicy,
) -> CallStanding:
    """How the call with ``dispatches``, in order, stands under ``table`` and ``policy``.

    Each dispatch is what it observed and the attribution recorded for it. A call that has
    taken no dispatch may take its first.

    >>> from leaveimpact.core.attribution import Match, ObservationKind
    >>> rows = tuple(
    ...     AttributionRow(kind.value, Match(kind), AttributionKind.INFRASTRUCTURE,
    ...                    redispatch=True)
    ...     for kind in ObservationKind)
    >>> table, policy = AttributionTable(rows), RedispatchPolicy(2, 500)
    >>> decide_call([], table, policy).decision.value
    'dispatch_again'
    >>> lost = (NoRecordedOutcome(), Attribution(AttributionKind.UNRESOLVED, "no_recorded_outcome"))
    >>> decide_call([lost, lost], table, policy).decision.value
    'failed_by_infrastructure'
    """
    taken = len(dispatches)
    reached = taken >= policy.max_dispatches
    if not dispatches:
        return CallStanding(CallDecision.DISPATCH_AGAIN, 0, None, False, reached)
    observation, attribution = dispatches[-1]
    if isinstance(observation, NoRecordedOutcome):
        decision = CallDecision.FAILED_BY_INFRASTRUCTURE if reached else CallDecision.DISPATCH_AGAIN
        return CallStanding(decision, taken, None, True, reached)
    row = table.row(attribution.rule)
    if row is None:
        raise ValueError(f"the table holds no row {attribution.rule!r} to read a dispatch by")
    if row.reading is not attribution.kind:
        raise ValueError(
            f"the row {row.identifier} reads {row.reading.value}; the dispatch records "
            f"{attribution.kind.value} under it"
        )
    match row.reading:
        case AttributionKind.BEHAVIOUR:
            decision = (
                CallDecision.ANSWERED
                if isinstance(observation, CompleteResponse)
                else CallDecision.ENDED_AS_BEHAVIOUR
            )
        case AttributionKind.DEFECT:
            decision = CallDecision.FAILED_BY_DEFECT
        case _:
            decision = (
                CallDecision.DISPATCH_AGAIN
                if row.redispatch and not reached
                else CallDecision.FAILED_BY_INFRASTRUCTURE
            )
    return CallStanding(decision, taken, row, False, reached)


__all__ = ["CallDecision", "CallStanding", "decide_call"]
