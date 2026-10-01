"""What a run did, in order: the model calls made, the reads attempted, the claims it ended with.

The trace is the part of a run export the grading replays. The evaluator re-derives
every fact from the records the operations returned, derives the run condition from
the reads that failed, counts the required-source attempts, the malformed calls and
the extra reads, and asks of each search whether the key's section sat in its top-k;
none of that needs a prompt or a line of assistant prose, so none is here (the
investigator milestone's second build step, ruling 3). Model calls appear as compact
records all the same, one per invocation even when it emitted no tool call and no
claim, because the finalization call, a refusal and the single-shot baseline's one
call are attempts the accounting counts and the usage ledger prices.

Three closed shapes carry the facts a replay needs and nothing the model could invent.
An *operation* is one attempted read: an opaque identifier the event log assigned,
its origin (the frozen prefetch, or the model call it answered), the tool and the
source it resolved to, the arguments exactly as accepted (the wrapper coerces and
defaults nothing, so accepted arguments are the effective ones), and one of six
*outcomes*: a record, no record, a sequence of records that may be empty, the source
unreachable, a record the adapter could not translate, or a call the wrapper refused
before any source was asked. The first three are completed reads, the next two failed
reads, and the last is neither a read nor a source attempt. Only an unreachable
outcome moves the observed run condition; a malformed record ends the attempt by
defect. An empty sequence and no record are different evidence and stay different.
Every accepted read names its source itself, because an absent result carries no
``Observed`` to read it from and the evaluator may not import the registry that would
resolve it. A *model call record* holds the identifier, the role, how the call ended,
the provider's stop reason, its latency, the digest of the exact rendered request,
and the usage the provider reported — each counter present only when reported, never
synthesized as zero, so a missing counter stays unknown and the cost it would have
priced stays incomplete.

Order is the sequence's own. Repeated reads stay repeated operations, since a later
replay policy may care that the same thing was read twice and in what order.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import NewType, cast

from leaveimpact.core.claims import Claim
from leaveimpact.core.enums import Source
from leaveimpact.core.ports.observed import Entity, Observed

OperationId = NewType("OperationId", str)
"""The event log's identifier of one attempted read, opaque here, unique within a trace."""

ModelCallId = NewType("ModelCallId", str)
"""The event log's identifier of one model invocation, opaque here, unique within a trace."""

SHA256_HEX_LENGTH = 64

USAGE_COUNTER_NAMES: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_write_input_tokens",
)
"""Every usage counter a provider may report, in the order a record holds them: append-only,
so a record sealed with fewer holds a prefix of this order and reads the rest as unavailable."""


def require_opaque_id(value: str, what: str) -> str:
    """``value`` if it is a usable identifier: non-empty with no surrounding whitespace."""
    if not value or value != value.strip():
        raise ValueError(f"{what} is a non-empty identifier, got {value!r}")
    return value


