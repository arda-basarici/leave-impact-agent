"""How an exported attempt ended, in the vocabulary the eligibility function reads, and
whether it permitted an attempt after it. The sixteen format fixtures project to the endings
their names say and two of them permit a successor; every ending kind is reached, and the
check is not evaluated without a retry rule or where the projection needs a standing or a
policy it was not given."""

from dataclasses import replace

from leaveimpact.core import (
    UNRESOLVED_RULE,
    AttributionKind,
    AttributionTable,
    CountingOperationId,
    Dispatch,
    DispatchPhase,
    DispatchSite,
    Failure,
    FailureCategory,
    HarnessSite,
    HarnessSiteName,
    InputBoundSite,
    ModelCall,
    ModelCallId,
    NoRecordedOutcome,
    RetryRule,
    RunExport,
    ServiceError,
    TerminalStatus,
)
from leaveimpact.core.eligibility import EligibilityRule
from leaveimpact.evaluator.attribution_check import check_attributions
from leaveimpact.evaluator.call_check import CallCheck, check_calls
from leaveimpact.evaluator.eligibility_check import (
    DISPATCH_SEND,
    INPUT_BOUND,
    EligibilityCheck,
    EndingKind,
    ProjectedEnding,
    check_eligibility,
    ending_of,
)
from tests.unit.format_fixtures import FIXTURES, POLICY, ROLE, TABLE, dispatch, export

RETRY = RetryRule(FailureCategory.INFRASTRUCTURE, 3)
CALL = ModelCallId("call-1")
THROTTLED = ServiceError(429, "ThrottlingException", None, "too many requests")
RULES = EligibilityRule


def calls_of(run: RunExport, table: AttributionTable = TABLE) -> CallCheck:
    calls = run.trace.model_calls
    return check_calls(
        calls, run.record.failure, table, POLICY, check_attributions(table, POLICY, calls)
    )


def checked(run: RunExport, table: AttributionTable = TABLE) -> EligibilityCheck | None:
    return check_eligibility(run, RETRY, calls_of(run, table), POLICY)


def failed_at_send(*dispatches: Dispatch, number: int) -> RunExport:
    call = ModelCall(CALL, ROLE, dispatches, None)
    failure = Failure(
        FailureCategory.INFRASTRUCTURE, DispatchSite(CALL, number, DispatchPhase.SEND), "failed"
    )
    return export((call,), failure=failure)


# --- The producers there are -------------------------------------------------------------------


def test_the_format_fixtures_end_as_their_names_say_and_two_permit_a_successor() -> None:
    endings: dict[str, tuple[EndingKind, bool, EligibilityRule]] = {}
    for name, build in FIXTURES.items():
        check = checked(build())
        assert check is not None, name
        endings[name] = (check.ending.kind, check.permitted, check.decided_by)
    assert endings["an attempt admitted and never claimed"] == (
        EndingKind.ABANDONED,
        True,
        RULES.ABANDONED_BEFORE_ANY_INTENT,
    )
    assert endings["a request whose input bound was never established"] == (
        EndingKind.INPUT_BOUND_EXHAUSTED,
        True,
        RULES.INPUT_BOUND_EXHAUSTED,
    )
    assert endings["an abandoned attempt"] == (
        EndingKind.ABANDONED,
        False,
        RULES.ABANDONED_AFTER_AN_INTENT,
    )
    assert endings["a tool call whose result was lost before it was logged"] == (
        EndingKind.ABANDONED,
        False,
        RULES.ABANDONED_AFTER_AN_INTENT,
    )
    assert endings["a recorded defect an operator finalized"] == (
        EndingKind.DEFECT,
        False,
        RULES.DEFECT,
    )
    assert endings["a multi-tool answer whose first call ends the attempt"] == (
        EndingKind.DEFECT,
        False,
        RULES.DEFECT,
    )
    completed = [name for name, (kind, _, _) in endings.items() if kind is EndingKind.COMPLETED]
    assert len(completed) == 10
    assert all(
        endings[name] == (EndingKind.COMPLETED, False, RULES.GRADED_RESULT) for name in completed
    )


def test_the_check_is_not_evaluated_without_a_retry_rule() -> None:
    run = FIXTURES["facts beside tools in one answer"]()
    assert check_eligibility(run, None, calls_of(run), POLICY) is None


# --- Each ending ---------------------------------------------------------------------------------


