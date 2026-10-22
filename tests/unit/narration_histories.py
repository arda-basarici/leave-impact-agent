"""Histories for the outcome variants the format fixtures' histories do not reach, each the
shortest log the transition admits that holds the variant: a read that found nothing and
one the wrapper refused, two skipped reads, an unreachable source, a count the service
refused and one that failed unclassified, the three dispatch failures that end a call at
its send, a finalization that ends at the cap, a human's approval resumed under an
operator's override, and a failure in the harness's own prefetch. Most are open; the
narration reads an open log as readily as a closed one.

Test infrastructure, in the manner of ``log_histories``: written from the rulings' cases
and the transition's own refusals, not from any reader.
"""

from __future__ import annotations

from collections.abc import Callable

from leaveimpact.agent.log_events import (
    ApprovalRequested,
    Approved,
    CapExhausted,
    CommitOverride,
    Completed,
    CountOutcomeLogged,
    Failed,
    FinalizationEntered,
    LoggedEvent,
    LoggedSettlement,
    ModelReadKey,
    OperationEvent,
    OperationResult,
    OperationSkip,
    PrefetchKey,
    Resumed,
    SegmentEnded,
    SegmentStarted,
)
from leaveimpact.core import (
    AbsentOutcome,
    Approver,
    AttributionKind,
    BrokenStream,
    ClientError,
    ClientErrorKind,
    CountLocalError,
    CountResult,
    CountServiceError,
    DispatchPhase,
    DispatchSite,
    FailureCategory,
    HarnessRevision,
    HarnessSite,
    HarnessSiteName,
    ModelCallId,
    RefusedBeforeSend,
    RefusedCallOutcome,
    ReservationState,
    Source,
    TreeState,
    UndispatchedReason,
    UnreachableOutcome,
)
from leaveimpact.core.model_calls import Observation
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as h

SETTLEMENT = LoggedSettlement(cases.ALLOCATION, ReservationState.RECONCILED, None, 7)
OTHER_COMMIT = "c" * 40
OTHER_REVISION = HarnessRevision(OTHER_COMMIT, TreeState.CLEAN)
DIGEST = cases.review_payload_digest((), cases.RULES)

Build = Callable[[], tuple[LoggedEvent, ...]]


def _claimed() -> h.History:
    log = h.History()
    log.admit(h.inputs(reservation=10 * cases.ALLOCATION))
    log.claim()
    return log


def _counted(log: h.History) -> None:
    log.worker(h.count_start("call-1"), offset=400)
    log.worker(h.count_outcome("call-1"), offset=500)


def _two_tool_calls(log: h.History) -> None:
    """A read, a count, and one answered call asking for a ticket and an employee."""
    log.worker(h.prefetch(1, "work_items", Source.JIRA), offset=100)
    _counted(log)
    log.worker(h.intent(1, shown=("prefetch/1",)), offset=600)
    response = h.body(
        "tool_use",
        h.tool_use("tu_1", "work_item", {"id": "ticket_042"}),
        h.tool_use("tu_2", "employee", {"id": "emp_999"}),
    )
    log.worker(h.outcome(1, 1, h.complete("tool_use"), response=response), offset=700)


def reads_absent_and_refused() -> tuple[LoggedEvent, ...]:
    log = _claimed()
    _two_tool_calls(log)
    log.worker(h.model_read(1, "tu_1", AbsentOutcome()), offset=800)
    refused = OperationResult(
        "employee", None, {"id": "emp_999"}, RefusedCallOutcome("the id names no employee")
    )
    log.worker(OperationEvent(ModelReadKey(1, "tu_2"), refused), offset=900)
    return log.logged()


def reads_skipped() -> tuple[LoggedEvent, ...]:
    log = _claimed()
    _two_tool_calls(log)
    log.worker(
        OperationEvent(ModelReadKey(1, "tu_1"), OperationSkip(UndispatchedReason.CAP)), offset=800
    )
    log.worker(
        OperationEvent(
            ModelReadKey(1, "tu_2"), OperationSkip(UndispatchedReason.SOURCE_UNREACHABLE)
        ),
        offset=900,
    )
    return log.logged()


def read_unreachable() -> tuple[LoggedEvent, ...]:
    log = _claimed()
    unreachable = OperationResult(
        "work_items",
        Source.JIRA,
        {},
        UnreachableOutcome(Source.JIRA, "connection refused after three retries"),
    )
    log.worker(OperationEvent(PrefetchKey(1), unreachable), offset=100)
    return log.logged()


def count_refused() -> tuple[LoggedEvent, ...]:
    log = _claimed()
    log.worker(h.prefetch(1, "work_items", Source.JIRA), offset=100)
    log.worker(h.count_start("call-1"), offset=400)
    error = CountServiceError(403, "AccessDeniedException", "not authorized to count", "req-1", 90)
    log.worker(h.count_outcome("call-1", error, CountResult.REFUSED), offset=500)
    return log.logged()