def require_integer(value: object, what: str, *, minimum: int = 0) -> int:
    """``value`` if it is an exact integer at least ``minimum``: never a boolean, never a float.

    >>> require_integer(True, "attempt")
    Traceback (most recent call last):
    ...
    ValueError: attempt is an integer, got True
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} is an integer, got {value!r}")
    if value < minimum:
        raise ValueError(f"{what} is at least {minimum}, got {value}")
    return value


def frozen_json(value: object, what: str) -> object:
    """``value`` as an immutable copy of a JSON value, refused if JSON could not carry it.

    Objects become read-only mappings and arrays tuples, all the way down, so a record
    holding the result cannot change under a caller that keeps the original; a value
    outside JSON's own (a date, a set, a non-finite float) is refused rather than
    serialized by surprise later.

    >>> frozen = frozen_json({"span": {"start": "2026-09-10", "end": "2026-09-12"}}, "arguments")
    >>> frozen["span"]["end"]
    '2026-09-12'
    """
    match value:
        case None | bool() | int() | str():
            return value
        case float():
            if not isfinite(value):
                raise ValueError(f"{what} holds a non-finite float, which JSON cannot carry")
            return value
        case list() | tuple():
            items = cast("list[object] | tuple[object, ...]", value)
            return tuple(frozen_json(item, what) for item in items)
        case Mapping():
            frozen: dict[str, object] = {}
            for key, item in cast("Mapping[object, object]", value).items():
                if not isinstance(key, str):
                    raise ValueError(f"{what} has a non-string key {key!r}")
                frozen[key] = frozen_json(item, what)
            return MappingProxyType(frozen)
        case _:
            raise ValueError(f"{what} holds {type(value).__name__}, which JSON cannot carry")


def require_digest(value: str, what: str) -> str:
    """``value`` if it is a lower-case SHA-256 hex digest."""
    if len(value) != SHA256_HEX_LENGTH or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{what} is a SHA-256 hex digest, got {value!r}")
    return value


# --- Usage and cost --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Usage:
    """The counters one call's provider reported, in the declared order, each only if reported.

    >>> usage = Usage((("input_tokens", 120), ("output_tokens", 30)))
    >>> usage.value("cache_read_input_tokens") is None
    True
    >>> Usage((("output_tokens", 30), ("input_tokens", 120)))
    Traceback (most recent call last):
    ...
    ValueError: usage counters are held in the declared order, got ['output_tokens', 'input_tokens']
    """

    counters: tuple[tuple[str, int], ...]

    def __post_init__(self) -> None:
        names = [name for name, _ in self.counters]
        unknown = [name for name in names if name not in USAGE_COUNTER_NAMES]
        if unknown:
            raise ValueError(f"not a usage counter a provider reports: {', '.join(unknown)}")
        if len(set(names)) != len(names):
            raise ValueError("a usage counter is reported once")
        declared = [name for name in USAGE_COUNTER_NAMES if name in names]
        if names != declared:
            raise ValueError(f"usage counters are held in the declared order, got {names}")
        for name, value in self.counters:
            require_integer(value, f"{name}: a usage counter")

    def value(self, name: str) -> int | None:
        """The counter ``name`` if the provider reported it; ``None`` is unknown, never zero."""
        for held, value in self.counters:
            if held == name:
                return value
        return None


@dataclass(frozen=True, slots=True)
class Cost:
    """A priced amount in integer nano-dollars, and whether every counter it needed was reported.

    Integer nano-dollars because the price table states rates as integers per token, so
    a product never rounds (ruling 5); ``complete`` is false when a counter the rate
    would have priced was not reported, so the amount is a floor, never a total.
    """

    nano_usd: int
    complete: bool

    def __post_init__(self) -> None:
        require_integer(self.nano_usd, "a cost in nano-dollars")
        if not isinstance(cast(object, self.complete), bool):
            raise ValueError(f"a cost's completeness is a boolean, got {self.complete!r}")


# --- Model calls -----------------------------------------------------------------------


class ModelCallOutcome(StrEnum):
    """How one invocation ended, as the harness classified the response.

    ``TEXT`` is a response with neither a tool call nor claims, which the loop treats as
    the model having nothing more to read; ``REFUSAL`` is a response that declined;
    ``INVALID_OUTPUT`` is a response the claim codec rejected. All three are system
    behaviour, graded with their omissions; only ``PROVIDER_FAULT`` is infrastructure,
    counted apart (ruling 3d).
    """

    TOOL_CALLS = "tool_calls"
    CLAIMS = "claims"
    TEXT = "text"
    REFUSAL = "refusal"
    INVALID_OUTPUT = "invalid_output"
    PROVIDER_FAULT = "provider_fault"

    @property
    def answered(self) -> bool:
        """Whether a response arrived at all; a provider fault is the one case it did not."""
        return self is not ModelCallOutcome.PROVIDER_FAULT


@dataclass(frozen=True, slots=True)
class ModelCallRecord:
    """One model invocation, compact: identity, role, how it ended, what it cost, no prose.

    ``request_digest`` is the SHA-256 of the exact rendered request, beside the prompt
    policy's asset digests the run record holds, the generator's own pattern. The
    provider's stop reason and its reported latency exist exactly when a response
    arrived, so a fault carries no invented ones; ``usage`` is ``None`` when the
    provider reported nothing, which a fault always is since usage arrives with the
    response, and a cost exists only over a usage. ``fault`` is the provider's reason,
    present exactly on a provider fault.
    """

    id: ModelCallId
    role: str
    outcome: ModelCallOutcome
    stop_reason: str | None
    provider_latency_ms: int | None
    request_digest: str
    usage: Usage | None
    cost: Cost | None
    fault: str | None

    def __post_init__(self) -> None:
        require_opaque_id(self.id, "a model call id")
        require_opaque_id(self.role, "a role")
        require_digest(self.request_digest, "request_digest")
        answered = self.outcome.answered
        if (self.stop_reason is not None) != answered:
            raise ValueError("a stop reason is recorded exactly when a response arrived")
        if (self.provider_latency_ms is not None) != answered:
            raise ValueError("a provider latency is recorded exactly when a response arrived")
        if self.provider_latency_ms is not None:
            require_integer(self.provider_latency_ms, "provider latency in ms")
        if (self.fault is not None) != (not answered):
            raise ValueError("a fault is recorded exactly on a provider fault")
        if not answered and self.usage is not None:
            raise ValueError("a provider fault reports no usage; usage arrives with a response")
        if self.cost is not None and self.usage is None:
            raise ValueError("a cost prices a reported usage; none was reported")


# --- Operations ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PrefetchOrigin:
    """The read was the frozen prefetch's, its arguments constructed by the harness."""


