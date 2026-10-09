"""A model call as a run records it: the dispatches it took, what arrived, and what an answer
carried.

Format 1 gave a call one outcome from six, and a run's history outgrew it at the acceptance
spike: a response with text beside tool calls had no truthful value, a process killed
between a logged intent and its outcome left a send nobody can prove or disprove, and a
provider's error said nothing about whether it was the model's behaviour or the
infrastructure's fault. The contract step's rulings separate what the one value conflated.

A *logical call* is one request the loop wanted answered. It holds its *dispatches* in
order, and each dispatch permits zero or one physical send: an intent never proves a send,
so a dispatch with no recorded outcome is unresolved, and a recovery that asks again takes
a new dispatch with a new number. Nothing retries beneath a dispatch (the SDK's attempts
are one, the client and the graph hold no retry policy), which is what makes the dispatch
the unit a cost and a cap can be counted in.

On a dispatch two things are kept apart. The *observation* is what arrived, as it arrived:
a complete response, a broken stream, a service error, a client error, a refusal before
anything was sent, or no recorded outcome. The *attribution* is how the measurement reads
it: behaviour, infrastructure, a defect of the harness, or unresolved, with the identifier
of the registered rule that decided. A service error stays a service error in the record
whichever rule reads it, so a rule can be changed before the freeze without rewriting what
was observed. The call's *state* (answered, failed, unresolved) is derived from its last
dispatch's observation and stored nowhere.

What an *answer* carried is its own record, present only when a complete response was
parsed: whether text was present (never the text), every tool call the model made with one
disposition each, and the fact batches it stated. A tool call became an operation (a read,
or a call the wrapper refused), was handled by the harness as a fact batch, could not be
parsed, was never dispatched for a stated reason, or is unresolved: it may have run with
its result lost. A fact batch is parsed, each entry a refused input or an admitted or
refused fact, or malformed. The two raw payloads kept here, a malformed batch and an
unparsed call's arguments, are the narrow exception to an export holding no assistant
prose: each sits beside the identity of the parser and schema that refused it, so the
classification can be verified from the export.

A dispatch's positions are the attempt's global event order, stable across recovery: the
position of its intent, and of its outcome when one was recorded. An operation holds the
position of its result. Neither clock orders events; a position does.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from leaveimpact.core.enums import require_member
from leaveimpact.core.input_bound import EstablishedBound
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.run_trace import (
    ClientErrorKind,
    Cost,
    ModelCallId,
    OperationId,
    require_digest,
    require_integer,
    require_opaque_id,
)
from leaveimpact.core.stated import Admission, Admitted, Refused, RefusedInput
from leaveimpact.core.usage import ReportedUsage

TOOL_USE_STOP = "tool_use"
"""The stop reason under which a tool call is dispatched; under any other, a tool call in
the response was cut or abandoned by the model and is never dispatched."""

UNRESOLVED_RULE = "no_recorded_outcome"
"""The rule an unresolved dispatch names. It is no row of any attribution table: with no
outcome recorded there is nothing to match, so the reading has one name and a dispatch
holds it."""


# --- The request ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RequestIdentity:
    """What was asked, in the terms a resumed run can reproduce.

    ``request_digest`` is the digest of the logical request as rebuilt from the log; the
    settings are in the body and so in the digest, and the body does not name the model,
    so the operation, the requested profile and the client region complete the identity.
    ``sent_body_digest`` is the digest of the bytes as sent, present only when a capture
    hook recorded them; ``None`` says no hook did. The region that served the call is not
    observable from the client and has no field.
    """

    request_digest: str
    operation: str
    requested_profile: str
    client_region: str
    sent_body_digest: str | None

    def __post_init__(self) -> None:
        require_digest(self.request_digest, "request_digest")
        require_opaque_id(self.operation, "the API operation")
        require_opaque_id(self.requested_profile, "the requested profile")
        require_opaque_id(self.client_region, "the client region")
        if self.sent_body_digest is not None:
            require_digest(self.sent_body_digest, "sent_body_digest")


# --- What arrived --------------------------------------------------------------------------


def _require_response_metadata(sdk_retries: int | None, provider_request_id: str | None) -> None:
    if sdk_retries is not None:
        require_integer(sdk_retries, "the SDK's retry count")
    if provider_request_id is not None:
        require_opaque_id(provider_request_id, "a provider request id")


@dataclass(frozen=True, slots=True)
class CompleteResponse:
    """A whole response arrived. ``sdk_retries`` is the retry count the response's metadata
    shows, ``None`` when it shows none; above zero it is a finding, since nothing retries
    beneath a dispatch. ``provider_request_id`` is the service's id for the request, from
    the response's headers, ``None`` when none was recorded."""

    stop_reason: str
    provider_latency_ms: int
    sdk_retries: int | None
    provider_request_id: str | None = None

    def __post_init__(self) -> None:
        require_opaque_id(self.stop_reason, "a stop reason")
        require_integer(self.provider_latency_ms, "provider latency in ms")
        _require_response_metadata(self.sdk_retries, self.provider_request_id)


