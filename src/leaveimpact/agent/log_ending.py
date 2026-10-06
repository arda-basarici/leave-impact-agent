"""An attempt's ending and its status, each a pure function of the log's state.

*The ending* is derived from a closed log by one function, whoever closed it (the event log
step's ruling on recovery and endings, part 1, read for every stopping failure at the
pure-log group's review). A recorded stopping failure is the ending, at its site and in
its category, an operator's close included: that close finalized it and abandoned nothing,
and the command is kept beside the failure as who closed (format 3's first fork). The
stopping failures are a malformed record and a dispatch read as a defect (defects), a call
that stood failed by infrastructure, and a count group that was refused (a defect),
exhausted or failed in an unclassified way. Otherwise the ending is the closing event's own:
completed, reported at
the cap, failed at the site the worker named, or abandoned, which is an infrastructure
failure at the abandoned site holding the command. Who closed and why the attempt failed
are two facts, both in the log, and the export states both.

*The status* is the three fields the job seam exposes (the ruling on the job seam, part
1): the attempt (open, or closed with its ending), the segment (never started, open,
stopped) and the approval (not requested, requested and unapproved, approved). No field
says a worker is alive: a log cannot know it.

*The eligibility ending* is the same closed log read into the vocabulary the eligibility
function in ``core`` takes, so admission can ask whether the predecessor permits a new
attempt (the ruling on placement, part 1: the agent projects events into the function's
inputs and the evaluator projects exports into the same ones; the two projections are
held equal over every fixture by a test). A failure at a dispatch's send is read through
the within-call decision over the call's dispatches, one at the input bound through the
count decision over the request's counting group, each outcome re-read and never the
worker's stored reading.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.agent.log_events import (
    Abandoned,
    ApprovalRequested,
    Approved,
    CapExhausted,
    Completed,
    Failed,
    Producer,
    call_id,
    count_id,
)
from leaveimpact.agent.log_transition import (
    AttemptState,
    Rules,
    calls_of,
    count_group,
    counts_of,
)
from leaveimpact.core import eligibility
from leaveimpact.core.call_decision import decide_call
from leaveimpact.core.input_bound import CountDecision, count_decision
from leaveimpact.core.run_ending import (
    Abandonment,
    Approval,
    ApprovalState,
    DispatchSite,
    HarnessSite,
    HarnessSiteName,
    InputBoundSite,
    OperationSite,
)
from leaveimpact.core.run_parts_json import review_payload_digest
from leaveimpact.core.run_record import Failure, FailureCategory, TerminalStatus


@dataclass(frozen=True, slots=True)
class Ending:
    """How a closed attempt ended: the status, the failure when it failed, and the abandon
    command when one closed it."""

    status: TerminalStatus
    failure: Failure | None
    abandonment: Abandonment | None


def ending_of(state: AttemptState) -> Ending:
    """The ending of ``state``'s log; ``ValueError`` while the attempt is open."""
    closed = state.closed
    if closed is None:
        raise ValueError("an open attempt has no ending")
    closing = state.closing
    assert closing is not None
    abandonment = None
    if isinstance(closing, Abandoned):
        producer = closed.envelope
        assert isinstance(producer, Producer)
        abandonment = Abandonment(producer.identity, closing.expected_generation, closing.reason)
    stopped = state.stopped
    if stopped is not None:
        reason = closing.reason if isinstance(closing, Failed) else stopped.reason
        failure = Failure(stopped.category, stopped.site, reason)
        return Ending(TerminalStatus.FAILED, failure, abandonment)
    match closing:
        case Completed():
            return Ending(TerminalStatus.COMPLETED, None, None)
        case CapExhausted():
            return Ending(TerminalStatus.CAP_EXHAUSTED, None, None)
        case Failed():
            return Ending(
                TerminalStatus.FAILED, Failure(closing.category, closing.site, closing.reason), None
            )
        case Abandoned():
            failure = Failure(
                FailureCategory.INFRASTRUCTURE,
                HarnessSite(HarnessSiteName.ABANDONED),
                _abandonment_reason(state),
            )
            return Ending(TerminalStatus.FAILED, failure, abandonment)


def _abandonment_reason(state: AttemptState) -> str:
    if not state.segments:
        return "no worker claimed the attempt"
    return "no worker resumed the attempt"


