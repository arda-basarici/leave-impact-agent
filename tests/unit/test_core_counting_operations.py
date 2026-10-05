"""A counting operation holds what came back and how the worker read it, and the two are tied
where the reading is no classification: a count that arrived is read as counted, no recorded
outcome as unresolved, and an error as one of the three failure readings, which the
evaluator reads again from the outcome under the method's specification."""

import pytest

from leaveimpact.core.counting_operations import (
    CountClientError,
    Counted,
    CountingOperation,
    CountLocalError,
    CountOutcome,
    CountServiceError,
    read_outcome,
)
from leaveimpact.core.input_bound import CountResult, RegisteredInputBound
from leaveimpact.core.model_calls import NoRecordedOutcome
from leaveimpact.core.run_trace import ClientErrorKind, CountingOperationId

METHOD = RegisteredInputBound("provider_count", 1)
DIGEST = "a" * 64
COUNTED = Counted(4_096, "req-1", 100)
THROTTLED = CountServiceError(429, "ThrottlingException", "rate exceeded", "req-2", 80)
DENIED = CountServiceError(403, "AccessDeniedException", "not authorized", None, 90)
ODD = CountServiceError(500, "ModelStreamErrorException", "stream", "req-3", 70)
TIMED_OUT = CountClientError(ClientErrorKind.TIMEOUT, 30_000)
LOCAL = CountLocalError("builtins.KeyError")


def operation(
    outcome: CountOutcome, reading: CountResult, *, start: int = 4, recorded: bool = True
) -> CountingOperation:
    return CountingOperation(
        CountingOperationId("count-1"),
        METHOD,
        "model-a-base",
        DIGEST,
        1,
        start,
        start + 1 if recorded else None,
        outcome,
        reading,
    )


def test_an_outcome_is_read_under_the_methods_specification() -> None:
    assert read_outcome(METHOD, COUNTED) is CountResult.COUNTED
    assert read_outcome(METHOD, NoRecordedOutcome()) is CountResult.UNRESOLVED
    assert read_outcome(METHOD, THROTTLED) is CountResult.FAILED
    assert read_outcome(METHOD, TIMED_OUT) is CountResult.FAILED
    assert read_outcome(METHOD, DENIED) is CountResult.REFUSED
    assert read_outcome(METHOD, ODD) is CountResult.UNCLASSIFIED
    # A local exception is no network fault: nothing shows it would pass on a retry.
    assert read_outcome(METHOD, LOCAL) is CountResult.UNCLASSIFIED


def test_counted_and_unresolved_are_tied_to_their_outcomes_and_an_error_is_a_failure() -> None:
    assert operation(COUNTED, CountResult.COUNTED).positions == (4, 5)
    assert operation(NoRecordedOutcome(), CountResult.UNRESOLVED, recorded=False).positions == (4,)
    with pytest.raises(ValueError, match="read as counted exactly when a count arrived"):
        operation(THROTTLED, CountResult.COUNTED)
    with pytest.raises(ValueError, match="read as counted exactly when a count arrived"):
        operation(COUNTED, CountResult.FAILED)
    with pytest.raises(ValueError, match="unresolved exactly when no outcome was recorded"):
        operation(THROTTLED, CountResult.UNRESOLVED)
    with pytest.raises(ValueError, match="outcome position is held exactly when an outcome"):
        operation(NoRecordedOutcome(), CountResult.UNRESOLVED)
    with pytest.raises(ValueError, match="outcome position is held exactly when an outcome"):
        operation(COUNTED, CountResult.COUNTED, recorded=False)
    with pytest.raises(ValueError, match="outcome is logged after its start"):
        CountingOperation(
            CountingOperationId("count-1"), METHOD, "m", DIGEST, 1, 5, 5, COUNTED,
            CountResult.COUNTED,
        )
    # Which failure reading an error gets is the worker's statement: the type holds any of
    # the three, and the evaluator reports one that differs from ``read_outcome``.
    for reading in (CountResult.FAILED, CountResult.REFUSED, CountResult.UNCLASSIFIED):
        assert operation(DENIED, reading).reading is reading
        assert read_outcome(METHOD, operation(DENIED, reading).outcome) is CountResult.REFUSED


def test_an_outcome_refuses_what_a_record_could_not_hold() -> None:
    with pytest.raises(ValueError, match="a counted input in tokens is at least 0"):
        Counted(-1, None, 100)
    with pytest.raises(ValueError, match="a provider request id is a non-empty identifier"):
        Counted(1, " ", 100)
    with pytest.raises(ValueError, match="an HTTP status is at least 100"):
        CountServiceError(99, "ThrottlingException", "sig", None, 1)
    with pytest.raises(ValueError, match="a client error's kind"):
        CountClientError("timeout", 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="a qualified exception type is a non-empty identifier"):
        CountLocalError("")
    with pytest.raises(ValueError, match="the counted request's digest"):
        CountingOperation(
            CountingOperationId("count-1"), METHOD, "m", "abc", 1, 4, 5, COUNTED,
            CountResult.COUNTED,
        )