@dataclass(frozen=True, slots=True)
class BrokenStream:
    """A stream opened and did not complete; ``reason`` is the error it ended on. A stream
    that opened carried response metadata, so the retry count and the request id are held
    as on a complete response."""

    reason: str
    sdk_retries: int | None = None
    provider_request_id: str | None = None

    def __post_init__(self) -> None:
        _require_response_metadata(self.sdk_retries, self.provider_request_id)


@dataclass(frozen=True, slots=True)
class ServiceError:
    """The service answered with an error: its HTTP status, its error code, the status of
    the model's own error when the service relays one, and a signature of the message. An
    error is a response and carries metadata: a retry count above zero shows several sends
    beneath one dispatch as plainly as it does on a success, and the request id names the
    send to the provider."""

    http_status: int
    code: str
    original_status: int | None
    message_signature: str
    sdk_retries: int | None = None
    provider_request_id: str | None = None

    def __post_init__(self) -> None:
        require_integer(self.http_status, "an HTTP status", minimum=100)
        require_opaque_id(self.code, "a service error code")
        if self.original_status is not None:
            require_integer(self.original_status, "an original status", minimum=100)
        _require_response_metadata(self.sdk_retries, self.provider_request_id)


@dataclass(frozen=True, slots=True)
class ClientError:
    """The client gave up with no answer: whether the request ran is unknown, and with no
    response there is no metadata, so how many times the SDK sent is unknown too."""

    kind: ClientErrorKind
    reason: str

    def __post_init__(self) -> None:
        require_member(self.kind, ClientErrorKind, "a client error's kind")


@dataclass(frozen=True, slots=True)
class RefusedBeforeSend:
    """The client's own validation refused the request and nothing was sent."""

    reason: str


@dataclass(frozen=True, slots=True)
class NoRecordedOutcome:
    """An intent was logged and no outcome was: zero sends or one, and nothing says which."""


type Observation = (
    CompleteResponse
    | BrokenStream
    | ServiceError
    | ClientError
    | RefusedBeforeSend
    | NoRecordedOutcome
)


_IDENTIFIER_RUN = re.compile(r"[0-9a-fA-F]{8,}|[0-9]+")


def message_signature(message: str) -> str:
    """The signature of a service error's message: the text with every run of digits and
    every hex run of eight or more replaced by ``#``, so a request id, an account id in a
    resource name or a count does not make two messages of one kind differ, and none of
    them reaches the record, which a public job log prints. The contract step left the
    signature undefined and the fixtures stand in with captured text; this is its first
    definition, and the captured texts hold no such run.

    >>> message_signature("Model produced invalid sequence as part of ToolUse")
    'Model produced invalid sequence as part of ToolUse'
    >>> message_signature("Too many tokens, 1200 over the limit (request 8f3a9c2e4b1d)")
    'Too many tokens, # over the limit (request #)'
    """
    return _IDENTIFIER_RUN.sub("#", message)


@dataclass(frozen=True, slots=True)
class Sent:
    """What one send produced: the observation, the response body for a complete one, and
    the digest of the bytes sent when a hook recorded them. The type sits beside the
    observations because a client is an adapter and the graph is above it: the client
    returns it, the graph records it, and neither imports the other."""

    observation: Observation
    response: JsonObject | None
    sent_body_digest: str | None


class AttributionKind(StrEnum):
    """How the measurement reads an observation; a member is the wire format."""

    BEHAVIOUR = "behaviour"
    INFRASTRUCTURE = "infrastructure"
    DEFECT = "defect"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class Attribution:
    """The reading of one observation and the registered rule that decided it. The rule is
    an identifier into the attribution table the record names by digest, or
    ``UNRESOLVED_RULE`` for the reading of no recorded outcome, which no table holds."""

    kind: AttributionKind
    rule: str

    def __post_init__(self) -> None:
        require_member(self.kind, AttributionKind, "an attribution's kind")
        require_opaque_id(self.rule, "an attribution rule")