def count_unclassified() -> tuple[LoggedEvent, ...]:
    log = _claimed()
    log.worker(h.prefetch(1, "work_items", Source.JIRA), offset=100)
    log.worker(h.count_start("call-1"), offset=400)
    log.worker(
        CountOutcomeLogged(
            h.key_of("call-1"), CountLocalError("builtins.KeyError"), CountResult.UNCLASSIFIED
        ),
        offset=500,
    )
    return log.logged()


def _failed_send(observation: Observation, rule: str) -> tuple[LoggedEvent, ...]:
    log = _claimed()
    _counted(log)
    log.worker(h.intent(1), offset=600)
    log.worker(h.outcome(1, 1, observation, AttributionKind.INFRASTRUCTURE, rule=rule), offset=700)
    return log.logged()


def broken_stream() -> tuple[LoggedEvent, ...]:
    return _failed_send(BrokenStream("connection reset mid-stream"), "stream")


def client_error() -> tuple[LoggedEvent, ...]:
    return _failed_send(ClientError(ClientErrorKind.TIMEOUT, "read timed out"), "gave_up")


def refused_before_send() -> tuple[LoggedEvent, ...]:
    return _failed_send(
        RefusedBeforeSend("the request exceeds the client's size bound"), "never_sent"
    )


def finalized_at_the_cap() -> tuple[LoggedEvent, ...]:
    log = _claimed()
    _counted(log)
    log.worker(h.intent(1), offset=600)
    log.worker(
        h.outcome(1, 1, h.complete(), response=h.body("end_turn", h.text("Done."))), offset=700
    )
    log.worker(FinalizationEntered(), offset=800)
    log.worker(ApprovalRequested((), cases.RULES, True), offset=900)
    log.outside(h.AUTOMATIC.identity, Approved(Approver.AUTOMATIC, DIGEST))
    log.worker(Resumed(), offset=1_000)
    log.worker(CapExhausted(SETTLEMENT), offset=1_100)
    return log.logged()


def overridden_claim_after_a_human_approval() -> tuple[LoggedEvent, ...]:
    log = _claimed()
    _counted(log)
    log.worker(h.intent(1), offset=600)
    log.worker(
        h.outcome(1, 1, h.complete(), response=h.body("end_turn", h.text("Done."))), offset=700
    )
    log.worker(ApprovalRequested((), cases.RULES, False), offset=7_000)
    log.worker(SegmentEnded(), offset=7_900)
    log.outside("human:reviewer", Approved(Approver.HUMAN, DIGEST))
    log.generation += 1
    override = CommitOverride("operator:ops", cases.COMMIT, OTHER_COMMIT)
    log.worker(SegmentStarted(OTHER_REVISION, "nonce-2", "launch-2", override), offset=0)
    log.worker(Resumed(), offset=50)
    log.worker(Completed(SETTLEMENT), offset=2_050)
    return log.logged()


def parse_failed_response() -> tuple[LoggedEvent, ...]:
    """A complete response whose body has no output object, which the log accepts, followed
    by the worker's failure at the dispatch's parse phase (the external read of the step's
    commits, second finding)."""
    log = _claimed()
    _counted(log)
    log.worker(h.intent(1), offset=600)
    unreadable: dict[str, object] = {
        "stopReason": "end_turn",
        "usage": dict(cases.REPORTED),
        "metrics": {"latencyMs": 840},
    }
    log.worker(h.outcome(1, 1, h.complete(), response=unreadable), offset=700)
    log.worker(
        Failed(
            FailureCategory.DEFECT,
            DispatchSite(ModelCallId("call-1"), 1, DispatchPhase.PARSE),
            "a response holds an output object",
            SETTLEMENT,
        ),
        offset=800,
    )
    return log.logged()


def failed_in_the_harness() -> tuple[LoggedEvent, ...]:
    log = _claimed()
    log.worker(
        Failed(
            FailureCategory.INFRASTRUCTURE,
            HarnessSite(HarnessSiteName.PREFETCH),
            "the prefetch raised before its first read",
            SETTLEMENT,
        ),
        offset=100,
    )
    return log.logged()


VARIANTS: dict[str, Build] = {
    "a read that found nothing and one the wrapper refused": reads_absent_and_refused,
    "two skipped reads": reads_skipped,
    "an unreachable source": read_unreachable,
    "a count the service refused": count_refused,
    "a count that failed unclassified": count_unclassified,
    "a broken stream": broken_stream,
    "a client error": client_error,
    "a request refused before send": refused_before_send,
    "a finalization that ends at the cap": finalized_at_the_cap,
    "a human's approval resumed under an override": overridden_claim_after_a_human_approval,
    "a failure in the harness's prefetch": failed_in_the_harness,
    "a response the parser cannot read": parse_failed_response,
}
"""Each variant history by what it holds."""
