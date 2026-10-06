"""Each call's standing under the registered table and policy, and whether the attempt ended
where its calls say. The sixteen format fixtures carry no finding under their table and
policy; the two findings are reached from hand-built exports, since no conforming harness
produces either; a call the attribution check faults gets no standing."""

from leaveimpact.core import (
    UNRESOLVED_RULE,
    Answer,
    AttributionKind,
    ClientError,
    ClientErrorKind,
    DispatchPhase,
    DispatchSite,
    Failure,
    FailureCategory,
    ModelCall,
    ModelCallId,
    NoRecordedOutcome,
    RunExport,
    ServiceError,
)
from leaveimpact.core.call_decision import CallDecision
from leaveimpact.core.model_calls import Observation
from leaveimpact.evaluator.attribution_check import AttributionFindingKind, check_attributions
from leaveimpact.evaluator.call_check import (
    CallCheck,
    CallFinding,
    CallFindingKind,
    Standing,
    check_calls,
)
from tests.unit.format_fixtures import (
    FIXTURES,
    NOVA_CUT,
    POLICY,
    ROLE,
    TABLE,
    answered,
    dispatch,
    export,
)

KINDS = CallFindingKind
CALL = ModelCallId("call-1")
TIMED_OUT = ClientError(ClientErrorKind.TIMEOUT, "timeout")
THROTTLED = ServiceError(429, "ThrottlingException", None, "too many requests")
NOVA_ERROR = ServiceError(400, "ValidationException", 400, NOVA_CUT)
AT_SEND = Failure(
    FailureCategory.INFRASTRUCTURE, DispatchSite(CALL, 1, DispatchPhase.SEND), "the send failed"
)
ANSWER = Answer(True, (), ())


def checked(run: RunExport) -> CallCheck:
    calls = run.trace.model_calls
    attribution = check_attributions(TABLE, POLICY, calls)
    return check_calls(calls, run.record.failure, TABLE, POLICY, attribution)


def one_dispatch(observation: Observation, rule: str) -> ModelCall:
    """The first call, one dispatch read as infrastructure under ``rule``."""
    sent = dispatch(6, observation, AttributionKind.INFRASTRUCTURE, rule=rule)
    return ModelCall(CALL, ROLE, (sent,), None)


# --- The producers there are -------------------------------------------------------------------


def test_the_format_fixtures_carry_no_finding_and_stand_as_their_last_dispatch_says() -> None:
    standings = {
        name: [s.decision for s in checked(build()).standings] for name, build in FIXTURES.items()
    }
    assert all(checked(build()).findings == () for build in FIXTURES.values())
    assert standings["the Nova signature beside another model error"] == [
        CallDecision.ENDED_AS_BEHAVIOUR,
        CallDecision.ANSWERED,
    ]
    assert standings["an attempt admitted and never claimed"] == []
    assert all(
        decisions == [CallDecision.ANSWERED]
        for name, decisions in standings.items()
        if name
        not in (
            "the Nova signature beside another model error",
            "an attempt admitted and never claimed",
            "a request whose input bound was never established",
        )
    )


def test_a_standing_holds_the_row_its_flag_and_the_two_deciding_flags() -> None:
    # Unresolved then answered: the last dispatch decides, read by the stop-reason row.
    run = FIXTURES["an unresolved dispatch followed by an answered one"]()
    (standing,) = checked(run).standings
    assert standing == Standing(
        CALL, CallDecision.ANSWERED, 2, "registered-stop-reason", False, False, False
    )
    lost = ModelCall(
        CALL,
        ROLE,
        (dispatch(6, NoRecordedOutcome(), AttributionKind.UNRESOLVED, rule=UNRESOLVED_RULE),),
        None,
    )
    (unresolved,) = checked(export((lost,), failure=AT_SEND)).standings
    assert unresolved == Standing(CALL, CallDecision.DISPATCH_AGAIN, 1, None, None, True, False)


def test_a_call_the_attribution_check_faults_gets_no_standing_and_no_finding() -> None:
    run = export((one_dispatch(TIMED_OUT, "no-such-rule"),), failure=AT_SEND)
    attribution = check_attributions(TABLE, POLICY, run.trace.model_calls)
    assert [f.kind for f in attribution.findings] == [AttributionFindingKind.RULE_NOT_THE_TABLES]
    assert checked(run) == CallCheck((), ())


# --- The two findings --------------------------------------------------------------------------


def test_a_call_standing_failed_that_is_not_the_attempts_failure() -> None:
    # Timed out under a row allowing no re-dispatch, and the attempt went on to complete.
    run = export((one_dispatch(TIMED_OUT, "gave_up"), answered("call-2", 10, ANSWER)))
    assert checked(run).findings == (CallFinding(KINDS.FAILED_CALL_NOT_THE_FAILURE, CALL),)
    # The same call, the attempt failed there: no finding.
    assert checked(export((one_dispatch(TIMED_OUT, "gave_up"),), failure=AT_SEND)).findings == ()


def test_an_attempt_that_failed_while_its_call_could_be_dispatched_again() -> None:
    # Throttled under the unmatched row, which allows a re-dispatch, one of three taken.
    run = export((one_dispatch(THROTTLED, "unmatched"),), failure=AT_SEND)
    check = checked(run)
    assert check.standings[0].decision is CallDecision.DISPATCH_AGAIN
    assert check.findings == (CallFinding(KINDS.ENDED_WHILE_DISPATCH_PERMITTED, CALL),)


def test_a_call_left_while_permitted_or_ended_as_behaviour_in_a_completed_attempt() -> None:
    # The loop's choice to stop asking is the graph step's: neither is a finding.
    gave_up_a_permitted_dispatch = export(
        (one_dispatch(THROTTLED, "unmatched"), answered("call-2", 10, ANSWER))
    )
    assert checked(gave_up_a_permitted_dispatch).findings == ()
    behaviour = ModelCall(
        CALL,
        ROLE,
        (dispatch(6, NOVA_ERROR, AttributionKind.BEHAVIOUR, rule="nova-cut-tool-use"),),
        None,
    )
    assert checked(export((behaviour, answered("call-2", 10, ANSWER)))).findings == ()