# --- A dispatch ----------------------------------------------------------------------------


class Sends(StrEnum):
    """How many physical sends a dispatch stands for."""

    NONE = "none"
    ONE = "one"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class Dispatch:
    """One permitted send of a logical call: what was asked, what arrived, how it is read,
    what it used and cost.

    ``number`` is durable across restarts and ``segment`` the process segment the intent was
    logged in. ``input_reads`` are the operations whose returned records the request
    rendered, in order: the origin of a read says who asked for it, and this says what the
    model was shown. ``allocation`` is this dispatch's share of the run's reservation, in
    pico-dollars, and ``allocation_tokens`` the worst-case tokens it was counted for against
    the run's token cap, under the registered counting rule; an unresolved dispatch keeps
    both. They are two numbers because money does not determine a token count when the
    rates differ by class, and the cap an auditor checks known tokens plus retained
    allocations against is in tokens.

    Usage is the raw object a response carried and exists only where something arrived.
    ``cost`` prices it. ``zero_cost_rule`` names the evidenced rule under which a send that
    reported no usage cost nothing; an error is not free because it returned no usage, so
    without usage and without a rule a send's cost is unknown and ``cost`` is ``None``.

    ``bound`` is what the dispatch's input was bounded by before it was authorized: the
    method, the identifier the count was asked of, the request digest it covers, the number,
    and the counting operation it rests on, which the trace holds; ``output_maximum`` is the
    most the call could generate under its configuration. The two are what
    ``allocation_tokens`` was computed from, stored beside it so an auditor can check the
    arithmetic and that the bound's digest is this request's; neither tie is enforced here,
    since a mismatch is the finding the evaluator exists to report.
    """

    number: int
    segment: int
    intent_position: int
    outcome_position: int | None
    request: RequestIdentity
    input_reads: tuple[OperationId, ...]
    observation: Observation
    attribution: Attribution
    usage: ReportedUsage | None
    cost: Cost | None
    zero_cost_rule: str | None
    allocation: int
    allocation_tokens: int
    bound: EstablishedBound
    output_maximum: int

    def __post_init__(self) -> None:
        require_integer(self.number, "a dispatch number", minimum=1)
        require_integer(self.segment, "a segment number", minimum=1)
        require_integer(self.intent_position, "an intent position", minimum=1)
        require_integer(self.allocation, "an allocation in pico-dollars")
        require_integer(self.allocation_tokens, "an allocation in tokens")
        require_integer(self.output_maximum, "an output maximum", minimum=1)
        for operation in self.input_reads:
            require_opaque_id(operation, "an input read's operation id")
        if len(set(self.input_reads)) != len(self.input_reads):
            raise ValueError("a dispatch names each input read once")
        unrecorded = isinstance(self.observation, NoRecordedOutcome)
        if (self.outcome_position is None) != unrecorded:
            raise ValueError("an outcome position is held exactly when an outcome was recorded")
        if self.outcome_position is not None:
            require_integer(self.outcome_position, "an outcome position", minimum=1)
            if self.outcome_position <= self.intent_position:
                raise ValueError("a dispatch's outcome is logged after its intent")
        if (self.attribution.kind is AttributionKind.UNRESOLVED) != unrecorded:
            raise ValueError("a dispatch is unresolved exactly when no outcome was recorded")
        if unrecorded and self.attribution.rule != UNRESOLVED_RULE:
            raise ValueError(
                f"an unresolved dispatch names the rule {UNRESOLVED_RULE}, which no table "
                f"holds, got {self.attribution.rule!r}"
            )
        if self.sends is not Sends.ONE and (self.usage is not None or self.cost is not None):
            raise ValueError("usage and cost are recorded for a send whose outcome arrived")
        if self.zero_cost_rule is not None:
            require_opaque_id(self.zero_cost_rule, "a zero-cost rule")
            if self.usage is not None or self.cost != Cost(0, True):
                raise ValueError(
                    "a zero-cost rule prices a send that reported no usage at a complete zero"
                )
        elif self.cost is not None and self.usage is None:
            raise ValueError("a cost prices a reported usage or names its zero-cost rule")

    @property
    def sends(self) -> Sends:
        """Zero sends when the client refused the request, zero or one when no outcome was
        recorded, one otherwise."""
        if isinstance(self.observation, RefusedBeforeSend):
            return Sends.NONE
        if isinstance(self.observation, NoRecordedOutcome):
            return Sends.UNRESOLVED
        return Sends.ONE


