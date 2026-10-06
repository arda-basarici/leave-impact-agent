"""The eligibility check: how an exported attempt ended, in the closed vocabulary the
eligibility function reads, and whether it permitted an attempt after it.

Whether a run may be attempted again is one total function in ``core`` (``eligibility``; the
event log step's ruling on new attempts), asked by admission of what the previous attempt's
log holds and by the evaluator of each exported attempt. This is the evaluator's side: the
record's status and failure are projected into an ending, the function is asked with the
attempt's number and the registered retry rule, and the answer is kept beside the attempt's
other trace metrics, where the attempt history reads it to find an attempt its predecessor
did not permit (``attempts``).

The projection, from the status and the failure's site:

- completed, or reported at the cap: those endings;
- a defect, at any site: a defect;
- infrastructure at a dispatch's send, read through the call's standing (``call_check``):
  unresolved at the maximum when the last dispatch has no outcome and the policy allows no
  more; a send failure naming the row that read it and that row's flag when a row did; an
  ending no rule names, at the site ``dispatch_send``, for an unresolved last dispatch
  below the maximum, a harness that gave up;
- infrastructure at the input bound, read through the group of counting requests for that
  request (``count_check``'s reuse key): exhausted when the group's decision under the
  policy's maximum is exhausted, an ending no rule names at the site ``input_bound``
  otherwise, an unclassified reading or a harness that gave up below the maximum;
- an abandonment, with how many dispatch intents the trace holds;
- any other harness site, an ending no rule names, by the site's name.

The function's ``recorded_defect`` is whether the failure is a defect: a dispatch read as a
defect is tied by the export's constructor to a failure by defect at its send, and a defect
an operator finalized keeps the defect as its failure, so no export records a defect its
failure does not name.

Evaluated with the registered retry rule and, for a failure at a dispatch's send or at the
input bound, the call's standing or the policy; ``None`` otherwise, which the attempt
history reads as a pair it cannot verify. Raises nothing for what a record states.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.attribution import RedispatchPolicy
from leaveimpact.core.eligibility import (
    Abandoned,
    Completed,
    EligibilityRule,
    EndedByDefect,
    Ending,
    InputBoundExhausted,
    OtherInfrastructure,
    ReportedAtCap,
    SendFailure,
    UnresolvedAtMaximum,
    new_attempt_eligibility,
)
from leaveimpact.core.input_bound import CountDecision, count_decision
from leaveimpact.core.registration import RetryRule
from leaveimpact.core.run_ending import (
    DispatchSite,
    HarnessSite,
    HarnessSiteName,
    InputBoundSite,
    OperationSite,
)
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import FailureCategory, TerminalStatus
from leaveimpact.evaluator.call_check import CallCheck
from leaveimpact.evaluator.count_check import reuse_key

DISPATCH_SEND = "dispatch_send"
"""The site of an infrastructure ending at a dispatch's send that no rule names: an unresolved
last dispatch below the maximum."""

INPUT_BOUND = "input_bound"
"""The site of an infrastructure ending at the input bound that no rule names: an unclassified
reading, or a group of counting requests given up below the maximum."""


class EndingKind(StrEnum):
    """The ending's kind as the eligibility function reads it; a member is the wire format."""

    COMPLETED = "completed"
    REPORTED_AT_CAP = "reported_at_cap"
    DEFECT = "defect"
    SEND_FAILURE = "send_failure"
    UNRESOLVED_AT_MAXIMUM = "unresolved_at_maximum"
    INPUT_BOUND_EXHAUSTED = "input_bound_exhausted"
    ABANDONED = "abandoned"
    OTHER_INFRASTRUCTURE = "other_infrastructure"


@dataclass(frozen=True, slots=True)
class ProjectedEnding:
    """The ending flat, for the artifact: its kind, and the one of ``rule`` with
    ``row_permits`` (a send failure), ``site`` (an ending no rule names) or
    ``dispatch_intents`` (an abandonment) the kind carries."""

    kind: EndingKind
    rule: str | None = None
    row_permits: bool | None = None
    site: str | None = None
    dispatch_intents: int | None = None


