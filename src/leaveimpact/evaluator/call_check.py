"""The call check: how each logical call stands under the registered table and policy, and
whether the attempt ended where its calls say it did.

The harness decides whether to ask a call again in one place, the within-call decision
(``core.call_decision``; the event log step's ruling on re-dispatch), from the call's
dispatches, the registered attribution table and the registered re-dispatch policy. The
evaluator runs it over every exported call and keeps each call's standing: answered, ended
as behaviour, permitted to dispatch again, failed by infrastructure, failed by defect, with
the row that read the last dispatch and the two flags the standing is decided by.

The decision refuses a dispatch whose recorded rule the table lacks or whose recorded
reading is not the row's, and says the evaluator reports that difference first; so the
attribution check runs before this, and a call carrying either finding is given no
standing here and no finding either.

Two findings per call, each a history no conforming harness produces, so both are tested on
hand-built exports alone:

- *A failed call that is not the failure.* The call stands failed by infrastructure or by
  defect and the attempt's failure is not anchored at its last dispatch's send: a call
  failing ends the attempt there, and a harness that ran on, to a report or to a failure
  elsewhere, recorded what the rulings do not allow. The export's constructor ties the
  defect direction already (a dispatch read as a defect is the failure's site); the
  infrastructure direction is this finding, kept as a finding and not a refusal, since a
  refusal would turn such a harness into an attempt closed without export.
- *Ended while a dispatch was permitted.* The attempt failed at a dispatch's send and that
  call stands as permitted to dispatch again: the harness gave up a dispatch the table and
  the policy allowed. Room is no excuse: a re-dispatch the account cannot fit enters
  finalization or ends the run at its cap, never as a failure.

A call standing answered, ended as behaviour, or permitted to dispatch again in an attempt
that did not fail at it, is no finding: what the loop does after such a call is the graph
step's. Evaluated with a table and a policy; a rules-only export reads zero calls.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.attribution import AttributionTable, RedispatchPolicy
from leaveimpact.core.call_decision import CallDecision, decide_call
from leaveimpact.core.model_calls import ModelCall
from leaveimpact.core.run_ending import DispatchPhase, DispatchSite
from leaveimpact.core.run_record import Failure
from leaveimpact.core.run_trace import ModelCallId
from leaveimpact.evaluator.attribution_check import AttributionCheck, AttributionFindingKind


class CallFindingKind(StrEnum):
    """What the check can find; a member is the wire format."""

    FAILED_CALL_NOT_THE_FAILURE = "failed_call_not_the_failure"
    ENDED_WHILE_DISPATCH_PERMITTED = "ended_while_dispatch_permitted"


@dataclass(frozen=True, slots=True)
class CallFinding:
    """One finding, by kind and the call it is about."""

    kind: CallFindingKind
    model_call: ModelCallId


@dataclass(frozen=True, slots=True)
class Standing:
    """How one call stands, as the within-call decision gives it: the decision, how many
    dispatches the call took, the identifier of the row that read its last dispatch with
    that row's flag for a new attempt (``None`` for an unresolved last dispatch, which no
    row reads), and the two flags that decided."""

    model_call: ModelCallId
    decision: CallDecision
    dispatches: int
    row: str | None
    row_permits_new_attempt: bool | None
    last_unresolved: bool
    maximum_reached: bool

    @property
    def failed(self) -> bool:
        return self.decision in (
            CallDecision.FAILED_BY_INFRASTRUCTURE,
            CallDecision.FAILED_BY_DEFECT,
        )


@dataclass(frozen=True, slots=True)
class CallCheck:
    """Every call's standing in the trace's order, a call with an attribution finding left
    out, and the findings in the same order."""

    standings: tuple[Standing, ...]
    findings: tuple[CallFinding, ...]

    def standing_of(self, call: ModelCallId) -> Standing | None:
        """The standing of ``call``, or ``None`` for a call given none."""
        for standing in self.standings:
            if standing.model_call == call:
                return standing
        return None


def check_calls(
    calls: Sequence[ModelCall],
    failure: Failure | None,
    table: AttributionTable,
    policy: RedispatchPolicy,
    attribution: AttributionCheck,
) -> CallCheck:
    """The standing of each of ``calls`` under ``table`` and ``policy``, held to ``failure``,
    the attempt's recorded failure; ``attribution`` is the attribution check over the same
    calls, whose rule and reading findings say which calls get no standing. Raises nothing
    for what the record states."""
    unreadable = {
        finding.model_call
        for finding in attribution.findings
        if finding.kind
        in (
            AttributionFindingKind.RULE_NOT_THE_TABLES,
            AttributionFindingKind.READING_NOT_THE_RULES,
        )
    }
    failed_at = (
        failure.site
        if failure is not None
        and isinstance(failure.site, DispatchSite)
        and failure.site.phase is DispatchPhase.SEND
        else None
    )
    standings: list[Standing] = []
    findings: list[CallFinding] = []
    for call in calls:
        if call.id in unreadable:
            continue
        decided = decide_call(
            [(dispatch.observation, dispatch.attribution) for dispatch in call.dispatches],
            table,
            policy,
        )
        row = decided.row
        standing = Standing(
            call.id,
            decided.decision,
            decided.dispatches,
            None if row is None else row.identifier,
            None if row is None else row.new_attempt,
            decided.last_unresolved,
            decided.maximum_reached,
        )
        standings.append(standing)
        ended_here = (
            failed_at is not None
            and failed_at.model_call == call.id
            and failed_at.dispatch == call.dispatches[-1].number
        )
        if standing.failed and not ended_here:
            findings.append(CallFinding(CallFindingKind.FAILED_CALL_NOT_THE_FAILURE, call.id))
        if (
            failed_at is not None
            and failed_at.model_call == call.id
            and standing.decision is CallDecision.DISPATCH_AGAIN
        ):
            findings.append(CallFinding(CallFindingKind.ENDED_WHILE_DISPATCH_PERMITTED, call.id))
    return CallCheck(tuple(standings), tuple(findings))


__all__ = ["CallCheck", "CallFinding", "CallFindingKind", "Standing", "check_calls"]
