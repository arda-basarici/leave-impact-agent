"""The within-call decision: a call stands by its last dispatch alone; a stopping
observation is read before the maximum is counted; an infrastructure reading is asked again
only where its row allows it and the maximum is not reached; a dispatch with no recorded
outcome may be followed until the maximum; a defect is never asked again; and a record that
does not agree with the table is the caller's error."""

import pytest

from leaveimpact.core.attribution import (
    UNRESOLVED_RULE,
    AttributionRow,
    AttributionTable,
    Cause,
    Match,
    ObservationKind,
    RedispatchPolicy,
    attribute,
)
from leaveimpact.core.call_decision import CallDecision, CallStanding, decide_call
from leaveimpact.core.model_calls import (
    Attribution,
    AttributionKind,
    BrokenStream,
    ClientError,
    ClientErrorKind,
    CompleteResponse,
    NoRecordedOutcome,
    Observation,
    RefusedBeforeSend,
    ServiceError,
)

BEHAVIOUR = AttributionKind.BEHAVIOUR
INFRASTRUCTURE = AttributionKind.INFRASTRUCTURE
POLICY = RedispatchPolicy(3, 500)


def table() -> AttributionTable:
    """Stand-in rows covering each way a dispatch can be read: an answer; a model's own
    error relayed by the service, read as behaviour; a request the harness built against
    its contract, a defect; a throttle that may be asked again; a denial that may not; and
    for every other kind a row that may be asked again."""
    service = ObservationKind.SERVICE_ERROR
    return AttributionTable(
        (
            AttributionRow("answer", Match(ObservationKind.COMPLETE_RESPONSE), BEHAVIOUR),
            AttributionRow(
                "bad_request",
                Match(service, cause=Cause.HARNESS_REQUEST_CONTRACT),
                AttributionKind.DEFECT,
            ),
            AttributionRow(
                "model_refusal", Match(service, original_statuses=frozenset({400})), BEHAVIOUR
            ),
            AttributionRow(
                "throttled",
                Match(service, http_statuses=frozenset({429})),
                INFRASTRUCTURE,
                redispatch=True,
                new_attempt=True,
            ),
            AttributionRow("service_error", Match(service), INFRASTRUCTURE, new_attempt=True),
            AttributionRow(
                "broken_stream",
                Match(ObservationKind.BROKEN_STREAM),
                INFRASTRUCTURE,
                redispatch=True,
            ),
            AttributionRow(
                "client_error", Match(ObservationKind.CLIENT_ERROR), INFRASTRUCTURE, redispatch=True
            ),
            AttributionRow(
                "refused_before_send",
                Match(ObservationKind.REFUSED_BEFORE_SEND),
                INFRASTRUCTURE,
            ),
        )
    )


ANSWER = CompleteResponse("end_turn", 800, 0)
THROTTLE = ServiceError(429, "ThrottlingException", None, "sig")
DENIAL = ServiceError(403, "AccessDeniedException", None, "sig")
MODEL_REFUSAL = ServiceError(424, "ModelErrorException", 400, "sig")
TIMEOUT = ClientError(ClientErrorKind.TIMEOUT, "read timed out")
LOST = NoRecordedOutcome()


def read(observation: Observation, cause: Cause | None = None) -> tuple[Observation, Attribution]:
    """The dispatch a conforming harness records for ``observation``."""
    return observation, attribute(table(), observation, cause)[0]


def standing(*observations: Observation) -> CallStanding:
    return decide_call([read(observation) for observation in observations], table(), POLICY)


def test_a_call_with_no_dispatch_may_take_its_first() -> None:
    held = standing()
    assert held == CallStanding(CallDecision.DISPATCH_AGAIN, 0, None, False, False)
    assert held.next_dispatch == 1


def test_a_complete_response_read_as_behaviour_is_an_answer() -> None:
    held = standing(ANSWER)
    assert held.decision is CallDecision.ANSWERED
    assert held.row is not None and held.row.identifier == "answer"


def test_a_behaviour_reading_of_an_error_ends_the_call_with_no_answer_and_no_failure() -> None:
    held = standing(MODEL_REFUSAL)
    assert held.decision is CallDecision.ENDED_AS_BEHAVIOUR
    assert held.row is not None and held.row.identifier == "model_refusal"


