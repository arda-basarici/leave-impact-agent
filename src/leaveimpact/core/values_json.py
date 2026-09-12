"""JSON for fact values: tagged by the predicate's value kind, decoded through the domain types.

A value never travels alone — it sits in a conflict's observation or a fact — and the
predicate beside it declares its spec, so the codec is spec-driven: the encoder writes
the spec's kind as the tag, and the decoder refuses a tag that disagrees with the spec
before it reads the payload (DESIGN, "The rules in code": the JSON tag is the spec's
kind rather than a second declaration). Enum members and skills travel as strings
under their own tags; a requirement's criteria carry a ``kind`` each so that a sealed
answer key survives a later criterion; an instant span keeps its IANA zone beside
the offset-bearing timestamps, since the zone is provenance for how a human read the
time and ``fromisoformat`` alone would flatten it to an offset.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import assert_never
from zoneinfo import ZoneInfo

from leaveimpact.core.enums import EmploymentType, EntityKind
from leaveimpact.core.ids import SkillId
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    expect_fields,
    integer_field,
    object_field,
    string_field,
)
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.values import (
    Criterion,
    EmploymentTypeCriterion,
    FactValue,
    Requirement,
    SkillCriterion,
    ValueKind,
    ValueSpec,
)
from leaveimpact.core.worldtime import DateSpan, InstantSpan, date_at, instant_at


def encode_ref(ref: EntityRef) -> JsonObject:
    """The JSON object of an entity reference."""
    return {"kind": ref.kind.value, "id": ref.id}


def decode_ref(data: Mapping[str, object]) -> EntityRef:
    """The entity reference ``data`` describes, validated by the domain constructor."""
    expect_fields(data, ("kind", "id"), "an entity ref")
    return EntityRef(EntityKind(string_field(data, "kind")), string_field(data, "id"))


def encode_value(value: FactValue, spec: ValueSpec) -> JsonObject:
    """``value`` tagged by ``spec``'s kind; a value the spec refuses raises ``ValueError``.

    >>> from leaveimpact.core.values import DATE_VALUE
    >>> encode_value(date(2026, 9, 14), DATE_VALUE)
    {'kind': 'date', 'value': '2026-09-14'}
    """
    spec.check(value)
    return {"kind": spec.kind.value, "value": _encode_payload(value)}


def _encode_payload(value: FactValue) -> object:
    match value:
        case EntityRef():
            return encode_ref(value)
        case Requirement():
            return {
                "count": value.count,
                "criteria": [_encode_criterion(criterion) for criterion in value.criteria],
            }
        case DateSpan():
            return {"start": value.start.isoformat(), "end": value.end.isoformat()}
        case InstantSpan():
            return {
                "start": value.start.isoformat(),
                "end": value.end.isoformat(),
                "zone": _zone_key(value.start),
            }
        case date():
            return value.isoformat()
        case str():
            return value
        case _:
            assert_never(value)


def _encode_criterion(criterion: Criterion) -> JsonObject:
    match criterion:
        case SkillCriterion():
            return {"kind": "skill", "skill": criterion.skill}
        case EmploymentTypeCriterion():
            return {"kind": "employment_type", "employment_type": criterion.employment_type.value}
        case _:
            assert_never(criterion)


def _zone_key(instant: datetime) -> str | None:
    return instant.tzinfo.key if isinstance(instant.tzinfo, ZoneInfo) else None


def decode_value(data: Mapping[str, object], spec: ValueSpec) -> FactValue:
    """The value ``data`` carries, which must be tagged with ``spec``'s kind and satisfy it.

    >>> from leaveimpact.core.values import DATE_VALUE, SKILL_VALUE
    >>> decode_value({"kind": "date", "value": "2026-09-14"}, DATE_VALUE)
    datetime.date(2026, 9, 14)
    >>> decode_value({"kind": "text", "value": "kafka"}, SKILL_VALUE)
    Traceback (most recent call last):
    ...
    ValueError: a fact value tagged 'text' where a skill is declared
    """
    expect_fields(data, ("kind", "value"), "a fact value")
    tag = string_field(data, "kind")
    if tag != spec.kind.value:
        raise ValueError(f"a fact value tagged {tag!r} where {spec.describe()} is declared")
    value = _decode_payload(spec.kind, data)
    spec.check(value)
    return value


def _decode_payload(kind: ValueKind, data: Mapping[str, object]) -> FactValue:
    match kind:
        case ValueKind.ENTITY_REF:
            return decode_ref(object_field(data, "value"))
        case ValueKind.TEXT | ValueKind.ENUM | ValueKind.SKILL:
            return string_field(data, "value")
        case ValueKind.DATE:
            return date_at(string_field(data, "value"), "a date")
        case ValueKind.DATE_SPAN:
            span = object_field(data, "value")
            expect_fields(span, ("start", "end"), "a date span")
            return DateSpan(
                date_at(string_field(span, "start"), "start"),
                date_at(string_field(span, "end"), "end"),
            )
        case ValueKind.INSTANT_SPAN:
            span = object_field(data, "value")
            expect_fields(span, ("start", "end", "zone"), "an instant span")
            zone = _zone(span)
            return InstantSpan(
                _instant(string_field(span, "start"), zone),
                _instant(string_field(span, "end"), zone),
            )
        case ValueKind.REQUIREMENT:
            requirement = object_field(data, "value")
            expect_fields(requirement, ("count", "criteria"), "a requirement")
            return Requirement(
                integer_field(requirement, "count"),
                tuple(
                    _decode_criterion(as_object(item, "a criterion"))
                    for item in array_field(requirement, "criteria")
                ),
            )
        case _:
            assert_never(kind)


def _zone(span: Mapping[str, object]) -> str | None:
    zone = span["zone"]
    if zone is None:
        return None
    if not isinstance(zone, str):
        raise ValueError(f"zone is a string or null, got {type(zone).__name__}")
    return zone


def _instant(text: str, zone: str | None) -> datetime:
    return instant_at(text, zone, "an instant")


def _decode_criterion(data: Mapping[str, object]) -> Criterion:
    kind = string_field(data, "kind")
    if kind == "skill":
        expect_fields(data, ("kind", "skill"), "a skill criterion")
        return SkillCriterion(SkillId(string_field(data, "skill")))
    if kind == "employment_type":
        expect_fields(data, ("kind", "employment_type"), "an employment type criterion")
        return EmploymentTypeCriterion(EmploymentType(string_field(data, "employment_type")))
    raise ValueError(f"a criterion is a skill or an employment_type, got kind {kind!r}")
