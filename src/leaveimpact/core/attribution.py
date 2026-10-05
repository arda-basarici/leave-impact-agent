"""The attribution table: how a measurement reads what a model dispatch observed.

A dispatch records two things apart (the contract step's ruling on dispatches). The
*observation* is what arrived, kept as it arrived. The *attribution* is how the measurement
reads it: as behaviour of the system under test, as an infrastructure fault, or as a defect
of the harness. The reading is not code scattered through a client. It is this table, plain
data the preregistration holds and names by digest, so that which failures count against a
system is fixed before any result exists and a record can say which row decided each one.

A row is a match and a reading. The match names one kind of observation and may constrain
the fields that kind carries; a row with no constraint takes every observation of its kind.
Rows are tried in the order the table holds them and the first that matches decides. Order
is therefore part of the table's meaning, and the digest covers it with the matching rule's
name. A table is refused unless every kind of observation ends in an unconstrained row, so
nothing a dispatch can observe is left without a reading, and a row after its kind's
unconstrained one is refused as unreachable. An unconstrained row may say it is the
*unmatched* one: the reading given because nothing more specific applied, which a report
counts apart from a reading a rule chose.

A defect is never read from an error code alone. A request the harness built against its own
contract and a request the service was right to reject for another reason can carry the same
code, so a defect row requires a *cause*: a member of a closed list the harness supplies
with the observation when it has established it. The table does not hold the evidence. The
attribution names the row, the row names the cause, and the failure recorded at that
dispatch holds where and why.

Two columns say what may follow an infrastructure reading: whether the logical call may be
dispatched again inside the run, and whether a failure on it makes the run eligible for a
new attempt. They are set only on an infrastructure row. Behaviour is the graded result and
a defect is never retried, since a retry could hide it.

An intent with no recorded outcome is not a row. Nothing was observed, the send is zero or
one, and its reading is always unresolved (``UNRESOLVED_RULE``, which lives with the
dispatch that must name it and is named again from here).

``RedispatchPolicy`` is the bound the harness dispatches under: no layer beneath a dispatch
retries, so a second send of a logical call is a new dispatch, at most this many, each
after the registered backoff.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

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
    UNRESOLVED_RULE,
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
from leaveimpact.core.run_trace import require_integer, require_opaque_id

TABLE_ENVELOPE_VERSION = 1
"""The shape of what the table's digest hashes; raised when the envelope's own shape changes."""

MATCHING_RULE = "first_match_in_row_order"
"""The name of how a row is chosen, held by the digest: whoever changes ``attribute`` renames
the rule with it, and a registered digest stops matching."""


class ObservationKind(StrEnum):
    """The kinds of observation a row can match; a member is the wire format, the same name
    the export gives the observation."""

    COMPLETE_RESPONSE = "complete_response"
    BROKEN_STREAM = "broken_stream"
    SERVICE_ERROR = "service_error"
    CLIENT_ERROR = "client_error"
    REFUSED_BEFORE_SEND = "refused_before_send"


class Cause(StrEnum):
    """What the harness established about an observation beyond what the observation holds.

    ``HARNESS_REQUEST_CONTRACT``: the request broke the harness's own rendering or
    validation contract, shown by the harness's check of the request it built and not
    inferred from the error that came back.
    """

    HARNESS_REQUEST_CONTRACT = "harness_request_contract"


def kind_of(observation: Observation) -> ObservationKind | None:
    """The kind a row would match ``observation`` under, ``None`` for no recorded outcome."""
    match observation:
        case CompleteResponse():
            return ObservationKind.COMPLETE_RESPONSE
        case BrokenStream():
            return ObservationKind.BROKEN_STREAM
        case ServiceError():
            return ObservationKind.SERVICE_ERROR
        case ClientError():
            return ObservationKind.CLIENT_ERROR
        case RefusedBeforeSend():
            return ObservationKind.REFUSED_BEFORE_SEND
        case NoRecordedOutcome():
            return None


_CONSTRAINTS: Mapping[str, ObservationKind] = {
    "stop_reasons": ObservationKind.COMPLETE_RESPONSE,
    "http_statuses": ObservationKind.SERVICE_ERROR,
    "codes": ObservationKind.SERVICE_ERROR,
    "original_statuses": ObservationKind.SERVICE_ERROR,
    "message_signatures": ObservationKind.SERVICE_ERROR,
    "client_errors": ObservationKind.CLIENT_ERROR,
}
"""Each constraint with the one kind of observation that carries the field it reads."""


@dataclass(frozen=True, slots=True)
class Match:
    """Which observations a row takes: one kind, narrowed by the constraints that are set.

    A constraint is a set of admitted values and ``None`` when the row does not ask. Every
    set constraint must hold. ``original_statuses`` is asked of the status a service relays
    from the model, and a service error that relays none does not meet it. ``cause``, when
    set, must be the cause the harness supplied.

    >>> Match(ObservationKind.CLIENT_ERROR, stop_reasons=frozenset({"end_turn"}))
    Traceback (most recent call last):
    ...
    ValueError: stop_reasons constrains a complete_response, not a client_error
    """

    observation: ObservationKind
    stop_reasons: frozenset[str] | None = None
    http_statuses: frozenset[int] | None = None
    codes: frozenset[str] | None = None
    original_statuses: frozenset[int] | None = None
    message_signatures: frozenset[str] | None = None
    client_errors: frozenset[ClientErrorKind] | None = None
    cause: Cause | None = None

    def __post_init__(self) -> None:
        for name, carried_by in _CONSTRAINTS.items():
            admitted = getattr(self, name)
            if admitted is None:
                continue
            if carried_by is not self.observation:
                raise ValueError(
                    f"{name} constrains a {carried_by.value}, not a {self.observation.value}"
                )
            if not admitted:
                raise ValueError(f"{name} admits at least one value; an empty set matches nothing")

    @property
    def unconstrained(self) -> bool:
        """Whether the row takes every observation of its kind, whatever cause was supplied."""
        return self.cause is None and all(getattr(self, name) is None for name in _CONSTRAINTS)

    def takes(self, observation: Observation, cause: Cause | None) -> bool:
        """Whether ``observation``, with the ``cause`` the harness established, is this row's."""
        if kind_of(observation) is not self.observation:
            return False
        if self.cause is not None and self.cause is not cause:
            return False
        match observation:
            case CompleteResponse():
                return _admits(self.stop_reasons, observation.stop_reason)
            case ServiceError():
                return (
                    _admits(self.http_statuses, observation.http_status)
                    and _admits(self.codes, observation.code)
                    and _admits(self.original_statuses, observation.original_status)
                    and _admits(self.message_signatures, observation.message_signature)
                )
            case ClientError():
                return _admits(self.client_errors, observation.kind)
            case _:
                return True


