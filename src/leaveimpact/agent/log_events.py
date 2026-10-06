"""The events of an attempt's log: what each kind holds, what identifies it, and its bytes.

An attempt is a row with a generation and a log of events, and the log fixes what happened
(the event log step's rulings on one writer and on the event). Every durable step a worker
or an outside producer takes is one event here: the admission that froze the run's inputs,
a segment's start and end, a tool read's result or a decision not to run it, a counting
request's start and outcome, a dispatch's intent and outcome, the entry into finalization,
the approval's request, the approval, the worker's resume, the three terminal events and
the abandon command. Sixteen kinds, closed; an unknown kind fails loudly in the codec.

*Envelopes.* A worker's event carries the generation it ran under, the segment and the
offset on that segment's monotonic clock; an outside producer's event carries the producer's
identity and no segment and no offset (the ruling on the event, parts 3 and 4). The position
and the database timestamp are first-append provenance, set by the store and kept unchanged
on replay. ``LoggedEvent`` is an event with its provenance.

*Keys.* An event is identified by its kind and a structured key derived from what the
writer is doing, never by a counter the writer picks: a segment's start by its number, an
operation by its origin (the prefetch's ordinal; the call and the tool call it answers; the
harness policy and its ordinal), a count by its reuse key and ordinal, a dispatch by its
call and number, the attempt-wide events by the attempt alone. The identifiers an export
carries are these keys rendered (``operation_id``, ``call_id``, ``count_id``), so two
writers of one key write one event and nobody mints a name.

*Bytes.* Idempotence compares the versioned canonical content of an event, which
``event_bytes`` gives: the log format version, the kind and the content, in canonical JSON.
What changes an event's meaning is content, so the approver's identity, an abandonment's
authority and a segment start's harness revision are inside it; the envelope's position
and timestamp are not.

*Formats.* The log format version covers these codecs and their canonicalization; it is set
on the attempt row at admission and inside the admission event, and a reader or a worker
that does not know it refuses. It is one of three versions with their own compatibility
rules, beside the schema's and the export's.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import assert_never

from leaveimpact.core.attribution import RedispatchPolicy
from leaveimpact.core.call_settings import (
    CallConfiguration,
    decode_call_configuration,
    encode_call_configuration,
)
from leaveimpact.core.claims import Claim
from leaveimpact.core.claims_json import decode_claim, encode_claim
from leaveimpact.core.counting_operations import CountOutcome
from leaveimpact.core.enums import Source, require_member
from leaveimpact.core.input_bound import CountResult, EstablishedBound, RegisteredInputBound
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    canonical_bytes,
    expect_fields,
    field_of,
    integer_field,
    object_field,
    optional_string_field,
    string_field,
    string_item,
)
from leaveimpact.core.model_calls import (
    Attribution,
    AttributionKind,
    NoRecordedOutcome,
    Observation,
    RefusedBy,
    UndispatchedReason,
)
from leaveimpact.core.pricing import decode_rate, encode_rate
from leaveimpact.core.registration import RetryRule
from leaveimpact.core.run_ending import (
    AbandonmentReason,
    Approver,
    ClaimAuthor,
    ComposingPolicy,
    Composition,
    FailureSite,
    KeptReason,
    ReservationState,
)
from leaveimpact.core.run_export_json import (
    decode_outcome,
    decode_run_context,
    encode_outcome,
    encode_run_context,
)
from leaveimpact.core.run_parts_json import (
    decode_bound,
    decode_composition,
    decode_count_outcome,
    decode_failure_site,
    decode_method,
    decode_observation,
    encode_bound,
    encode_composition,
    encode_count_outcome,
    encode_failure_site,
    encode_method,
    encode_observation,
)
from leaveimpact.core.run_record import (
    Caps,
    FailureCategory,
    OutageAssignment,
    PrefetchRule,
    PricingBasis,
    PricingSelection,
    Retrieval,
    RetrievalKind,
    System,
    SystemKind,
)
from leaveimpact.core.run_timing import HarnessRevision, TreeState, require_commit
from leaveimpact.core.run_trace import (
    CountingOperationId,
    ModelCallId,
    OperationId,
    Outcome,
    frozen_json,
    require_digest,
    require_integer,
    require_opaque_id,
    thawed_json,
)
from leaveimpact.core.timeshape import decode_date, decode_instant, encode_date, encode_instant
from leaveimpact.core.worldtime import RunContext

LOG_FORMAT_VERSION = 1
"""The log format this code writes and reads: the codecs here and their canonicalization."""


# --- Envelopes -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkerStamp:
    """A worker's event: the generation it owned the attempt under, the segment it ran in,
    the offset on that segment's monotonic clock in whole milliseconds."""

    generation: int
    segment: int
    offset_ms: int

    def __post_init__(self) -> None:
        require_integer(self.generation, "a generation", minimum=1)
        require_integer(self.segment, "a segment number", minimum=1)
        require_integer(self.offset_ms, "an offset in ms")


@dataclass(frozen=True, slots=True)
class Producer:
    """An outside producer's event: the admitter, an approver, an abandoning operator or
    recovery, by an opaque identity. No segment and no offset."""

    identity: str

    def __post_init__(self) -> None:
        require_opaque_id(self.identity, "a producer's identity")


type Envelope = WorkerStamp | Producer


# --- Keys ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PrefetchKey:
    """The frozen prefetch's ``ordinal``-th call."""

    ordinal: int

    def __post_init__(self) -> None:
        require_integer(self.ordinal, "a prefetch ordinal", minimum=1)


@dataclass(frozen=True, slots=True)
class ModelReadKey:
    """The read answering tool call ``tool_call`` of the model call ``call`` (its ordinal)."""

    call: int
    tool_call: str

    def __post_init__(self) -> None:
        require_integer(self.call, "a model call ordinal", minimum=1)
        require_opaque_id(self.tool_call, "a tool call id")


@dataclass(frozen=True, slots=True)
class HarnessReadKey:
    """The ``ordinal``-th read the harness issued under the registered policy ``policy``."""

    policy: str
    ordinal: int

    def __post_init__(self) -> None:
        require_opaque_id(self.policy, "the policy that issued a harness read")
        require_integer(self.ordinal, "a harness read ordinal", minimum=1)


