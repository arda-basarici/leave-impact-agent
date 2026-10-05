"""The input bound: what is known of a request's input tokens before it is sent, and by what method.

A model call is authorized on its worst case, committed before the request leaves: an upper
bound of its input tokens and the most it may generate (the event log step's rulings on the
ledger and on counting). The guarantee that a run stays inside its caps holds only while
each such bound is true, so a method of bounding is admitted on two things together: a
justified basis for calling its number an upper bound, and probes that showed no breach. An
estimate tuned to be usually right is not a bound and is not here.

One method is registered, ``provider_count``: the bound is the number the provider's
counting call returns for the request, with no margin added. Its basis is the provider's
documented statement that the count matches what inference would be charged, the inference
profile's constituents all being the model the count is asked of, and seventeen requests
from 14 to 87,231 tokens on which the count ran 16 to 49 above the reported input and never
below (``probes/FINDINGS.md``, ``input-bound``). None of the three is a proof. A request's
byte length was measured beside it and declined: the inequality held on the request shapes
tried, and nothing establishes it for the input a provider constructs from a body, which is
another object than the JSON that was sent. A model family with no counting call therefore
has no method, and no run that calls it is registered.

The count is asked of another identifier than the one that infers: the counting call is
served for a base model id and refused for the cross-region profile in front of it. The
registration names both and nothing derives one from the other.

A method's specification is closed. It lists the request fields its count covers and the
fields outside the count it tolerates because they add no input; a request holding any
other field is refused a bound, since the count would be of a different request than the
one sent. It lists the error codes that say the model or the request cannot be counted at
all, which is a wrong configuration and so a defect, apart from every other failure of the
counting call, which is the provider's and transient.

What the ledger takes is an *established bound* or nothing: the method and its version, the
identifier the count was asked of, the digest of the request it covers, the number, and
the counting operation it rests on. A bound is reused only for the request, identifier and
method it was established for, so a re-dispatch of the same request does not count again
and a changed request cannot ride an old count.

A counting request is retried on a count of its own under the re-dispatch policy's
maximum. A request that was started and has no recorded outcome consumed one of those: a
worker that died after asking is not given the maximum again.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from leaveimpact.core.call_settings import CallConfiguration
from leaveimpact.core.run_trace import require_digest, require_integer, require_opaque_id

PROVIDER_COUNT = "provider_count"
"""The bound is the provider's own count of the request, taken as returned."""

MAX_OUTPUT_SETTING = "max_tokens"
"""The setting that limits everything a call may generate. A configuration without it has no
worst case and is refused one."""


# --- The methods ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InputBoundMethod:
    """One method's frozen specification: what its count covers, what it tolerates outside
    the count, and which errors of the counting call say the request cannot be counted.

    A change to any of the three is a new ``version``: a run's evidence names the version
    it was bounded under.
    """

    name: str
    version: int
    counted_fields: tuple[str, ...]
    uncounted_fields: tuple[str, ...]
    refusal_codes: tuple[str, ...]


INPUT_BOUND_METHODS: Mapping[str, InputBoundMethod] = MappingProxyType(
    {
        PROVIDER_COUNT: InputBoundMethod(
            name=PROVIDER_COUNT,
            version=1,
            counted_fields=("messages", "system", "toolConfig", "additionalModelRequestFields"),
            uncounted_fields=("inferenceConfig",),
            refusal_codes=("ValidationException",),
        )
    }
)
"""The registered methods by name. Closed: a method is added with a basis and a probe, and
an existing one changes only by a new version."""


@dataclass(frozen=True, slots=True)
class RegisteredInputBound:
    """The method a registration or a piece of evidence names: a registered name at the
    version the registry holds.

    >>> RegisteredInputBound("request_bytes", 1)
    Traceback (most recent call last):
    ...
    ValueError: an input-bound method is a registered one (provider_count), got 'request_bytes'
    >>> RegisteredInputBound("provider_count", 2)
    Traceback (most recent call last):
    ...
    ValueError: provider_count is registered at version 1, got 2
    """

    name: str
    version: int

    def __post_init__(self) -> None:
        if self.name not in INPUT_BOUND_METHODS:
            raise ValueError(
                "an input-bound method is a registered one "
                f"({', '.join(INPUT_BOUND_METHODS)}), got {self.name!r}"
            )
        held = INPUT_BOUND_METHODS[self.name].version
        if isinstance(self.version, bool) or self.version != held:
            raise ValueError(f"{self.name} is registered at version {held}, got {self.version!r}")

    @property
    def specification(self) -> InputBoundMethod:
        return INPUT_BOUND_METHODS[self.name]


def counted_projection(
    method: RegisteredInputBound, request: Mapping[str, object]
) -> dict[str, object]:
    """The part of ``request`` the method's count is asked about, its fields in the
    specification's order; ``ValueError`` when the request holds a field the specification
    neither counts nor tolerates, since a count would then be of another request.

    >>> method = RegisteredInputBound("provider_count", 1)
    >>> counted_projection(method, {"inferenceConfig": {"maxTokens": 256}, "messages": []})
    {'messages': []}
    >>> counted_projection(method, {"messages": [], "guardrailConfig": {}})
    Traceback (most recent call last):
    ...
    ValueError: provider_count version 1 bounds no request holding guardrailConfig
    """
    specification = method.specification
    known = {*specification.counted_fields, *specification.uncounted_fields}
    outside = [name for name in request if name not in known]
    if outside:
        raise ValueError(
            f"{method.name} version {method.version} bounds no request holding {', '.join(outside)}"
        )
    return {name: request[name] for name in specification.counted_fields if name in request}