def approval_of(state: AttemptState) -> Approval:
    """The approval as the log states it: not requested, requested and unapproved, or
    approved by whoever delivered it, over the requested payload's digest."""
    request = state.approval_requested
    if request is None:
        return Approval(ApprovalState.NOT_REQUESTED, None, None)
    asked = request.event
    assert isinstance(asked, ApprovalRequested)
    digest = review_payload_digest(asked.claims, asked.composition)
    approved = state.approved
    if approved is None:
        return Approval(ApprovalState.REQUESTED_UNAPPROVED, None, digest)
    given = approved.event
    assert isinstance(given, Approved)
    return Approval(ApprovalState.APPROVED, given.approver, digest)


# --- Status ----------------------------------------------------------------------------------


class SegmentStatus(StrEnum):
    """Where the attempt's execution stands; a member is the wire format."""

    NEVER_STARTED = "never_started"
    OPEN = "open"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class Status:
    """The three fields: the attempt (its ending when closed), the segment, the approval."""

    ending: Ending | None
    segment: SegmentStatus
    approval: ApprovalState

    @property
    def open(self) -> bool:
        return self.ending is None


def status_of(state: AttemptState) -> Status:
    """The status of ``state``'s log, open or closed."""
    current = state.current_segment
    if current is None:
        segment = SegmentStatus.NEVER_STARTED
    elif current.ended:
        segment = SegmentStatus.STOPPED
    else:
        segment = SegmentStatus.OPEN
    ending = None if state.closed is None else ending_of(state)
    return Status(ending, segment, approval_of(state).state)


def eligibility_ending_of(state: AttemptState, rules: Rules) -> eligibility.Ending:
    """The ending of ``state``'s closed log in the eligibility function's vocabulary, under
    the registered ``rules``; ``ValueError`` while the attempt is open."""
    ending = ending_of(state)
    match ending.status:
        case TerminalStatus.COMPLETED:
            return eligibility.Completed()
        case TerminalStatus.CAP_EXHAUSTED:
            return eligibility.ReportedAtCap()
        case TerminalStatus.FAILED:
            pass
    failure = ending.failure
    assert failure is not None, "a failed attempt records its failure"
    if failure.category is FailureCategory.DEFECT:
        return eligibility.EndedByDefect()
    site = failure.site
    match site:
        case DispatchSite():
            return _at_dispatch_send(state, site, rules)
        case InputBoundSite():
            return _at_input_bound(state, site, rules)
        case HarnessSite():
            if site.site is HarnessSiteName.ABANDONED:
                intents = sum(len(call.intents) for call in calls_of(state))
                return eligibility.Abandoned(intents)
            return eligibility.OtherInfrastructure(site.site.value)
        case OperationSite():
            return eligibility.OtherInfrastructure("operation")


def _at_dispatch_send(
    state: AttemptState, site: DispatchSite, rules: Rules
) -> eligibility.Ending:
    if rules.table is None or rules.redispatch is None:
        raise ValueError("a failure at a dispatch's send needs the registered table and policy")
    call = next(
        (call for call in calls_of(state) if call_id(call.ordinal) == site.model_call), None
    )
    if call is None:
        raise ValueError(f"the log holds no call {site.model_call!r} to read the failure at")
    standing = decide_call(call.pairs(), rules.table, rules.redispatch)
    if standing.last_unresolved and standing.maximum_reached:
        return eligibility.UnresolvedAtMaximum()
    row = standing.row
    if row is not None:
        return eligibility.SendFailure(row.identifier, row.new_attempt)
    return eligibility.OtherInfrastructure(eligibility.DISPATCH_SEND)


def _at_input_bound(
    state: AttemptState, site: InputBoundSite, rules: Rules
) -> eligibility.Ending:
    if rules.redispatch is None:
        raise ValueError("a failure at the input bound needs the registered policy")
    named = next(
        (count for count in counts_of(state) if count_id(count.key) == site.counting_operation),
        None,
    )
    if named is None:
        raise ValueError(
            f"the log holds no counting operation {site.counting_operation!r} to read the "
            f"failure at"
        )
    group = count_group(state, named.key)
    readings = [count.reading() for count in group]
    match count_decision(readings, rules.redispatch.max_dispatches):
        case CountDecision.EXHAUSTED:
            return eligibility.InputBoundExhausted()
        case CountDecision.DEFECT:
            return eligibility.EndedByDefect()
        case _:
            return eligibility.OtherInfrastructure(eligibility.INPUT_BOUND)


__all__ = [
    "Ending",
    "SegmentStatus",
    "Status",
    "approval_of",
    "eligibility_ending_of",
    "ending_of",
    "status_of",
]