type OperationKey = PrefetchKey | ModelReadKey | HarnessReadKey


@dataclass(frozen=True, slots=True)
class CountKey:
    """A counting request: the reuse key a durable count is reused under (the method, the
    identifier the count is asked of, the request's digest) and the ordinal within it."""

    method: RegisteredInputBound
    counting_identifier: str
    request_digest: str
    ordinal: int

    def __post_init__(self) -> None:
        require_opaque_id(self.counting_identifier, "the counting identifier")
        require_digest(self.request_digest, "the counted request's digest")
        require_integer(self.ordinal, "a counting request's ordinal", minimum=1)

    @property
    def reuse(self) -> tuple[RegisteredInputBound, str, str]:
        """What a durable count is reused under: everything but the ordinal."""
        return (self.method, self.counting_identifier, self.request_digest)


def operation_id(key: OperationKey) -> OperationId:
    """The identifier an export carries for the operation with ``key``.

    >>> operation_id(PrefetchKey(2)), operation_id(ModelReadKey(1, "tu_1"))
    ('prefetch/2', 'call-1/tu_1')
    """
    match key:
        case PrefetchKey():
            return OperationId(f"prefetch/{key.ordinal}")
        case ModelReadKey():
            return OperationId(f"{call_id(key.call)}/{key.tool_call}")
        case HarnessReadKey():
            return OperationId(f"{key.policy}/{key.ordinal}")
        case _:
            assert_never(key)


def call_id(ordinal: int) -> ModelCallId:
    """The identifier an export carries for the attempt's ``ordinal``-th logical call."""
    return ModelCallId(f"call-{require_integer(ordinal, 'a model call ordinal', minimum=1)}")


def count_id(key: CountKey) -> CountingOperationId:
    """The identifier an export carries for the counting request with ``key``.

    >>> method = RegisteredInputBound("provider_count", 1)
    >>> count_id(CountKey(method, "model-a-base", "a" * 64, 2))
    'count/provider_count-1/model-a-base/aaaaaaaaaaaaaaaa/2'
    """
    return CountingOperationId(
        f"count/{key.method.name}-{key.method.version}/{key.counting_identifier}/"
        f"{key.request_digest[:16]}/{key.ordinal}"
    )


# --- The admission's content -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FrozenInputs:
    """Everything the export's record and an empty trace need, frozen at admission so an
    export is rebuilt from the log and nothing mutable (the ruling on admission, part 2).

    The attribution table is held by its digest and the re-dispatch policy by its values,
    both ``None`` exactly for a system that calls no model, as is the reservation; the
    transition function takes the registered values from its caller and refuses ones that
    differ from these. ``counting_identifiers`` is each role's counting model id, which the
    export does not carry and the transition needs. ``parser`` is the fact parser's identity
    and schema digest, verified at claim and used by the reader.
    """

    run_id: str
    attempt: int
    context: RunContext
    preregistration_commit: str
    system: System
    retrieval: Retrieval
    caps: Caps
    model_configurations: tuple[tuple[str, CallConfiguration], ...]
    pricing_selections: tuple[tuple[str, PricingSelection], ...]
    counting_identifiers: tuple[tuple[str, str], ...]
    pricing: PricingBasis
    prompt_digests: tuple[tuple[str, str, str], ...]
    tool_surface_digests: tuple[tuple[str, str], ...]
    attribution_table: str | None
    redispatch: RedispatchPolicy | None
    retry: RetryRule
    prefetch_rule: PrefetchRule
    composing_policy: ComposingPolicy
    claim_author: ClaimAuthor
    parser: RefusedBy
    outage: OutageAssignment
    corpus_level: str
    reservation_pico_usd: int | None
    log_format_version: int

    def __post_init__(self) -> None:
        require_opaque_id(self.run_id, "a run id")
        require_integer(self.attempt, "an attempt number", minimum=1)
        require_commit(self.preregistration_commit, "the preregistration commit")
        require_opaque_id(self.corpus_level, "the assigned corpus level")
        require_member(self.claim_author, ClaimAuthor, "the claim author")
        roles = sorted(role for role, _ in self.model_configurations)
        if roles != sorted(set(roles)):
            raise ValueError(f"a role calls one model configuration, got {roles}")
        for name, held in (
            ("pricing_selections", self.pricing_selections),
            ("counting_identifiers", self.counting_identifiers),
            ("tool_surface_digests", self.tool_surface_digests),
        ):
            if sorted(role for role, _ in held) != roles:
                raise ValueError(f"{name} names exactly the configured roles {roles}")
        if sorted({role for role, _, _ in self.prompt_digests}) != roles:
            raise ValueError(f"prompt_digests names exactly the configured roles {roles}")
        calls_a_model = bool(roles)
        for name, held in (
            ("an attribution table", self.attribution_table),
            ("a re-dispatch policy", self.redispatch),
            ("a reservation", self.reservation_pico_usd),
        ):
            if (held is not None) != calls_a_model:
                raise ValueError(f"{name} is frozen exactly when a role calls a model")
        if self.attribution_table is not None:
            require_digest(self.attribution_table, "the attribution table digest")
        if self.reservation_pico_usd is not None:
            require_integer(self.reservation_pico_usd, "a reservation in pico-dollars")
        if (self.system.kind is SystemKind.RULES_ONLY) != (not calls_a_model):
            raise ValueError("rules-only calls no model; every other system configures a role")
        if self.log_format_version != LOG_FORMAT_VERSION:
            raise ValueError(
                f"this code writes log format {LOG_FORMAT_VERSION}, got {self.log_format_version}"
            )
        for pairs in (
            "model_configurations",
            "pricing_selections",
            "counting_identifiers",
            "tool_surface_digests",
        ):
            object.__setattr__(self, pairs, tuple(sorted(getattr(self, pairs), key=_first)))
        object.__setattr__(self, "prompt_digests", tuple(sorted(self.prompt_digests)))

    def configuration_of(self, role: str) -> CallConfiguration | None:
        return dict(self.model_configurations).get(role)

    def selection_of(self, role: str) -> PricingSelection | None:
        return dict(self.pricing_selections).get(role)

    def counting_identifier_of(self, role: str) -> str | None:
        return dict(self.counting_identifiers).get(role)