def test_a_defect_is_never_asked_again() -> None:
    dispatch = read(
        ServiceError(400, "ValidationException", None, "sig"), Cause.HARNESS_REQUEST_CONTRACT
    )
    held = decide_call([dispatch], table(), POLICY)
    assert held.decision is CallDecision.FAILED_BY_DEFECT
    assert not held.maximum_reached


@pytest.mark.parametrize(
    "observation", [THROTTLE, TIMEOUT, BrokenStream("connection reset")], ids=str
)
def test_an_infrastructure_reading_whose_row_allows_it_is_asked_again(
    observation: Observation,
) -> None:
    held = standing(observation)
    assert held.decision is CallDecision.DISPATCH_AGAIN
    assert held.next_dispatch == 2


@pytest.mark.parametrize("observation", [DENIAL, RefusedBeforeSend("no credentials")], ids=str)
def test_an_infrastructure_reading_whose_row_allows_none_fails_at_once(
    observation: Observation,
) -> None:
    held = standing(observation)
    assert held.decision is CallDecision.FAILED_BY_INFRASTRUCTURE
    assert not held.maximum_reached


def test_the_maximum_ends_a_call_that_could_otherwise_be_asked_again() -> None:
    held = standing(THROTTLE, THROTTLE, THROTTLE)
    assert held.decision is CallDecision.FAILED_BY_INFRASTRUCTURE
    assert held.maximum_reached
    assert held.row is not None and held.row.new_attempt


def test_one_dispatch_below_the_maximum_is_still_asked_again() -> None:
    assert standing(THROTTLE, TIMEOUT).decision is CallDecision.DISPATCH_AGAIN


@pytest.mark.parametrize(
    ("last", "expected"),
    [(ANSWER, CallDecision.ANSWERED), (MODEL_REFUSAL, CallDecision.ENDED_AS_BEHAVIOUR)],
)
def test_a_stopping_observation_on_the_last_permitted_dispatch_fails_nothing(
    last: Observation, expected: CallDecision
) -> None:
    held = standing(THROTTLE, THROTTLE, last)
    assert held.decision is expected
    assert held.maximum_reached


def test_a_dispatch_with_no_recorded_outcome_may_be_followed() -> None:
    held = standing(LOST)
    assert held == CallStanding(CallDecision.DISPATCH_AGAIN, 1, None, True, False)


def test_the_maximum_reached_on_an_unresolved_dispatch_fails_by_infrastructure() -> None:
    held = standing(THROTTLE, LOST, LOST)
    assert held == CallStanding(CallDecision.FAILED_BY_INFRASTRUCTURE, 3, None, True, True)


def test_only_the_last_dispatch_decides() -> None:
    assert standing(DENIAL, ANSWER).decision is CallDecision.ANSWERED
    assert standing(LOST, THROTTLE).decision is CallDecision.DISPATCH_AGAIN


def test_under_a_maximum_of_one_nothing_is_asked_again() -> None:
    once = RedispatchPolicy(1, 0)
    assert decide_call([], table(), once).decision is CallDecision.DISPATCH_AGAIN
    for observation in (THROTTLE, LOST):
        held = decide_call([read(observation)], table(), once)
        assert held.decision is CallDecision.FAILED_BY_INFRASTRUCTURE


def test_a_rule_the_table_does_not_hold_is_the_callers_error() -> None:
    dispatch = (THROTTLE, Attribution(INFRASTRUCTURE, "some_other_tables_row"))
    with pytest.raises(ValueError, match="the table holds no row 'some_other_tables_row'"):
        decide_call([dispatch], table(), POLICY)


def test_a_reading_that_is_not_the_rows_is_the_callers_error() -> None:
    dispatch = (THROTTLE, Attribution(BEHAVIOUR, "throttled"))
    with pytest.raises(ValueError, match="the row throttled reads infrastructure"):
        decide_call([dispatch], table(), POLICY)


def test_an_unresolved_dispatch_is_read_by_no_row_whatever_it_names() -> None:
    dispatch = (LOST, Attribution(AttributionKind.UNRESOLVED, UNRESOLVED_RULE))
    assert decide_call([dispatch], table(), POLICY).row is None