@dataclass(frozen=True, slots=True)
class ModelOrigin:
    """The read answered a tool call the model made in the invocation ``model_call``."""

    model_call: ModelCallId

    def __post_init__(self) -> None:
        require_opaque_id(self.model_call, "a model call id")


type Origin = PrefetchOrigin | ModelOrigin


@dataclass(frozen=True, slots=True)
class RecordOutcome:
    """A single read found its record."""

    record: Observed[Entity]


@dataclass(frozen=True, slots=True)
class AbsentOutcome:
    """A single read found nothing: evidence of absence, not a failure."""


@dataclass(frozen=True, slots=True)
class RecordsOutcome:
    """An enumerating read or a search returned these records in this order, possibly none."""

    records: tuple[Observed[Entity], ...]


@dataclass(frozen=True, slots=True)
class UnreachableOutcome:
    """The source could not answer after the adapter's retries: a run condition."""

    source: Source
    reason: str


@dataclass(frozen=True, slots=True)
class DefectOutcome:
    """The source answered and the record at ``locator`` could not be translated: a defect."""

    source: Source
    locator: str
    reason: str


@dataclass(frozen=True, slots=True)
class RefusedCallOutcome:
    """The wrapper refused the call's arguments before any source was asked."""

    reason: str


type Outcome = (
    RecordOutcome
    | AbsentOutcome
    | RecordsOutcome
    | UnreachableOutcome
    | DefectOutcome
    | RefusedCallOutcome
)


def is_completed_read(outcome: Outcome) -> bool:
    """Whether the source answered: a record, no record, or a sequence."""
    return isinstance(outcome, RecordOutcome | AbsentOutcome | RecordsOutcome)


def is_failed_read(outcome: Outcome) -> bool:
    """Whether a source was asked and the read failed: unreachable, or a malformed record."""
    return isinstance(outcome, UnreachableOutcome | DefectOutcome)