def _first(pair: tuple[str, object]) -> str:
    return pair[0]


# --- The settlement a closing event carries --------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoggedSettlement:
    """What the closer computed under the lock and the ledger wrote in the same transaction:
    the amount charged, the reservation's state with its reason, and the ledger revision the
    settlement was written at. Absent on a system with no reservation."""

    charged_pico_usd: int
    state: ReservationState
    kept_reason: KeptReason | None
    ledger_revision: int

    def __post_init__(self) -> None:
        require_integer(self.charged_pico_usd, "the amount charged in pico-dollars")
        require_member(self.state, ReservationState, "a reservation's state")
        if (self.kept_reason is not None) != (self.state is ReservationState.KEPT):
            raise ValueError("a reason is given exactly for a kept reservation")
        require_integer(self.ledger_revision, "a ledger revision")


# --- The events ------------------------------------------------------------------------------


class EventKind(StrEnum):
    """The sixteen kinds, closed; a member is the wire format."""

    ADMITTED = "admitted"
    SEGMENT_STARTED = "segment_started"
    SEGMENT_ENDED = "segment_ended"
    OPERATION = "operation"
    COUNT_STARTED = "count_started"
    COUNT_OUTCOME = "count_outcome"
    DISPATCH_INTENT = "dispatch_intent"
    DISPATCH_OUTCOME = "dispatch_outcome"
    FINALIZATION_ENTERED = "finalization_entered"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVED = "approved"
    RESUMED = "resumed"
    COMPLETED = "completed"
    CAP_EXHAUSTED = "cap_exhausted"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class Admitted:
    """The first event, appended by the admitter: the frozen inputs."""

    inputs: FrozenInputs


@dataclass(frozen=True, slots=True)
class SegmentStarted:
    """A claim: the harness revision the segment runs, the claiming process's nonce, and the
    launch identity of the execution that started it. The segment number is the stamp's."""

    harness: HarnessRevision
    nonce: str
    launch: str

    def __post_init__(self) -> None:
        require_opaque_id(self.nonce, "a process nonce")
        require_opaque_id(self.launch, "a launch identity")


@dataclass(frozen=True, slots=True)
class SegmentEnded:
    """A worker stopped cleanly without a terminal event; the segment is the stamp's."""


@dataclass(frozen=True, slots=True)
class OperationResult:
    """A tool call was made: the tool, the source it resolved to, the arguments as accepted
    and what came back, a wrapper's refusal included."""

    tool: str
    source: Source | None
    arguments: Mapping[str, object]
    outcome: Outcome

    def __post_init__(self) -> None:
        require_opaque_id(self.tool, "a tool name")
        object.__setattr__(self, "arguments", frozen_json(dict(self.arguments), "arguments"))


@dataclass(frozen=True, slots=True)
class OperationSkip:
    """A final decision not to run a tool call the model made: the cap, or a source already
    marked unreachable. Honoured on replay; it is no intent."""

    reason: UndispatchedReason

    def __post_init__(self) -> None:
        if self.reason not in (UndispatchedReason.CAP, UndispatchedReason.SOURCE_UNREACHABLE):
            raise ValueError(f"a skip is for the cap or an unreachable source, got {self.reason}")


@dataclass(frozen=True, slots=True)
class OperationEvent:
    """One tool call's resolution, a result or a skip, keyed by what asked for it."""

    key: OperationKey
    resolution: OperationResult | OperationSkip

    def __post_init__(self) -> None:
        if isinstance(self.resolution, OperationSkip) and not isinstance(self.key, ModelReadKey):
            raise ValueError("only a read the model asked for is skipped")


@dataclass(frozen=True, slots=True)
class CountStarted:
    """A counting request, committed before the remote call, for ``role``'s request."""

    key: CountKey
    role: str

    def __post_init__(self) -> None:
        require_opaque_id(self.role, "a role")


@dataclass(frozen=True, slots=True)
class CountOutcomeLogged:
    """What the counting request with ``key`` returned, and how the worker read it."""

    key: CountKey
    outcome: CountOutcome
    reading: CountResult

    def __post_init__(self) -> None:
        require_member(self.reading, CountResult, "a counting operation's reading")
        if isinstance(self.outcome, NoRecordedOutcome):
            raise ValueError("a count outcome event records an outcome")
        if self.reading is CountResult.UNRESOLVED:
            raise ValueError("a recorded outcome is never read as unresolved")


@dataclass(frozen=True, slots=True)
class DispatchIntent:
    """A dispatch authorized under the lock before anything external: the call (by ordinal)
    and the number, the role, the request's identity, the reads it rendered, the bound and
    the output maximum, and the worst case in tokens and in money."""

    call: int
    number: int
    role: str
    request_digest: str
    operation: str
    requested_profile: str
    client_region: str
    input_reads: tuple[OperationId, ...]
    bound: EstablishedBound
    output_maximum: int
    allocation_tokens: int
    allocation_pico_usd: int

    def __post_init__(self) -> None:
        require_integer(self.call, "a model call ordinal", minimum=1)
        require_integer(self.number, "a dispatch number", minimum=1)
        require_opaque_id(self.role, "a role")
        require_digest(self.request_digest, "request_digest")
        require_opaque_id(self.operation, "the API operation")
        require_opaque_id(self.requested_profile, "the requested profile")
        require_opaque_id(self.client_region, "the client region")
        if len(set(self.input_reads)) != len(self.input_reads):
            raise ValueError("a dispatch names each input read once")
        require_integer(self.output_maximum, "an output maximum", minimum=1)
        require_integer(self.allocation_tokens, "an allocation in tokens")
        require_integer(self.allocation_pico_usd, "an allocation in pico-dollars")


