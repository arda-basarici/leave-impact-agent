"""An attempt's ending and its status, each a pure function of the log's state.

*The ending* is derived from a closed log by one function, whoever closed it (the event log
step's ruling on recovery and endings, part 1). A recorded stopping defect is the ending,
failed by defect at its site, an operator's close included: that close finalized a defect
and abandoned nothing, and the command is kept beside the failure as who closed (format
3's first fork). Otherwise the ending is the closing event's own: completed, reported at
the cap, failed at the site the worker named, or abandoned, which is an infrastructure
failure at the abandoned site holding the command. Who closed and why the attempt failed
are two facts, both in the log, and the export states both.

*The status* is the three fields the job seam exposes (the ruling on the job seam, part
1): the attempt (open, or closed with its ending), the segment (never started, open,
stopped) and the approval (not requested, requested and unapproved, approved). No field
says a worker is alive: a log cannot know it.
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
)
from leaveimpact.agent.log_transition import AttemptState
from leaveimpact.core.run_ending import (
    Abandonment,
    Approval,
    ApprovalState,
    HarnessSite,
    HarnessSiteName,
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
    defect = state.defect
    if defect is not None:
        reason = closing.reason if isinstance(closing, Failed) else defect.reason
        failure = Failure(FailureCategory.DEFECT, defect.site, reason)
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


__all__ = ["Ending", "SegmentStatus", "Status", "approval_of", "ending_of", "status_of"]
