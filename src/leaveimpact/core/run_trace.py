"""The reads of a run, and the primitives every part of a run export shares.

The trace is the part of a run export the grading replays. The evaluator re-derives
every fact from the records the operations returned, derives the run condition from
the reads that failed, counts the required-source attempts, the malformed calls and
the extra reads, and asks of each search whether the key's section sat in its top-k;
none of that needs a prompt or a line of assistant prose, so none is here (the
investigator milestone's second build step, ruling 3). This module holds the half of
the trace that is reads; the model calls are ``model_calls``'s, and the two meet with
the claims in the trace type beside the export.

An *operation* is one attempted read: an opaque identifier the event log assigned,
its origin (the frozen prefetch, a read the harness issued under a registered policy,
or the model call it answered), the tool and the source it resolved to, the arguments
exactly as accepted (the wrapper coerces and defaults nothing, so accepted arguments
are the effective ones), and one of six *outcomes*: a record, no record, a sequence of
records that may be empty, the source unreachable, a record the adapter could not
translate, or a call the wrapper refused before any source was asked. The first three
are completed reads, the next two failed reads, and the last is neither a read nor a
source attempt. Only an unreachable outcome moves the observed run condition; a
malformed record ends the attempt by defect. An empty sequence and no record are
different evidence and stay different. Every accepted read names its source itself,
because an absent result carries no ``Observed`` to read it from and the evaluator may
not import the registry that would resolve it.

An operation in a trace also holds its *position*: where its result's append sits in
the attempt's event order, which is what orders it against a model dispatch (neither
clock does). An operation built outside a trace, by a rule or a test that reads
outcomes, has none.

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

from leaveimpact.core.enums import Source
from leaveimpact.core.ports.observed import Entity, Observed

OperationId = NewType("OperationId", str)
"""The event log's identifier of one attempted read, opaque here, unique within a trace."""

ModelCallId = NewType("ModelCallId", str)
"""The event log's identifier of one model invocation, opaque here, unique within a trace."""

CountingOperationId = NewType("CountingOperationId", str)
"""The event log's identifier of one token-counting request, opaque here, unique within a trace."""


class ClientErrorKind(StrEnum):
    """How a client gave up on a remote call with no answer from the service; a member is the
    wire format. Shared by a model dispatch and a counting request, which fail the same two
    ways on the client's side."""

    TIMEOUT = "timeout"
    CONNECTION = "connection"


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


def require_integer(value: object, what: str, *, minimum: int | None = 0) -> int:
    """``value`` if it is an exact integer, never a boolean or a float, at least ``minimum`` if one.

    >>> require_integer(True, "attempt")
    Traceback (most recent call last):
    ...
    ValueError: attempt is an integer, got True
    >>> require_integer(-5, "a bound", minimum=None)
    -5
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} is an integer, got {value!r}")
    if minimum is not None and value < minimum:
        raise ValueError(f"{what} is at least {minimum}, got {value}")
    return value


def frozen_json(value: object, what: str) -> object:
    """``value`` as an immutable copy of a JSON value, refused if JSON could not carry it.

    Objects become read-only mappings with their keys in sorted order and arrays tuples,
    all the way down, so a record holding the result cannot change under a caller that
    keeps the original and two equal argument objects are equal in bytes whatever order
    the caller spelled them in (a key's position says nothing in JSON); a value outside
    JSON's own (a date, a set, a non-finite float) is refused rather than serialized by
    surprise later.

    >>> frozen = frozen_json({"span": {"start": "2026-09-10", "end": "2026-09-12"}}, "arguments")
    >>> frozen["span"]["end"]
    '2026-09-12'
    >>> list(frozen_json({"b": 1, "a": 2}, "arguments"))
    ['a', 'b']
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
            return MappingProxyType(dict(sorted(frozen.items())))
        case _:
            raise ValueError(f"{what} holds {type(value).__name__}, which JSON cannot carry")


def thawed_json(value: object) -> object:
    """A frozen JSON value (``frozen_json``) back as the lists and dicts the serializer writes."""
    match value:
        case Mapping():
            items = cast("Mapping[object, object]", value).items()
            return {str(key): thawed_json(item) for key, item in items}
        case tuple() | list():
            return [thawed_json(item) for item in cast("tuple[object, ...] | list[object]", value)]
        case _:
            return value


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
    """A priced amount in integer pico-dollars, and whether every counter it needed was reported.

    Integer pico-dollars because the price table states rates as integers per token, so
    a product never rounds, and pico-dollars per token is the coarsest unit in which every
    rate the project pays is an integer (the contract step's ruling on the rate unit: the
    smallest models' cache reads are fractions of a nano-dollar). ``complete`` is false
    when a counter the rate would have priced was not reported, so the amount is a floor,
    never a total.
    """

    pico_usd: int
    complete: bool

    def __post_init__(self) -> None:
        require_integer(self.pico_usd, "a cost in pico-dollars")
        if not isinstance(cast(object, self.complete), bool):
            raise ValueError(f"a cost's completeness is a boolean, got {self.complete!r}")


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


@dataclass(frozen=True, slots=True)
class HarnessOrigin:
    """The read was issued by the harness outside the frozen prefetch, under the registered
    policy or component ``policy`` names: a single-shot system's retrieval query, the
    documents a full-context system is shown. Who asked for a read is not what a model was
    shown; that is the dispatch's input reads."""

    policy: str

    def __post_init__(self) -> None:
        require_opaque_id(self.policy, "the policy that issued a harness read")


type Origin = PrefetchOrigin | HarnessOrigin | ModelOrigin


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
    was read from it. ``position`` is where the operation's result sits in the attempt's
    event order, held by every operation of a trace and by none built outside one.

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
    position: int | None = None

    def __post_init__(self) -> None:
        require_opaque_id(self.id, "an operation id")
        require_opaque_id(self.tool, "a tool name")
        if self.position is not None:
            require_integer(self.position, "an operation's position", minimum=1)
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