@dataclass(frozen=True, slots=True)
class DispatchOutcome:
    """What arrived for a dispatch, as it arrived: the observation, the response body for a
    complete response (what the parser derives the answer from), the worker's attribution,
    an evidenced zero-cost rule, and the digest of the bytes sent when a hook recorded them."""

    call: int
    number: int
    observation: Observation
    response: Mapping[str, object] | None
    attribution: Attribution
    zero_cost_rule: str | None
    sent_body_digest: str | None

    def __post_init__(self) -> None:
        require_integer(self.call, "a model call ordinal", minimum=1)
        require_integer(self.number, "a dispatch number", minimum=1)
        if isinstance(self.observation, NoRecordedOutcome):
            raise ValueError("a dispatch outcome event records an outcome")
        if self.attribution.kind is AttributionKind.UNRESOLVED:
            raise ValueError("a recorded outcome is never read as unresolved")
        if self.response is not None:
            object.__setattr__(self, "response", frozen_json(dict(self.response), "a response"))
        if self.zero_cost_rule is not None:
            require_opaque_id(self.zero_cost_rule, "a zero-cost rule")
        if self.sent_body_digest is not None:
            require_digest(self.sent_body_digest, "sent_body_digest")


@dataclass(frozen=True, slots=True)
class FinalizationEntered:
    """The run stopped investigating and began to finalize."""


@dataclass(frozen=True, slots=True)
class ApprovalRequested:
    """The review payload, frozen: the claims and how they were composed. Its digest is
    what an approval answers."""

    claims: tuple[Claim, ...]
    composition: Composition


@dataclass(frozen=True, slots=True)
class Approved:
    """An approval delivered by an outside producer: who, and the digest of the payload."""

    approver: Approver
    payload_digest: str

    def __post_init__(self) -> None:
        require_member(self.approver, Approver, "an approver")
        require_digest(self.payload_digest, "the review payload's digest")


@dataclass(frozen=True, slots=True)
class Resumed:
    """The worker's own transition after the approval was delivered."""


@dataclass(frozen=True, slots=True)
class Completed:
    """The system produced its final claims; the settlement the closer wrote."""

    settlement: LoggedSettlement | None


@dataclass(frozen=True, slots=True)
class CapExhausted:
    """The system reported what it had at the cap; the settlement the closer wrote."""

    settlement: LoggedSettlement | None


@dataclass(frozen=True, slots=True)
class Failed:
    """A defect or an infrastructure fault ended the attempt: the category, the site, the
    reason, and the settlement the closer wrote."""

    category: FailureCategory
    site: FailureSite
    reason: str
    settlement: LoggedSettlement | None

    def __post_init__(self) -> None:
        require_member(self.category, FailureCategory, "a failure's category")


@dataclass(frozen=True, slots=True)
class Abandoned:
    """The abandon command: the generation it expects to fence, the reason, the settlement.
    The authority is the producer's identity."""

    expected_generation: int
    reason: AbandonmentReason
    settlement: LoggedSettlement | None

    def __post_init__(self) -> None:
        require_integer(self.expected_generation, "an ownership generation")
        require_member(self.reason, AbandonmentReason, "an abandonment's reason")


type Event = (
    Admitted
    | SegmentStarted
    | SegmentEnded
    | OperationEvent
    | CountStarted
    | CountOutcomeLogged
    | DispatchIntent
    | DispatchOutcome
    | FinalizationEntered
    | ApprovalRequested
    | Approved
    | Resumed
    | Completed
    | CapExhausted
    | Failed
    | Abandoned
)

type TerminalEvent = Completed | CapExhausted | Failed
type ClosingEvent = TerminalEvent | Abandoned


def kind_of(event: Event) -> EventKind:
    """The kind of ``event``."""
    match event:
        case Admitted():
            return EventKind.ADMITTED
        case SegmentStarted():
            return EventKind.SEGMENT_STARTED
        case SegmentEnded():
            return EventKind.SEGMENT_ENDED
        case OperationEvent():
            return EventKind.OPERATION
        case CountStarted():
            return EventKind.COUNT_STARTED
        case CountOutcomeLogged():
            return EventKind.COUNT_OUTCOME
        case DispatchIntent():
            return EventKind.DISPATCH_INTENT
        case DispatchOutcome():
            return EventKind.DISPATCH_OUTCOME
        case FinalizationEntered():
            return EventKind.FINALIZATION_ENTERED
        case ApprovalRequested():
            return EventKind.APPROVAL_REQUESTED
        case Approved():
            return EventKind.APPROVED
        case Resumed():
            return EventKind.RESUMED
        case Completed():
            return EventKind.COMPLETED
        case CapExhausted():
            return EventKind.CAP_EXHAUSTED
        case Failed():
            return EventKind.FAILED
        case Abandoned():
            return EventKind.ABANDONED
        case _:
            assert_never(event)


def is_worker_event(event: Event) -> bool:
    """Whether ``event`` is one a worker appends under a stamp; the three others (the
    admission, an approval, an abandonment) are an outside producer's."""
    return not isinstance(event, Admitted | Approved | Abandoned)


# --- The logged event ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoggedEvent:
    """An event with its first-append provenance: the position, the database's timestamp of
    the accept, and the envelope its producer wrote it under."""

    position: int
    timestamp: datetime
    envelope: Envelope
    event: Event

    def __post_init__(self) -> None:
        require_integer(self.position, "a position", minimum=1)
        if self.timestamp.utcoffset() is None:
            raise ValueError(
                f"an event's timestamp is a timezone-aware instant, got {self.timestamp!r}"
            )
        worker = isinstance(self.envelope, WorkerStamp)
        if worker != is_worker_event(self.event):
            producer = "a worker" if worker else "an outside producer"
            raise ValueError(f"{kind_of(self.event).value} is not an event {producer} appends")

    @property
    def stamp(self) -> WorkerStamp | None:
        return self.envelope if isinstance(self.envelope, WorkerStamp) else None


type EventKey = tuple[EventKind, tuple[object, ...]]
"""What identifies an event for uniqueness and the idempotent re-append: its kind and the
structured key derived from what its writer was doing."""


def event_key(logged: LoggedEvent) -> EventKey:
    """The key of ``logged``: segment events take their segment from the stamp, the
    attempt-wide events have the empty key, the rest carry theirs."""
    event = logged.event
    kind = kind_of(event)
    match event:
        case SegmentStarted() | SegmentEnded():
            stamp = logged.stamp
            assert stamp is not None
            return (kind, (stamp.segment,))
        case OperationEvent():
            return (kind, (event.key,))
        case CountStarted() | CountOutcomeLogged():
            return (kind, (event.key,))
        case DispatchIntent() | DispatchOutcome():
            return (kind, (event.call, event.number))
        case _:
            return (kind, ())