# --- What the ledger takes -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EstablishedBound:
    """An upper bound of one request's input tokens, with what it rests on.

    ``request_digest`` is the digest of the whole inference request, so the counted
    projection and the inference configuration are both inside it. ``counting_identifier``
    is the model the count was asked of and ``evidence`` the counting operation that
    answered, by its id.
    """

    method: RegisteredInputBound
    counting_identifier: str
    request_digest: str
    input_tokens: int
    evidence: str

    def __post_init__(self) -> None:
        require_opaque_id(self.counting_identifier, "the counting identifier")
        require_digest(self.request_digest, "the bounded request's digest")
        require_integer(self.input_tokens, "an input bound in tokens")
        require_opaque_id(self.evidence, "the counting operation's id")

    def covers(
        self, method: RegisteredInputBound, counting_identifier: str, request_digest: str
    ) -> bool:
        """Whether this bound was established for exactly this request, under this method
        and asked of this identifier: the only case in which it is reused."""
        return (self.method, self.counting_identifier, self.request_digest) == (
            method,
            counting_identifier,
            request_digest,
        )


def output_maximum(configuration: CallConfiguration) -> int:
    """The most tokens a call under ``configuration`` may generate: its ``max_tokens``.

    ``ValueError`` when the configuration sets none, or sets something that is not a
    positive integer: such a call has no worst case and is not admitted. No supported
    configuration enables a reasoning budget; one that does is registered only once its
    reasoning tokens are shown to sit inside this limit.

    >>> from leaveimpact.core.call_settings import CallSetting
    >>> output_maximum(CallConfiguration("eu.model", (CallSetting("max_tokens", 1024),)))
    1024
    >>> output_maximum(CallConfiguration("eu.model", (CallSetting("temperature", 0),)))
    Traceback (most recent call last):
    ...
    ValueError: the configuration of eu.model sets no max_tokens, so its calls have no worst case
    """
    for setting in configuration.settings:
        if setting.name != MAX_OUTPUT_SETTING:
            continue
        value = setting.value
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(
                f"{MAX_OUTPUT_SETTING} of {configuration.model_id} is a positive integer, "
                f"got {value!r}"
            )
        return value
    raise ValueError(
        f"the configuration of {configuration.model_id} sets no {MAX_OUTPUT_SETTING}, so its "
        "calls have no worst case"
    )


def worst_case_tokens(bound: EstablishedBound, output_maximum: int) -> int:
    """The tokens a dispatch is counted for until its usage replaces them: the input bound
    and everything it may generate. An upper bound under every counting rule, since a rule
    sums reported classes and each is input or output."""
    return bound.input_tokens + require_integer(output_maximum, "an output maximum", minimum=1)


# --- Counting, and counting again ----------------------------------------------------------


class CountResult(StrEnum):
    """What became of one counting request; a member is the wire format."""

    COUNTED = "counted"
    FAILED = "failed"
    """The counting call failed for a reason that is the provider's or the network's:
    throttled, unavailable, denied, timed out."""
    REFUSED = "refused"
    """The service said the model or the request cannot be counted."""
    UNRESOLVED = "unresolved"
    """The request was started and no outcome was recorded."""


def result_of_error(method: RegisteredInputBound, code: str | None) -> CountResult:
    """How a failed counting request is read: refused when the service's error code is one
    the method's specification lists, failed otherwise. ``code`` is ``None`` when the client
    gave up with no answer, which is never a refusal.

    >>> method = RegisteredInputBound("provider_count", 1)
    >>> result_of_error(method, "ValidationException").value, result_of_error(method, None).value
    ('refused', 'failed')
    """
    if code is not None and code in method.specification.refusal_codes:
        return CountResult.REFUSED
    return CountResult.FAILED


class CountDecision(StrEnum):
    """What the harness does next about a request's input bound."""

    USE = "use"
    """A counting request for this request succeeded and is durable: its number is the bound."""
    COUNT = "count"
    """No count yet and the maximum is not reached: a counting request may be made."""
    EXHAUSTED = "exhausted"
    """The maximum was reached with no count: the attempt ends, by infrastructure."""
    DEFECT = "defect"
    """The request cannot be counted: the attempt ends, by defect."""


def count_decision(results: Sequence[CountResult], max_requests: int) -> CountDecision:
    """What follows from the counting requests logged so far for one request, in order.

    A refusal decides first, since a recorded defect keeps precedence over whatever came
    after it. A request with no recorded outcome counts toward the maximum like a failed
    one. ``max_requests`` is the re-dispatch policy's maximum, which a registration applies
    to counting by reference.

    >>> failed, unresolved = CountResult.FAILED, CountResult.UNRESOLVED
    >>> count_decision([], 3).value, count_decision([failed, unresolved], 3).value
    ('count', 'count')
    >>> count_decision([failed, unresolved, failed], 3).value
    'exhausted'
    """
    require_integer(max_requests, "the most counting requests", minimum=1)
    if CountResult.REFUSED in results:
        return CountDecision.DEFECT
    if CountResult.COUNTED in results:
        return CountDecision.USE
    return CountDecision.EXHAUSTED if len(results) >= max_requests else CountDecision.COUNT


__all__ = [
    "INPUT_BOUND_METHODS",
    "MAX_OUTPUT_SETTING",
    "PROVIDER_COUNT",
    "CountDecision",
    "CountResult",
    "EstablishedBound",
    "InputBoundMethod",
    "RegisteredInputBound",
    "count_decision",
    "counted_projection",
    "output_maximum",
    "result_of_error",
    "worst_case_tokens",
]