def test_reported_at_the_cap_is_a_graded_result() -> None:
    run = FIXTURES["facts beside tools in one answer"]()
    at_cap = replace(run, record=replace(run.record, status=TerminalStatus.CAP_EXHAUSTED))
    assert checked(at_cap) == EligibilityCheck(
        ProjectedEnding(EndingKind.REPORTED_AT_CAP), False, RULES.GRADED_RESULT, None
    )


def test_a_send_failure_carries_its_row_and_the_rows_flag_decides() -> None:
    run = failed_at_send(
        dispatch(2, THROTTLED, AttributionKind.INFRASTRUCTURE, rule="unmatched"), number=1
    )
    assert checked(run) == EligibilityCheck(
        ProjectedEnding(EndingKind.SEND_FAILURE, "unmatched", False),
        False,
        RULES.SEND_ROW,
        "unmatched",
    )
    permitting = AttributionTable(
        tuple(
            replace(row, new_attempt=True) if row.identifier == "unmatched" else row
            for row in TABLE.rows
        )
    )
    assert checked(run, permitting) == EligibilityCheck(
        ProjectedEnding(EndingKind.SEND_FAILURE, "unmatched", True),
        True,
        RULES.SEND_ROW,
        "unmatched",
    )
    # Without the call's standing the ending cannot be projected.
    assert check_eligibility(run, RETRY, None, POLICY) is None


def test_an_unresolved_last_dispatch_permits_at_the_maximum_and_is_unnamed_below_it() -> None:
    lost = [
        dispatch(
            2 + 2 * n,
            NoRecordedOutcome(),
            AttributionKind.UNRESOLVED,
            rule=UNRESOLVED_RULE,
            number=n + 1,
        )
        for n in range(3)
    ]
    exhausted = failed_at_send(*lost, number=3)
    assert checked(exhausted) == EligibilityCheck(
        ProjectedEnding(EndingKind.UNRESOLVED_AT_MAXIMUM), True, RULES.UNRESOLVED_AT_MAXIMUM, None
    )
    gave_up = failed_at_send(lost[0], number=1)
    assert checked(gave_up) == EligibilityCheck(
        ProjectedEnding(EndingKind.OTHER_INFRASTRUCTURE, site=DISPATCH_SEND),
        False,
        RULES.NO_RULE_NAMES_THE_ENDING,
        None,
    )


def test_an_input_bound_failure_is_exhausted_or_unnamed_by_its_groups_decision() -> None:
    run = FIXTURES["a request whose input bound was never established"]()
    assert ending_of(run, None, None) is None
    two = run.trace.counting_operations[:2]
    failure = run.record.failure
    assert failure is not None
    gave_up = replace(
        run,
        record=replace(run.record, failure=replace(failure, site=InputBoundSite(two[-1].id))),
        trace=replace(run.trace, counting_operations=two),
    )
    assert checked(gave_up) == EligibilityCheck(
        ProjectedEnding(EndingKind.OTHER_INFRASTRUCTURE, site=INPUT_BOUND),
        False,
        RULES.NO_RULE_NAMES_THE_ENDING,
        None,
    )
    assert isinstance(failure.site, InputBoundSite)
    assert failure.site.counting_operation == CountingOperationId("count-3")


def test_a_harness_site_no_rule_names_and_the_maximum_reached() -> None:
    run = FIXTURES["facts beside tools in one answer"]()
    failed = replace(
        run,
        record=replace(
            run.record,
            status=TerminalStatus.FAILED,
            failure=Failure(
                FailureCategory.INFRASTRUCTURE, HarnessSite(HarnessSiteName.PREFETCH), "down"
            ),
            approval=FIXTURES["an abandoned attempt"]().record.approval,
        ),
    )
    assert checked(failed) == EligibilityCheck(
        ProjectedEnding(EndingKind.OTHER_INFRASTRUCTURE, site="prefetch"),
        False,
        RULES.NO_RULE_NAMES_THE_ENDING,
        None,
    )
    third = replace(FIXTURES["an attempt admitted and never claimed"](), attempt=3)
    check = checked(third)
    assert check is not None
    assert (check.permitted, check.decided_by) == (False, RULES.MAXIMUM_REACHED)
    assert check.ending == ProjectedEnding(EndingKind.ABANDONED, dispatch_intents=0)


def test_an_abandonment_counts_the_dispatch_intents_the_trace_holds() -> None:
    check = checked(FIXTURES["an abandoned attempt"]())
    assert check is not None
    assert check.ending == ProjectedEnding(EndingKind.ABANDONED, dispatch_intents=1)