def event_bytes(event: Event) -> bytes:
    """The versioned canonical content idempotence compares: the log format version, the
    kind and the content, in canonical JSON."""
    return canonical_bytes(
        {
            "log_format": LOG_FORMAT_VERSION,
            "kind": kind_of(event).value,
            "content": encode_event(event),
        }
    )


def event_digest(event: Event) -> str:
    """SHA-256 of ``event_bytes``."""
    return hashlib.sha256(event_bytes(event)).hexdigest()


# --- The codec -------------------------------------------------------------------------------


def encode_logged_event(logged: LoggedEvent) -> JsonObject:
    """The JSON object of a logged event: provenance, envelope, kind, content."""
    envelope = logged.envelope
    return {
        "position": logged.position,
        "timestamp": encode_instant(logged.timestamp),
        "envelope": (
            {
                "kind": "worker",
                "generation": envelope.generation,
                "segment": envelope.segment,
                "offset_ms": envelope.offset_ms,
            }
            if isinstance(envelope, WorkerStamp)
            else {"kind": "producer", "identity": envelope.identity}
        ),
        "event_kind": kind_of(logged.event).value,
        "content": encode_event(logged.event),
    }


def decode_logged_event(value: object) -> LoggedEvent:
    """The logged event ``value`` encodes, through every constructor invariant."""
    data = as_object(value, "a logged event")
    expect_fields(
        data, ("position", "timestamp", "envelope", "event_kind", "content"), "a logged event"
    )
    envelope = object_field(data, "envelope")
    kind = string_field(envelope, "kind")
    if kind == "worker":
        expect_fields(
            envelope, ("kind", "generation", "segment", "offset_ms"), "a worker's envelope"
        )
        held: Envelope = WorkerStamp(
            integer_field(envelope, "generation"),
            integer_field(envelope, "segment"),
            integer_field(envelope, "offset_ms"),
        )
    elif kind == "producer":
        expect_fields(envelope, ("kind", "identity"), "a producer's envelope")
        held = Producer(string_field(envelope, "identity"))
    else:
        raise ValueError(f"an envelope is worker or producer, got {kind!r}")
    return LoggedEvent(
        integer_field(data, "position"),
        decode_instant(field_of(data, "timestamp"), "timestamp"),
        held,
        decode_event(string_field(data, "event_kind"), object_field(data, "content")),
    )


def encode_event(event: Event) -> JsonObject:
    """The content of ``event`` as a JSON object; the kind is carried beside it."""
    match event:
        case Admitted():
            return {"inputs": _encode_inputs(event.inputs)}
        case SegmentStarted():
            return {
                "harness": {"commit": event.harness.commit, "tree": event.harness.tree.value},
                "nonce": event.nonce,
                "launch": event.launch,
            }
        case SegmentEnded() | FinalizationEntered() | Resumed():
            return {}
        case OperationEvent():
            return {
                "key": _encode_operation_key(event.key),
                "resolution": _encode_resolution(event.resolution),
            }
        case CountStarted():
            return {"key": _encode_count_key(event.key), "role": event.role}
        case CountOutcomeLogged():
            return {
                "key": _encode_count_key(event.key),
                "outcome": encode_count_outcome(event.outcome),
                "reading": event.reading.value,
            }
        case DispatchIntent():
            return {
                "call": event.call,
                "number": event.number,
                "role": event.role,
                "request_digest": event.request_digest,
                "operation": event.operation,
                "requested_profile": event.requested_profile,
                "client_region": event.client_region,
                "input_reads": list(event.input_reads),
                "bound": encode_bound(event.bound),
                "output_maximum": event.output_maximum,
                "allocation_tokens": event.allocation_tokens,
                "allocation_pico_usd": event.allocation_pico_usd,
            }
        case DispatchOutcome():
            return {
                "call": event.call,
                "number": event.number,
                "observation": encode_observation(event.observation),
                "response": None if event.response is None else thawed_json(event.response),
                "attribution": {
                    "kind": event.attribution.kind.value,
                    "rule": event.attribution.rule,
                },
                "zero_cost_rule": event.zero_cost_rule,
                "sent_body_digest": event.sent_body_digest,
            }
        case ApprovalRequested():
            return {
                "claims": [encode_claim(claim) for claim in event.claims],
                "composition": encode_composition(event.composition),
            }
        case Approved():
            return {"approver": event.approver.value, "payload_digest": event.payload_digest}
        case Completed() | CapExhausted():
            return {"settlement": _encode_settlement(event.settlement)}
        case Failed():
            return {
                "category": event.category.value,
                "site": encode_failure_site(event.site),
                "reason": event.reason,
                "settlement": _encode_settlement(event.settlement),
            }
        case Abandoned():
            return {
                "expected_generation": event.expected_generation,
                "reason": event.reason.value,
                "settlement": _encode_settlement(event.settlement),
            }
        case _:
            assert_never(event)


