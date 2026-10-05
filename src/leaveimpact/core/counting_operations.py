"""A token-counting request as a run records it: what was asked, what came back, how the
worker read it.

A model request is authorized on an upper bound of its input tokens, and the one
registered method asks the provider to count the request before it is sent
(``input_bound``). That counting call is an operation of its own in the log, with its own
identity, request binding, result and failure evidence, and its latency is active time
(the event log step's ruling on counting). It takes no call-cap slot and no allocation.
Every counting operation an attempt made is exported, the failed ones included, so an
auditor can see that a dispatch's bound rests on a count that succeeded and preceded it,
that the count retries kept their maximum, and that a failed count was read as what its
error says.

As on a model dispatch, two things are kept apart. The *outcome* is what arrived, as it
arrived: the count, a service error, a client error, a local error, or no recorded
outcome. The *reading* is how the worker classified it, which decided whether it counted
again, ended the attempt as an infrastructure failure, or ended it as a defect; the
method's specification fixes the classification (``input_bound.result_of_error``), the
reading is stored because only a stored value can disagree with the outcome, and the
evaluator reads the outcome again and reports a reading that differs. Two readings are not
classifications and are tied here: a count that arrived is read as counted and an
operation with no recorded outcome as unresolved.

A local error is an exception raised on the worker's side that is neither a timeout nor a
lost connection; it is recorded by its qualified type alone, no message, since a message
may hold scenario content and a job's log is public.

Positions are the attempt's global event order: the start, committed before the remote
call so that a worker killed mid-count is seen to have consumed one of the maximum, and
the outcome when one was recorded.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.enums import require_member
from leaveimpact.core.input_bound import CountResult, RegisteredInputBound, result_of_error
from leaveimpact.core.model_calls import NoRecordedOutcome
from leaveimpact.core.run_trace import (
    ClientErrorKind,
    CountingOperationId,
    require_digest,
    require_integer,
    require_opaque_id,
)


@dataclass(frozen=True, slots=True)
class Counted:
    """The provider counted the request. ``provider_request_id`` is the service's id for the
    counting request, ``None`` when none was recorded."""

    input_tokens: int
    provider_request_id: str | None
    latency_ms: int

    def __post_init__(self) -> None:
        require_integer(self.input_tokens, "a counted input in tokens")
        if self.provider_request_id is not None:
            require_opaque_id(self.provider_request_id, "a provider request id")
        require_integer(self.latency_ms, "a counting request's latency in ms")


@dataclass(frozen=True, slots=True)
class CountServiceError:
    """The service answered the counting request with an error."""

    http_status: int
    code: str
    message_signature: str
    provider_request_id: str | None
    latency_ms: int

    def __post_init__(self) -> None:
        require_integer(self.http_status, "an HTTP status", minimum=100)
        require_opaque_id(self.code, "a service error code")
        if self.provider_request_id is not None:
            require_opaque_id(self.provider_request_id, "a provider request id")
        require_integer(self.latency_ms, "a counting request's latency in ms")


@dataclass(frozen=True, slots=True)
class CountClientError:
    """The client gave up on the counting request with no answer: a timeout or a lost
    connection, so whether the service counted is unknown."""

    kind: ClientErrorKind
    latency_ms: int

    def __post_init__(self) -> None:
        require_member(self.kind, ClientErrorKind, "a client error's kind")
        require_integer(self.latency_ms, "a counting request's latency in ms")


@dataclass(frozen=True, slots=True)
class CountLocalError:
    """An exception on the worker's side that is no timeout and no lost connection, by its
    qualified type only."""

    exception_type: str

    def __post_init__(self) -> None:
        require_opaque_id(self.exception_type, "a qualified exception type")


type CountOutcome = (
    Counted | CountServiceError | CountClientError | CountLocalError | NoRecordedOutcome
)


def read_outcome(method: RegisteredInputBound, outcome: CountOutcome) -> CountResult:
    """How ``outcome`` is read under ``method``'s specification: the reading the worker
    should have recorded, and the one the evaluator compares with the recorded one.

    >>> method = RegisteredInputBound("provider_count", 1)
    >>> read_outcome(method, Counted(4_096, "req-1", 100)).value
    'counted'
    >>> read_outcome(method, CountServiceError(403, "AccessDeniedException", "sig", None, 90)).value
    'refused'
    >>> read_outcome(method, CountLocalError("builtins.KeyError")).value
    'unclassified'
    """
    match outcome:
        case Counted():
            return CountResult.COUNTED
        case NoRecordedOutcome():
            return CountResult.UNRESOLVED
        case CountServiceError():
            return result_of_error(method, code=outcome.code)
        case CountClientError():
            return result_of_error(method, client_error=outcome.kind)
        case CountLocalError():
            return result_of_error(method)


@dataclass(frozen=True, slots=True)
class CountingOperation:
    """One counting request: its identity, what it was asked about, where it sits, what came
    back and how the worker read it.

    ``request_digest`` is the digest of the whole inference request the count was for, the
    key a durable count is reused under together with the identifier and the method. The
    outcome position is held exactly when an outcome was recorded, after the start. The
    reading is counted exactly for a count that arrived and unresolved exactly for no
    recorded outcome; for an error it is one of the three failure readings, and which one
    is the worker's statement, checked by the evaluator against ``read_outcome``.

    >>> method = RegisteredInputBound("provider_count", 1)
    >>> CountingOperation(
    ...     CountingOperationId("count-1"), method, "model-base", "a" * 64, 1, 4, None,
    ...     Counted(4_096, None, 100), CountResult.COUNTED,
    ... )
    Traceback (most recent call last):
    ...
    ValueError: an outcome position is held exactly when an outcome was recorded
    """

    id: CountingOperationId
    method: RegisteredInputBound
    counting_identifier: str
    request_digest: str
    segment: int
    start_position: int
    outcome_position: int | None
    outcome: CountOutcome
    reading: CountResult

    def __post_init__(self) -> None:
        require_opaque_id(self.id, "a counting operation id")
        require_opaque_id(self.counting_identifier, "the counting identifier")
        require_digest(self.request_digest, "the counted request's digest")
        require_integer(self.segment, "a segment number", minimum=1)
        require_integer(self.start_position, "a start position", minimum=1)
        require_member(self.reading, CountResult, "a counting operation's reading")
        unrecorded = isinstance(self.outcome, NoRecordedOutcome)
        if (self.outcome_position is None) != unrecorded:
            raise ValueError("an outcome position is held exactly when an outcome was recorded")
        if self.outcome_position is not None:
            require_integer(self.outcome_position, "an outcome position", minimum=1)
            if self.outcome_position <= self.start_position:
                raise ValueError("a counting operation's outcome is logged after its start")
        if (self.reading is CountResult.UNRESOLVED) != unrecorded:
            raise ValueError(
                "a counting operation is unresolved exactly when no outcome was recorded"
            )
        if (self.reading is CountResult.COUNTED) != isinstance(self.outcome, Counted):
            raise ValueError("a counting operation is read as counted exactly when a count arrived")

    @property
    def positions(self) -> tuple[int, ...]:
        """The positions this operation took in the attempt's event order."""
        if self.outcome_position is None:
            return (self.start_position,)
        return (self.start_position, self.outcome_position)


__all__ = [
    "CountClientError",
    "CountLocalError",
    "CountOutcome",
    "CountServiceError",
    "Counted",
    "CountingOperation",
    "read_outcome",
]