def _admits[T](admitted: frozenset[T] | None, value: T | None) -> bool:
    return admitted is None or value in admitted


@dataclass(frozen=True, slots=True)
class AttributionRow:
    """One rule of the table: a match, the reading it gives, and what may follow.

    ``redispatch`` says the logical call may be dispatched again inside the run and
    ``new_attempt`` that a failure on this reading makes the run eligible for a new
    attempt; both only ever on an infrastructure row. ``unmatched`` marks the row as the
    reading given for want of a more specific one.

    >>> AttributionRow("denied", Match(ObservationKind.SERVICE_ERROR), AttributionKind.DEFECT)
    Traceback (most recent call last):
    ...
    ValueError: the defect row denied requires a cause; a defect is not read from an error alone
    """

    identifier: str
    match: Match
    reading: AttributionKind
    redispatch: bool = False
    new_attempt: bool = False
    unmatched: bool = False

    def __post_init__(self) -> None:
        require_opaque_id(self.identifier, "an attribution rule")
        if self.identifier == UNRESOLVED_RULE:
            raise ValueError(f"{UNRESOLVED_RULE} names the unresolved reading and is no row")
        if self.reading is AttributionKind.UNRESOLVED:
            raise ValueError(
                f"the row {self.identifier} reads an observation; unresolved is the reading "
                "of no recorded outcome"
            )
        if self.reading is AttributionKind.DEFECT and self.match.cause is None:
            raise ValueError(
                f"the defect row {self.identifier} requires a cause; a defect is not read "
                "from an error alone"
            )
        if self.reading is not AttributionKind.INFRASTRUCTURE and (
            self.redispatch or self.new_attempt
        ):
            raise ValueError(
                f"the row {self.identifier} reads {self.reading.value}; only an infrastructure "
                "reading may be followed by another dispatch or a new attempt"
            )
        if self.unmatched and not self.match.unconstrained:
            raise ValueError(
                f"the row {self.identifier} is marked unmatched and constrains its match; the "
                "unmatched reading is the one given when nothing narrower applied"
            )