@dataclass(frozen=True, slots=True)
class EligibilityCheck:
    """How the attempt ended and whether it permitted an attempt after it, with the rule
    that decided and, for a send failure, the row whose flag was read."""

    ending: ProjectedEnding
    permitted: bool
    decided_by: EligibilityRule
    row: str | None


def ending_of(
    export: RunExport, calls: CallCheck | None, policy: RedispatchPolicy | None
) -> Ending | None:
    """The ending of the attempt ``export`` records, or ``None`` where the projection needs a
    standing or a policy it was not given."""
    record = export.record
    match record.status:
        case TerminalStatus.COMPLETED:
            return Completed()
        case TerminalStatus.CAP_EXHAUSTED:
            return ReportedAtCap()
        case TerminalStatus.FAILED:
            pass
    failure = record.failure
    if failure is None:
        return None
    if failure.category is FailureCategory.DEFECT:
        return EndedByDefect()
    site = failure.site
    match site:
        case DispatchSite():
            standing = None if calls is None else calls.standing_of(site.model_call)
            if standing is None:
                return None
            if standing.last_unresolved and standing.maximum_reached:
                return UnresolvedAtMaximum()
            if standing.row is not None and standing.row_permits_new_attempt is not None:
                return SendFailure(standing.row, standing.row_permits_new_attempt)
            return OtherInfrastructure(DISPATCH_SEND)
        case InputBoundSite():
            named = export.trace.counting_operation(site.counting_operation)
            if policy is None or named is None:
                return None
            key = reuse_key(named)
            readings = [
                count.reading
                for count in export.trace.counting_operations
                if reuse_key(count) == key
            ]
            if count_decision(readings, policy.max_dispatches) is CountDecision.EXHAUSTED:
                return InputBoundExhausted()
            return OtherInfrastructure(INPUT_BOUND)
        case HarnessSite():
            if site.site is HarnessSiteName.ABANDONED:
                return Abandoned(len(export.trace.dispatches))
            return OtherInfrastructure(site.site.value)
        case OperationSite():
            return OtherInfrastructure("operation")


def check_eligibility(
    export: RunExport,
    retry: RetryRule | None,
    calls: CallCheck | None,
    policy: RedispatchPolicy | None,
) -> EligibilityCheck | None:
    """Whether the attempt ``export`` records permitted an attempt after it under ``retry``;
    ``None`` without a retry rule or where the ending cannot be projected. Raises nothing
    for what the record states."""
    if retry is None:
        return None
    ending = ending_of(export, calls, policy)
    if ending is None:
        return None
    failure = export.record.failure
    decided = new_attempt_eligibility(
        ending,
        recorded_defect=failure is not None and failure.category is FailureCategory.DEFECT,
        attempt=export.attempt,
        retry=retry,
    )
    return EligibilityCheck(_projected(ending), decided.permitted, decided.rule, decided.row)


def _projected(ending: Ending) -> ProjectedEnding:
    match ending:
        case Completed():
            return ProjectedEnding(EndingKind.COMPLETED)
        case ReportedAtCap():
            return ProjectedEnding(EndingKind.REPORTED_AT_CAP)
        case EndedByDefect():
            return ProjectedEnding(EndingKind.DEFECT)
        case SendFailure():
            return ProjectedEnding(EndingKind.SEND_FAILURE, ending.rule, ending.row_permits)
        case UnresolvedAtMaximum():
            return ProjectedEnding(EndingKind.UNRESOLVED_AT_MAXIMUM)
        case InputBoundExhausted():
            return ProjectedEnding(EndingKind.INPUT_BOUND_EXHAUSTED)
        case Abandoned():
            return ProjectedEnding(EndingKind.ABANDONED, dispatch_intents=ending.dispatch_intents)
        case OtherInfrastructure():
            return ProjectedEnding(EndingKind.OTHER_INFRASTRUCTURE, site=ending.site)


__all__ = [
    "DISPATCH_SEND",
    "INPUT_BOUND",
    "EligibilityCheck",
    "EndingKind",
    "ProjectedEnding",
    "check_eligibility",
    "ending_of",
]