def decode_event(kind: str, data: Mapping[str, object]) -> Event:
    """The event of ``kind`` that ``data`` encodes; an unknown kind refuses by name."""
    try:
        member = EventKind(kind)
    except ValueError:
        raise ValueError(f"not an event kind this log format holds: {kind!r}") from None
    match member:
        case EventKind.ADMITTED:
            expect_fields(data, ("inputs",), "an admission")
            return Admitted(_decode_inputs(object_field(data, "inputs")))
        case EventKind.SEGMENT_STARTED:
            expect_fields(data, ("harness", "nonce", "launch"), "a segment start")
            harness = object_field(data, "harness")
            expect_fields(harness, ("commit", "tree"), "the harness")
            return SegmentStarted(
                HarnessRevision(
                    string_field(harness, "commit"), TreeState(string_field(harness, "tree"))
                ),
                string_field(data, "nonce"),
                string_field(data, "launch"),
            )
        case EventKind.SEGMENT_ENDED:
            expect_fields(data, (), "a segment end")
            return SegmentEnded()
        case EventKind.OPERATION:
            expect_fields(data, ("key", "resolution"), "an operation")
            return OperationEvent(
                _decode_operation_key(object_field(data, "key")),
                _decode_resolution(object_field(data, "resolution")),
            )
        case EventKind.COUNT_STARTED:
            expect_fields(data, ("key", "role"), "a count start")
            return CountStarted(
                _decode_count_key(object_field(data, "key")), string_field(data, "role")
            )
        case EventKind.COUNT_OUTCOME:
            expect_fields(data, ("key", "outcome", "reading"), "a count outcome")
            return CountOutcomeLogged(
                _decode_count_key(object_field(data, "key")),
                decode_count_outcome(object_field(data, "outcome")),
                CountResult(string_field(data, "reading")),
            )
        case EventKind.DISPATCH_INTENT:
            expect_fields(data, _INTENT_FIELDS, "a dispatch intent")
            return DispatchIntent(
                integer_field(data, "call"),
                integer_field(data, "number"),
                string_field(data, "role"),
                string_field(data, "request_digest"),
                string_field(data, "operation"),
                string_field(data, "requested_profile"),
                string_field(data, "client_region"),
                tuple(
                    OperationId(string_item(item, "input_reads"))
                    for item in array_field(data, "input_reads")
                ),
                decode_bound(object_field(data, "bound")),
                integer_field(data, "output_maximum"),
                integer_field(data, "allocation_tokens"),
                integer_field(data, "allocation_pico_usd"),
            )
        case EventKind.DISPATCH_OUTCOME:
            expect_fields(data, _OUTCOME_FIELDS, "a dispatch outcome")
            attribution = object_field(data, "attribution")
            expect_fields(attribution, ("kind", "rule"), "an attribution")
            response = field_of(data, "response")
            return DispatchOutcome(
                integer_field(data, "call"),
                integer_field(data, "number"),
                decode_observation(object_field(data, "observation")),
                None if response is None else as_object(response, "a response"),
                Attribution(
                    AttributionKind(string_field(attribution, "kind")),
                    string_field(attribution, "rule"),
                ),
                optional_string_field(data, "zero_cost_rule"),
                optional_string_field(data, "sent_body_digest"),
            )
        case EventKind.FINALIZATION_ENTERED:
            expect_fields(data, (), "the entry into finalization")
            return FinalizationEntered()
        case EventKind.APPROVAL_REQUESTED:
            expect_fields(data, ("claims", "composition"), "an approval request")
            return ApprovalRequested(
                tuple(
                    decode_claim(as_object(item, "a claim")) for item in array_field(data, "claims")
                ),
                decode_composition(object_field(data, "composition")),
            )
        case EventKind.APPROVED:
            expect_fields(data, ("approver", "payload_digest"), "an approval")
            return Approved(
                Approver(string_field(data, "approver")), string_field(data, "payload_digest")
            )
        case EventKind.RESUMED:
            expect_fields(data, (), "a resume")
            return Resumed()
        case EventKind.COMPLETED:
            expect_fields(data, ("settlement",), "a completion")
            return Completed(_decode_settlement(field_of(data, "settlement")))
        case EventKind.CAP_EXHAUSTED:
            expect_fields(data, ("settlement",), "a cap exhaustion")
            return CapExhausted(_decode_settlement(field_of(data, "settlement")))
        case EventKind.FAILED:
            expect_fields(data, ("category", "site", "reason", "settlement"), "a failure")
            return Failed(
                FailureCategory(string_field(data, "category")),
                decode_failure_site(object_field(data, "site")),
                string_field(data, "reason"),
                _decode_settlement(field_of(data, "settlement")),
            )
        case EventKind.ABANDONED:
            expect_fields(data, ("expected_generation", "reason", "settlement"), "an abandonment")
            return Abandoned(
                integer_field(data, "expected_generation"),
                AbandonmentReason(string_field(data, "reason")),
                _decode_settlement(field_of(data, "settlement")),
            )
        case _:
            assert_never(member)


_INTENT_FIELDS = (
    "call",
    "number",
    "role",
    "request_digest",
    "operation",
    "requested_profile",
    "client_region",
    "input_reads",
    "bound",
    "output_maximum",
    "allocation_tokens",
    "allocation_pico_usd",
)
_OUTCOME_FIELDS = (
    "call",
    "number",
    "observation",
    "response",
    "attribution",
    "zero_cost_rule",
    "sent_body_digest",
)


def _encode_operation_key(key: OperationKey) -> JsonObject:
    match key:
        case PrefetchKey():
            return {"origin": "prefetch", "ordinal": key.ordinal}
        case ModelReadKey():
            return {"origin": "model", "call": key.call, "tool_call": key.tool_call}
        case HarnessReadKey():
            return {"origin": "harness", "policy": key.policy, "ordinal": key.ordinal}
        case _:
            assert_never(key)


def _decode_operation_key(data: Mapping[str, object]) -> OperationKey:
    origin = string_field(data, "origin")
    if origin == "prefetch":
        expect_fields(data, ("origin", "ordinal"), "a prefetch key")
        return PrefetchKey(integer_field(data, "ordinal"))
    if origin == "model":
        expect_fields(data, ("origin", "call", "tool_call"), "a model read key")
        return ModelReadKey(integer_field(data, "call"), string_field(data, "tool_call"))
    if origin == "harness":
        expect_fields(data, ("origin", "policy", "ordinal"), "a harness read key")
        return HarnessReadKey(string_field(data, "policy"), integer_field(data, "ordinal"))
    raise ValueError(f"an operation's origin is prefetch, model or harness, got {origin!r}")


def _encode_resolution(resolution: OperationResult | OperationSkip) -> JsonObject:
    if isinstance(resolution, OperationSkip):
        return {"kind": "skip", "reason": resolution.reason.value}
    return {
        "kind": "result",
        "tool": resolution.tool,
        "source": None if resolution.source is None else resolution.source.value,
        "arguments": thawed_json(resolution.arguments),
        "outcome": encode_outcome(resolution.outcome),
    }