# --- What an answer carried ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RefusedBy:
    """The parser and the schema that refused a payload, so the refusal can be checked."""

    parser: str
    schema_digest: str

    def __post_init__(self) -> None:
        require_opaque_id(self.parser, "a parser's identifier")
        require_digest(self.schema_digest, "a schema digest")


@dataclass(frozen=True, slots=True)
class AsOperation:
    """The call became the operation ``operation``: a read, or a call refused at validation."""

    operation: OperationId

    def __post_init__(self) -> None:
        require_opaque_id(self.operation, "an operation id")


@dataclass(frozen=True, slots=True)
class HandledAsBatch:
    """The harness took the call itself, as the fact batch at ``batch`` in the same answer."""

    batch: int

    def __post_init__(self) -> None:
        require_integer(self.batch, "a fact batch's index")


@dataclass(frozen=True, slots=True)
class Unparsed:
    """The call's arguments were not a JSON object; ``raw_arguments`` is the text as it
    arrived."""

    raw_arguments: str
    refused_by: RefusedBy


class UndispatchedReason(StrEnum):
    """Why a tool call the model made was never dispatched; a member is the wire format."""

    STOP_REASON_NOT_TOOL_USE = "stop_reason_not_tool_use"
    CAP = "cap"
    SOURCE_UNREACHABLE = "source_unreachable"
    """The source was already marked unreachable in this run."""
    ATTEMPT_ENDED_FIRST = "attempt_ended_first"
    """Claimed only on durable evidence the call was never reached, such as a terminal event
    anchored at an earlier call under sequential dispatch."""


@dataclass(frozen=True, slots=True)
class Undispatched:
    """The call was never dispatched, for a reason from the closed list."""

    reason: UndispatchedReason

    def __post_init__(self) -> None:
        require_member(self.reason, UndispatchedReason, "an undispatched call's reason")


@dataclass(frozen=True, slots=True)
class UnresolvedToolCall:
    """No result was logged and nothing shows the call was never reached: it may have run
    with its result lost. Every tool is a read, so nothing metered and nothing changed."""


type Disposition = AsOperation | HandledAsBatch | Unparsed | Undispatched | UnresolvedToolCall


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool call the model made, by the provider's id, with what became of it."""

    id: str
    name: str
    disposition: Disposition

    def __post_init__(self) -> None:
        require_opaque_id(self.id, "a tool call id")
        require_opaque_id(self.name, "a tool call's name")


type BatchEntry = RefusedInput | Admission
"""One entry of a parsed batch: an input no stated fact could be made of, or a stated fact
with whether it entered the view."""


@dataclass(frozen=True, slots=True)
class ParsedBatch:
    """A fact batch the parser read: its entries in the order the model stated them."""

    entries: tuple[BatchEntry, ...]

    def __post_init__(self) -> None:
        for entry in self.entries:
            if not isinstance(cast(object, entry), RefusedInput | Admitted | Refused):
                raise ValueError(
                    f"a batch entry is a refused input or an admission, got {type(entry).__name__}"
                )


@dataclass(frozen=True, slots=True)
class MalformedBatch:
    """A fact payload the parser could not read as a batch; ``raw`` is the designated
    payload as it arrived."""

    raw: str
    refused_by: RefusedBy


type FactBatch = ParsedBatch | MalformedBatch


@dataclass(frozen=True, slots=True)
class Answer:
    """What one complete response carried, parsed: text or not, the tool calls, the facts.

    A tool call handled by the harness names a batch this answer holds, and no batch is
    named twice; a batch no tool call names arrived in the response's own content.
    """

    text_present: bool
    tool_calls: tuple[ToolCall, ...]
    fact_batches: tuple[FactBatch, ...]

    def __post_init__(self) -> None:
        if not isinstance(cast(object, self.text_present), bool):
            raise ValueError(f"text_present is a boolean, got {self.text_present!r}")
        ids = [call.id for call in self.tool_calls]
        if len(set(ids)) != len(ids):
            raise ValueError("tool call ids are unique within an answer")
        handled = [
            call.disposition.batch
            for call in self.tool_calls
            if isinstance(call.disposition, HandledAsBatch)
        ]
        if len(set(handled)) != len(handled):
            raise ValueError("a fact batch is the handling of one tool call")
        for batch in handled:
            if batch >= len(self.fact_batches):
                raise ValueError(f"a tool call names fact batch {batch}, which the answer lacks")