@dataclass(frozen=True, slots=True)
class Operation:
    """One attempted read: who asked, what was asked, of which source, and what came back.

    ``source`` is ``None`` only for a refused call whose tool name resolved to nothing;
    every other outcome names the one source the tool reads, and every record returned
    was read from it.

    >>> Operation(OperationId("op-1"), PrefetchOrigin(), "employees", None, {}, AbsentOutcome())
    Traceback (most recent call last):
    ...
    ValueError: an accepted read names its source; only a refused call may name none
    """

    id: OperationId
    origin: Origin
    tool: str
    source: Source | None
    arguments: Mapping[str, object]
    outcome: Outcome

    def __post_init__(self) -> None:
        require_opaque_id(self.id, "an operation id")
        require_opaque_id(self.tool, "a tool name")
        object.__setattr__(self, "arguments", frozen_json(dict(self.arguments), "arguments"))
        if self.source is None and not isinstance(self.outcome, RefusedCallOutcome):
            raise ValueError("an accepted read names its source; only a refused call may name none")
        for record in _records_of(self.outcome):
            if record.source is not self.source:
                raise ValueError(
                    f"a record read from {record.source.value} in an operation on {_name(self)}"
                )
        outcome = self.outcome
        if (
            isinstance(outcome, UnreachableOutcome | DefectOutcome)
            and outcome.source is not self.source
        ):
            raise ValueError(
                f"a failure of {outcome.source.value} in an operation on {_name(self)}"
            )


def _records_of(outcome: Outcome) -> tuple[Observed[Entity], ...]:
    if isinstance(outcome, RecordOutcome):
        return (outcome.record,)
    if isinstance(outcome, RecordsOutcome):
        return outcome.records
    return ()


def _name(operation: Operation) -> str:
    return "no source" if operation.source is None else operation.source.value


# --- The trace -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunTrace:
    """The model calls, the attempted reads and the final claims of one run attempt.

    Calls and operations keep the order they happened in. Claims are held in claim-id
    order, the claim codec's own, since a claim's position says nothing (its id is its
    identity and the grading matches by key), and one order means the export's bytes
    are a property of the trace and not of the emission. Identifiers are unique within
    their kind, and every read the model asked for names a model call this trace holds
    that emitted tool calls; those are the structural facts a replay stands on. What the
    record block claims about the trace (the cumulative usage, the observed condition)
    is not enforced here: the evaluator verifies a claim against the trace, and a
    constructor that enforced it would hide the mismatch the verification exists to
    report.
    """

    model_calls: tuple[ModelCallRecord, ...]
    operations: tuple[Operation, ...]
    claims: tuple[Claim, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "claims", tuple(sorted(self.claims, key=lambda claim: claim.claim_id))
        )
        call_ids = [call.id for call in self.model_calls]
        if len(set(call_ids)) != len(call_ids):
            raise ValueError("model call ids are unique within a trace")
        operation_ids = [operation.id for operation in self.operations]
        if len(set(operation_ids)) != len(operation_ids):
            raise ValueError("operation ids are unique within a trace")
        by_id = {call.id: call for call in self.model_calls}
        for operation in self.operations:
            origin = operation.origin
            if not isinstance(origin, ModelOrigin):
                continue
            call = by_id.get(origin.model_call)
            if call is None:
                raise ValueError(
                    f"operation {operation.id} answers model call {origin.model_call!r}, "
                    "which the trace does not hold"
                )
            if call.outcome is not ModelCallOutcome.TOOL_CALLS:
                raise ValueError(
                    f"operation {operation.id} answers model call {origin.model_call!r}, "
                    f"which emitted {call.outcome.value}, not tool calls"
                )
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("claim ids are unique within a trace")

    def model_call(self, id: ModelCallId) -> ModelCallRecord:
        """The model call record ``id`` names; ``KeyError`` is a bug, the constructor checked."""
        for call in self.model_calls:
            if call.id == id:
                return call
        raise KeyError(id)

    def operation(self, id: OperationId) -> Operation | None:
        """The operation ``id`` names, or ``None``."""
        for operation in self.operations:
            if operation.id == id:
                return operation
        return None

    def model_call_or_none(self, id: ModelCallId) -> ModelCallRecord | None:
        """The model call record ``id`` names, or ``None``."""
        for call in self.model_calls:
            if call.id == id:
                return call
        return None