@dataclass(frozen=True, slots=True)
class AttributionTable:
    """The rows in the order they are tried.

    Held to what makes a reading total and every row reachable: an identifier once, every
    kind of observation ending in an unconstrained row, and no row of a kind after it.
    """

    rows: tuple[AttributionRow, ...]

    def __post_init__(self) -> None:
        identifiers = [row.identifier for row in self.rows]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f"an attribution rule is identified once, got {identifiers}")
        for kind in ObservationKind:
            held = [row for row in self.rows if row.match.observation is kind]
            if not held or not held[-1].match.unconstrained:
                raise ValueError(
                    f"the rows for a {kind.value} end in one that takes every such "
                    "observation, so none is left without a reading"
                )
            shadowed = [row.identifier for row in held[:-1] if row.match.unconstrained]
            if shadowed:
                raise ValueError(
                    f"the row {shadowed[0]} takes every {kind.value}, so the rows after it "
                    "are never reached"
                )

    def row(self, identifier: str) -> AttributionRow | None:
        """The row identified as ``identifier``, or ``None``."""
        for row in self.rows:
            if row.identifier == identifier:
                return row
        return None


def attribute(
    table: AttributionTable, observation: Observation, cause: Cause | None = None
) -> tuple[Attribution, AttributionRow | None]:
    """How ``table`` reads ``observation``: the attribution a dispatch records, and the row
    that decided it, ``None`` for no recorded outcome, which no row reads.

    ``cause`` is what the harness established about the observation, if anything. The
    first row in order whose match takes the observation decides; a table always has one.
    """
    if isinstance(observation, NoRecordedOutcome):
        return Attribution(AttributionKind.UNRESOLVED, UNRESOLVED_RULE), None
    for row in table.rows:
        if row.match.takes(observation, cause):
            return Attribution(row.reading, row.identifier), row
    raise AssertionError("a table holds an unconstrained row for every kind of observation")