# --- The logical call ----------------------------------------------------------------------


class CallState(StrEnum):
    """How a logical call stands, from its last dispatch's observation."""

    ANSWERED = "answered"
    FAILED = "failed"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class ModelCall:
    """One logical model call: its role, its dispatches in order, and what its answer carried.

    Dispatches are numbered from one without a gap and their intents are in position
    order, each asked after the outcome of the one before it was logged and in the same
    segment or a later one. Only the last may hold a complete response: an answered call is
    not asked again.
    ``answer`` is present only over a complete response; a complete response with no answer
    is one a later defect kept from being parsed, which the export's failure then names.
    Under a stop reason other than ``tool_use`` no tool call became an operation, and a
    call is undispatched for its stop reason only under such a stop.
    """

    id: ModelCallId
    role: str
    dispatches: tuple[Dispatch, ...]
    answer: Answer | None

    def __post_init__(self) -> None:
        require_opaque_id(self.id, "a model call id")
        require_opaque_id(self.role, "a role")
        if not self.dispatches:
            raise ValueError("a logical call holds at least one dispatch")
        numbers = [dispatch.number for dispatch in self.dispatches]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"dispatches are numbered from one without a gap, got {numbers}")
        positions = [dispatch.intent_position for dispatch in self.dispatches]
        if positions != sorted(set(positions)):
            raise ValueError("dispatch intents are in position order")
        for earlier, later in zip(self.dispatches, self.dispatches[1:], strict=False):
            if (
                earlier.outcome_position is not None
                and later.intent_position < earlier.outcome_position
            ):
                raise ValueError(
                    f"dispatch {later.number} is asked before the outcome of dispatch "
                    f"{earlier.number} was logged; a call is asked again only after"
                )
            if later.segment < earlier.segment:
                raise ValueError("a later dispatch runs in the same segment or a later one")
        for dispatch in self.dispatches[:-1]:
            if isinstance(dispatch.observation, CompleteResponse):
                raise ValueError("only a call's last dispatch holds a complete response")
        last = self.dispatches[-1].observation
        if self.answer is None:
            return
        if not isinstance(last, CompleteResponse):
            raise ValueError("an answer is what a complete response carried; none arrived")
        tool_use = last.stop_reason == TOOL_USE_STOP
        for call in self.answer.tool_calls:
            disposition = call.disposition
            if isinstance(disposition, AsOperation) and not tool_use:
                raise ValueError(
                    f"tool call {call.id} became an operation under the stop reason "
                    f"{last.stop_reason!r}; a call is dispatched only under {TOOL_USE_STOP!r}"
                )
            if (
                isinstance(disposition, Undispatched)
                and disposition.reason is UndispatchedReason.STOP_REASON_NOT_TOOL_USE
                and tool_use
            ):
                raise ValueError(
                    f"tool call {call.id} is undispatched for its stop reason, which is "
                    f"{TOOL_USE_STOP!r}"
                )

    @property
    def state(self) -> CallState:
        """Answered when the last dispatch holds a complete response, unresolved when it
        holds no recorded outcome, failed otherwise. How the failure is read (behaviour,
        infrastructure, defect) is the dispatch's attribution, not the state."""
        last = self.dispatches[-1].observation
        if isinstance(last, CompleteResponse):
            return CallState.ANSWERED
        if isinstance(last, NoRecordedOutcome):
            return CallState.UNRESOLVED
        return CallState.FAILED

    @property
    def stop_reason(self) -> str | None:
        """The stop reason of the call's complete response, or ``None`` when none arrived."""
        last = self.dispatches[-1].observation
        return last.stop_reason if isinstance(last, CompleteResponse) else None


__all__ = [
    "TOOL_USE_STOP",
    "UNRESOLVED_RULE",
    "Answer",
    "AsOperation",
    "Attribution",
    "AttributionKind",
    "BatchEntry",
    "BrokenStream",
    "CallState",
    "ClientError",
    "ClientErrorKind",
    "CompleteResponse",
    "Dispatch",
    "Disposition",
    "FactBatch",
    "HandledAsBatch",
    "MalformedBatch",
    "ModelCall",
    "NoRecordedOutcome",
    "Observation",
    "ParsedBatch",
    "RefusedBeforeSend",
    "RefusedBy",
    "RequestIdentity",
    "Sends",
    "Sent",
    "ServiceError",
    "ToolCall",
    "Undispatched",
    "UndispatchedReason",
    "Unparsed",
    "UnresolvedToolCall",
    "message_signature",
]