def _decode_resolution(data: Mapping[str, object]) -> OperationResult | OperationSkip:
    kind = string_field(data, "kind")
    if kind == "skip":
        expect_fields(data, ("kind", "reason"), "a skip")
        return OperationSkip(UndispatchedReason(string_field(data, "reason")))
    if kind == "result":
        expect_fields(data, ("kind", "tool", "source", "arguments", "outcome"), "a result")
        source = optional_string_field(data, "source")
        return OperationResult(
            string_field(data, "tool"),
            None if source is None else Source(source),
            object_field(data, "arguments"),
            decode_outcome(object_field(data, "outcome")),
        )
    raise ValueError(f"a resolution is result or skip, got {kind!r}")


def _encode_count_key(key: CountKey) -> JsonObject:
    return {
        "method": encode_method(key.method),
        "counting_identifier": key.counting_identifier,
        "request_digest": key.request_digest,
        "ordinal": key.ordinal,
    }


def _decode_count_key(data: Mapping[str, object]) -> CountKey:
    expect_fields(
        data, ("method", "counting_identifier", "request_digest", "ordinal"), "a count key"
    )
    return CountKey(
        decode_method(object_field(data, "method")),
        string_field(data, "counting_identifier"),
        string_field(data, "request_digest"),
        integer_field(data, "ordinal"),
    )


def _encode_settlement(settlement: LoggedSettlement | None) -> JsonObject | None:
    if settlement is None:
        return None
    return {
        "charged_pico_usd": settlement.charged_pico_usd,
        "state": settlement.state.value,
        "kept_reason": None if settlement.kept_reason is None else settlement.kept_reason.value,
        "ledger_revision": settlement.ledger_revision,
    }


def _decode_settlement(value: object) -> LoggedSettlement | None:
    if value is None:
        return None
    data = as_object(value, "a settlement")
    expect_fields(
        data, ("charged_pico_usd", "state", "kept_reason", "ledger_revision"), "a settlement"
    )
    reason = optional_string_field(data, "kept_reason")
    return LoggedSettlement(
        integer_field(data, "charged_pico_usd"),
        ReservationState(string_field(data, "state")),
        None if reason is None else KeptReason(reason),
        integer_field(data, "ledger_revision"),
    )


_INPUT_FIELDS = (
    "run_id",
    "attempt",
    "context",
    "preregistration_commit",
    "system",
    "retrieval",
    "caps",
    "model_configurations",
    "pricing_selections",
    "counting_identifiers",
    "pricing",
    "prompt_digests",
    "tool_surface_digests",
    "attribution_table",
    "redispatch",
    "retry",
    "prefetch_rule",
    "composing_policy",
    "claim_author",
    "parser",
    "outage",
    "corpus_level",
    "reservation_pico_usd",
    "log_format_version",
)


def _encode_inputs(inputs: FrozenInputs) -> JsonObject:
    caps = inputs.caps
    return {
        "run_id": inputs.run_id,
        "attempt": inputs.attempt,
        "context": encode_run_context(inputs.context),
        "preregistration_commit": inputs.preregistration_commit,
        "system": {"kind": inputs.system.kind.value, "variant": inputs.system.variant},
        "retrieval": {
            "kind": inputs.retrieval.kind.value,
            "embedding_model": inputs.retrieval.embedding_model,
        },
        "caps": {
            "call_cap": caps.call_cap,
            "token_cap": caps.token_cap,
            "finalization_call_reserve": caps.finalization_call_reserve,
            "finalization_token_reserve": caps.finalization_token_reserve,
            "counting_rule": caps.counting_rule,
            "input_bound": encode_method(caps.input_bound),
        },
        "model_configurations": [
            {"role": role, "configuration": encode_call_configuration(configured)}
            for role, configured in inputs.model_configurations
        ],
        "pricing_selections": [
            {
                "role": role,
                "pricing_key": selection.pricing_key,
                "region": selection.region,
                "billing_mode": selection.billing_mode,
            }
            for role, selection in inputs.pricing_selections
        ],
        "counting_identifiers": [
            {"role": role, "counting_identifier": identifier}
            for role, identifier in inputs.counting_identifiers
        ],
        "pricing": {
            "table_digest": inputs.pricing.table_digest,
            "currency": inputs.pricing.currency,
            "effective_from": encode_date(inputs.pricing.effective_from),
            "rows": [encode_rate(row) for row in inputs.pricing.rows],
        },
        "prompt_digests": [
            {"role": role, "name": name, "digest": digest}
            for role, name, digest in inputs.prompt_digests
        ],
        "tool_surface_digests": [
            {"role": role, "digest": digest} for role, digest in inputs.tool_surface_digests
        ],
        "attribution_table": inputs.attribution_table,
        "redispatch": (
            None
            if inputs.redispatch is None
            else {
                "max_dispatches": inputs.redispatch.max_dispatches,
                "delay_ms": inputs.redispatch.delay_ms,
            }
        ),
        "retry": {"after": inputs.retry.after.value, "max_attempts": inputs.retry.max_attempts},
        "prefetch_rule": {
            "identifier": inputs.prefetch_rule.identifier,
            "digest": inputs.prefetch_rule.digest,
        },
        "composing_policy": {
            "identifier": inputs.composing_policy.identifier,
            "digest": inputs.composing_policy.digest,
        },
        "claim_author": inputs.claim_author.value,
        "parser": {"parser": inputs.parser.parser, "schema_digest": inputs.parser.schema_digest},
        "outage": {
            "scheduled_unreachable": sorted(
                source.value for source in inputs.outage.scheduled_unreachable
            ),
            "schedule_digest": inputs.outage.schedule_digest,
        },
        "corpus_level": inputs.corpus_level,
        "reservation_pico_usd": inputs.reservation_pico_usd,
        "log_format_version": inputs.log_format_version,
    }