def attribution_table_digest(table: AttributionTable) -> str:
    """SHA-256 over the table as data: the envelope version, the matching rule by name and
    the rows in their order, in canonical JSON. What a run record names its attributions'
    table by.

    >>> rows = tuple(AttributionRow(k.value, Match(k), AttributionKind.INFRASTRUCTURE)
    ...              for k in ObservationKind)
    >>> len(attribution_table_digest(AttributionTable(rows)))
    64
    """
    envelope: JsonObject = {
        "envelope_version": TABLE_ENVELOPE_VERSION,
        "matching": MATCHING_RULE,
        "rows": encode_attribution_table(table),
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


@dataclass(frozen=True, slots=True)
class RedispatchPolicy:
    """The bound a logical call is dispatched under: at most ``max_dispatches`` dispatches,
    the first included, each later one after a backoff of ``delay_ms``.

    The backoff is fixed, with no jitter: one serialized client has no herd to spread, and
    a fixed wait reproduces. It is the deliberate wait and not a bound on the interval
    between an outcome and the next dispatch, which also holds the request's preparation,
    its count and the attempt's lock.

    >>> RedispatchPolicy(0, 1000)
    Traceback (most recent call last):
    ...
    ValueError: max_dispatches is at least 1, got 0
    """

    max_dispatches: int
    delay_ms: int

    def __post_init__(self) -> None:
        require_integer(self.max_dispatches, "max_dispatches", minimum=1)
        require_integer(self.delay_ms, "delay_ms")


# --- JSON ----------------------------------------------------------------------------------

_MATCH_FIELDS = ("observation", *_CONSTRAINTS, "cause")
_ROW_FIELDS = ("identifier", "match", "reading", "redispatch", "new_attempt", "unmatched")


def encode_attribution_table(table: AttributionTable) -> list[object]:
    """The JSON array of a table: its rows in order, every field written, a constraint that
    is not asked as ``null`` and one that is as its values in sorted order."""
    return [_encode_row(row) for row in table.rows]


def _encode_row(row: AttributionRow) -> JsonObject:
    match = row.match
    return {
        "identifier": row.identifier,
        "match": {
            "observation": match.observation.value,
            "stop_reasons": _sorted(match.stop_reasons),
            "http_statuses": _sorted(match.http_statuses),
            "codes": _sorted(match.codes),
            "original_statuses": _sorted(match.original_statuses),
            "message_signatures": _sorted(match.message_signatures),
            "client_errors": _sorted(
                None
                if match.client_errors is None
                else frozenset(kind.value for kind in match.client_errors)
            ),
            "cause": None if match.cause is None else match.cause.value,
        },
        "reading": row.reading.value,
        "redispatch": row.redispatch,
        "new_attempt": row.new_attempt,
        "unmatched": row.unmatched,
    }


def _sorted[T: (int, str)](values: frozenset[T] | None) -> list[object] | None:
    return None if values is None else list(sorted(values))


def decode_attribution_table(value: object) -> AttributionTable:
    """The table ``value`` encodes; ``ValueError`` names what is malformed. A constraint
    written out of order decodes to the same table, so bytes holding it are not canonical
    and a byte decoder that re-encodes refuses them."""
    if not isinstance(value, list):
        raise ValueError(f"an attribution table is a JSON array, got {type(value).__name__}")
    return AttributionTable(tuple(_decode_row(item) for item in cast("list[object]", value)))


def _decode_row(item: object) -> AttributionRow:
    data = as_object(item, "an attribution row")
    expect_fields(data, _ROW_FIELDS, "an attribution row")
    match = object_field(data, "match")
    expect_fields(match, _MATCH_FIELDS, "an attribution match")
    cause = optional_string_field(match, "cause")
    errors = _strings(match, "client_errors")
    return AttributionRow(
        string_field(data, "identifier"),
        Match(
            ObservationKind(string_field(match, "observation")),
            stop_reasons=_strings(match, "stop_reasons"),
            http_statuses=_integers(match, "http_statuses"),
            codes=_strings(match, "codes"),
            original_statuses=_integers(match, "original_statuses"),
            message_signatures=_strings(match, "message_signatures"),
            client_errors=(
                None if errors is None else frozenset(ClientErrorKind(name) for name in errors)
            ),
            cause=None if cause is None else Cause(cause),
        ),
        AttributionKind(string_field(data, "reading")),
        redispatch=_boolean(data, "redispatch"),
        new_attempt=_boolean(data, "new_attempt"),
        unmatched=_boolean(data, "unmatched"),
    )


def _strings(data: Mapping[str, object], key: str) -> frozenset[str] | None:
    if field_of(data, key) is None:
        return None
    return frozenset(string_item(item, key) for item in array_field(data, key))


def _integers(data: Mapping[str, object], key: str) -> frozenset[int] | None:
    if field_of(data, key) is None:
        return None
    return frozenset(require_integer(item, key) for item in array_field(data, key))


def _boolean(data: Mapping[str, object], key: str) -> bool:
    value = field_of(data, key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} is true or false, got {type(value).__name__}")
    return value


def encode_redispatch_policy(policy: RedispatchPolicy) -> JsonObject:
    """The JSON object of a re-dispatch policy."""
    return {"max_dispatches": policy.max_dispatches, "delay_ms": policy.delay_ms}


def decode_redispatch_policy(value: object) -> RedispatchPolicy:
    """The re-dispatch policy ``value`` encodes; ``ValueError`` names what is malformed."""
    data = as_object(value, "a re-dispatch policy")
    expect_fields(data, ("max_dispatches", "delay_ms"), "a re-dispatch policy")
    return RedispatchPolicy(integer_field(data, "max_dispatches"), integer_field(data, "delay_ms"))


__all__ = [
    "MATCHING_RULE",
    "TABLE_ENVELOPE_VERSION",
    "UNRESOLVED_RULE",
    "AttributionRow",
    "AttributionTable",
    "Cause",
    "Match",
    "ObservationKind",
    "RedispatchPolicy",
    "attribute",
    "attribution_table_digest",
    "decode_attribution_table",
    "decode_redispatch_policy",
    "encode_attribution_table",
    "encode_redispatch_policy",
    "kind_of",
]