def _decode_inputs(data: Mapping[str, object]) -> FrozenInputs:
    expect_fields(data, _INPUT_FIELDS, "the frozen inputs")
    system = object_field(data, "system")
    expect_fields(system, ("kind", "variant"), "the system")
    retrieval = object_field(data, "retrieval")
    expect_fields(retrieval, ("kind", "embedding_model"), "the retrieval")
    caps = object_field(data, "caps")
    expect_fields(
        caps,
        (
            "call_cap",
            "token_cap",
            "finalization_call_reserve",
            "finalization_token_reserve",
            "counting_rule",
            "input_bound",
        ),
        "the caps",
    )
    pricing = object_field(data, "pricing")
    expect_fields(pricing, ("table_digest", "currency", "effective_from", "rows"), "the pricing")
    redispatch = field_of(data, "redispatch")
    retry = object_field(data, "retry")
    expect_fields(retry, ("after", "max_attempts"), "the retry rule")
    prefetch = object_field(data, "prefetch_rule")
    expect_fields(prefetch, ("identifier", "digest"), "the prefetch rule")
    composing = object_field(data, "composing_policy")
    expect_fields(composing, ("identifier", "digest"), "the composing policy")
    parser = object_field(data, "parser")
    expect_fields(parser, ("parser", "schema_digest"), "the parser")
    outage = object_field(data, "outage")
    expect_fields(outage, ("scheduled_unreachable", "schedule_digest"), "the outage")
    reservation = field_of(data, "reservation_pico_usd")
    policy = None
    if redispatch is not None:
        held = as_object(redispatch, "the re-dispatch policy")
        expect_fields(held, ("max_dispatches", "delay_ms"), "the re-dispatch policy")
        policy = RedispatchPolicy(
            integer_field(held, "max_dispatches"), integer_field(held, "delay_ms")
        )
    return FrozenInputs(
        run_id=string_field(data, "run_id"),
        attempt=integer_field(data, "attempt"),
        context=decode_run_context(object_field(data, "context")),
        preregistration_commit=string_field(data, "preregistration_commit"),
        system=System(SystemKind(string_field(system, "kind")), string_field(system, "variant")),
        retrieval=Retrieval(
            RetrievalKind(string_field(retrieval, "kind")),
            optional_string_field(retrieval, "embedding_model"),
        ),
        caps=Caps(
            integer_field(caps, "call_cap"),
            integer_field(caps, "token_cap"),
            integer_field(caps, "finalization_call_reserve"),
            integer_field(caps, "finalization_token_reserve"),
            string_field(caps, "counting_rule"),
            decode_method(object_field(caps, "input_bound")),
        ),
        model_configurations=tuple(
            _decode_configured(item) for item in array_field(data, "model_configurations")
        ),
        pricing_selections=tuple(
            _decode_selection(item) for item in array_field(data, "pricing_selections")
        ),
        counting_identifiers=tuple(
            _decode_pair(item, "counting_identifier")
            for item in array_field(data, "counting_identifiers")
        ),
        pricing=PricingBasis(
            string_field(pricing, "table_digest"),
            string_field(pricing, "currency"),
            decode_date(string_field(pricing, "effective_from"), "effective_from"),
            tuple(decode_rate(item) for item in array_field(pricing, "rows")),
        ),
        prompt_digests=tuple(_decode_prompt(item) for item in array_field(data, "prompt_digests")),
        tool_surface_digests=tuple(
            _decode_pair(item, "digest") for item in array_field(data, "tool_surface_digests")
        ),
        attribution_table=optional_string_field(data, "attribution_table"),
        redispatch=policy,
        retry=RetryRule(
            FailureCategory(string_field(retry, "after")), integer_field(retry, "max_attempts")
        ),
        prefetch_rule=PrefetchRule(
            string_field(prefetch, "identifier"), string_field(prefetch, "digest")
        ),
        composing_policy=ComposingPolicy(
            string_field(composing, "identifier"), string_field(composing, "digest")
        ),
        claim_author=ClaimAuthor(string_field(data, "claim_author")),
        parser=RefusedBy(string_field(parser, "parser"), string_field(parser, "schema_digest")),
        outage=OutageAssignment(
            frozenset(
                Source(string_item(item, "scheduled_unreachable"))
                for item in array_field(outage, "scheduled_unreachable")
            ),
            string_field(outage, "schedule_digest"),
        ),
        corpus_level=string_field(data, "corpus_level"),
        reservation_pico_usd=None
        if reservation is None
        else integer_field(data, "reservation_pico_usd"),
        log_format_version=integer_field(data, "log_format_version"),
    )


def _decode_configured(item: object) -> tuple[str, CallConfiguration]:
    data = as_object(item, "a model configuration entry")
    expect_fields(data, ("role", "configuration"), "a model configuration entry")
    return string_field(data, "role"), decode_call_configuration(field_of(data, "configuration"))


def _decode_selection(item: object) -> tuple[str, PricingSelection]:
    data = as_object(item, "a pricing selection")
    expect_fields(data, ("role", "pricing_key", "region", "billing_mode"), "a pricing selection")
    return string_field(data, "role"), PricingSelection(
        string_field(data, "pricing_key"),
        string_field(data, "region"),
        string_field(data, "billing_mode"),
    )


def _decode_pair(item: object, value: str) -> tuple[str, str]:
    data = as_object(item, f"a role's {value}")
    expect_fields(data, ("role", value), f"a role's {value}")
    return string_field(data, "role"), string_field(data, value)


def _decode_prompt(item: object) -> tuple[str, str, str]:
    data = as_object(item, "a prompt digest")
    expect_fields(data, ("role", "name", "digest"), "a prompt digest")
    return string_field(data, "role"), string_field(data, "name"), string_field(data, "digest")


__all__ = [
    "LOG_FORMAT_VERSION",
    "Abandoned",
    "Admitted",
    "ApprovalRequested",
    "Approved",
    "CapExhausted",
    "ClosingEvent",
    "Completed",
    "CountKey",
    "CountOutcomeLogged",
    "CountStarted",
    "DispatchIntent",
    "DispatchOutcome",
    "Envelope",
    "Event",
    "EventKey",
    "EventKind",
    "Failed",
    "FinalizationEntered",
    "FrozenInputs",
    "HarnessReadKey",
    "LoggedEvent",
    "LoggedSettlement",
    "ModelReadKey",
    "OperationEvent",
    "OperationKey",
    "OperationResult",
    "OperationSkip",
    "PrefetchKey",
    "Producer",
    "Resumed",
    "SegmentEnded",
    "SegmentStarted",
    "TerminalEvent",
    "WorkerStamp",
    "call_id",
    "count_id",
    "decode_event",
    "decode_logged_event",
    "encode_event",
    "encode_logged_event",
    "event_bytes",
    "event_digest",
    "event_key",
    "is_worker_event",
    "kind_of",
    "operation_id",
]
