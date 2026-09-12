"""The value codec: every kind round-trips under its spec's tag, an instant span keeps its zone,
and a tag that disagrees with the spec, a value outside the vocabulary, a malformed
criterion or a non-integer count all fail at decode."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.core import (
    DATE_SPAN_VALUE,
    DATE_VALUE,
    INSTANT_SPAN_VALUE,
    REQUIREMENT_VALUE,
    SKILL_VALUE,
    TEXT_VALUE,
    DateSpan,
    EmploymentType,
    EmploymentTypeCriterion,
    EntityKind,
    EntityRef,
    FactValue,
    InstantSpan,
    Requirement,
    SkillCriterion,
    ValueSpec,
    WorkItemStatus,
    decode_value,
    encode_value,
    entity_value,
    enum_value,
)
from leaveimpact.core.ids import SkillId

LONDON = ZoneInfo("Europe/London")
REQUIREMENT = Requirement(
    2, (SkillCriterion(SkillId("kafka")), EmploymentTypeCriterion(EmploymentType.EMPLOYEE))
)


@pytest.mark.parametrize(
    ("spec", "value", "tag"),
    [
        (entity_value(EntityKind.TEAM), EntityRef(EntityKind.TEAM, "team_001"), "entity_ref"),
        (TEXT_VALUE, "Istanbul", "text"),
        (enum_value(WorkItemStatus), WorkItemStatus.DONE, "enum"),
        (SKILL_VALUE, "kafka", "skill"),
        (DATE_VALUE, date(2026, 9, 14), "date"),
        (DATE_SPAN_VALUE, DateSpan(date(2026, 9, 15), date(2026, 9, 19)), "date_span"),
        (
            INSTANT_SPAN_VALUE,
            InstantSpan(
                datetime(2026, 9, 16, 10, tzinfo=UTC), datetime(2026, 9, 16, 11, tzinfo=UTC)
            ),
            "instant_span",
        ),
        (REQUIREMENT_VALUE, REQUIREMENT, "requirement"),
    ],
)
def test_every_kind_round_trips_under_its_own_tag(
    spec: ValueSpec, value: FactValue, tag: str
) -> None:
    encoded = encode_value(value, spec)
    assert encoded["kind"] == tag
    assert decode_value(encoded, spec) == value


def test_a_requirement_criterion_is_tagged_on_the_wire() -> None:
    encoded = encode_value(REQUIREMENT, REQUIREMENT_VALUE)
    assert encoded["value"] == {
        "count": 2,
        "criteria": [
            {"kind": "employment_type", "employment_type": "employee"},
            {"kind": "skill", "skill": "kafka"},
        ],
    }


def test_an_instant_span_keeps_its_zone_as_provenance() -> None:
    span = InstantSpan(
        datetime(2026, 10, 25, 0, 30, tzinfo=LONDON), datetime(2026, 10, 25, 1, 30, tzinfo=LONDON)
    )
    encoded = encode_value(span, INSTANT_SPAN_VALUE)
    assert encoded["value"] == {
        "start": "2026-10-25T00:30:00+01:00",
        "end": "2026-10-25T01:30:00+01:00",
        "zone": "Europe/London",
    }
    decoded = decode_value(encoded, INSTANT_SPAN_VALUE)
    assert isinstance(decoded, InstantSpan)
    assert decoded == span
    assert decoded.start.tzinfo is LONDON
    naive = {
        "kind": "instant_span",
        "value": {"start": "2026-10-25T00:30:00", "end": "x", "zone": None},
    }
    with pytest.raises(ValueError, match="an instant carries its offset"):
        decode_value(naive, INSTANT_SPAN_VALUE)


def test_an_instant_span_refuses_an_unknown_zone_and_an_offset_that_is_not_the_zones() -> None:
    unknown = {
        "kind": "instant_span",
        "value": {
            "start": "2026-10-25T00:30:00+01:00",
            "end": "2026-10-25T01:30:00+01:00",
            "zone": "Nowhere/Place",
        },
    }
    with pytest.raises(ValueError, match="not an IANA timezone key: 'Nowhere/Place'"):
        decode_value(unknown, INSTANT_SPAN_VALUE)
    # Written at UTC, labelled London in summer: the encoder never produces the pair, and
    # converting it would decode to a value whose re-encoding is not these bytes.
    skewed = {
        "kind": "instant_span",
        "value": {
            "start": "2026-07-01T09:00:00+00:00",
            "end": "2026-07-01T10:00:00+00:00",
            "zone": "Europe/London",
        },
    }
    written_as = "which Europe/London writes as '2026-07-01T10:00:00\\+01:00'"
    with pytest.raises(ValueError, match=written_as):
        decode_value(skewed, INSTANT_SPAN_VALUE)


def test_a_spelling_the_encoder_never_writes_is_refused_for_instants_and_dates() -> None:
    zulu = {
        "kind": "instant_span",
        "value": {"start": "2026-07-01T09:00:00Z", "end": "2026-07-01T10:00:00Z", "zone": None},
    }
    with pytest.raises(ValueError, match="spelled '2026-07-01T09:00:00Z', canonical is"):
        decode_value(zulu, INSTANT_SPAN_VALUE)
    basic = {"kind": "date", "value": "20260701"}
    with pytest.raises(ValueError, match="a date is spelled '20260701', canonical is '2026-07-01'"):
        decode_value(basic, DATE_VALUE)


def test_a_tag_that_disagrees_with_the_spec_is_refused_before_the_payload() -> None:
    with pytest.raises(ValueError, match="tagged 'text' where a skill is declared"):
        decode_value({"kind": "text", "value": "kafka"}, SKILL_VALUE)
    with pytest.raises(ValueError, match="expected a skill, got 'Kafka'"):
        encode_value("Kafka", SKILL_VALUE)


def test_a_decoded_value_still_passes_the_spec() -> None:
    with pytest.raises(ValueError, match="expected an enum from WorkItemStatus, got 'closed'"):
        decode_value({"kind": "enum", "value": "closed"}, enum_value(WorkItemStatus))
    with pytest.raises(ValueError, match="expected an entity_ref to a team, got an entity_ref"):
        decode_value(
            {"kind": "entity_ref", "value": {"kind": "component", "id": "comp_001"}},
            entity_value(EntityKind.TEAM),
        )


def test_a_malformed_requirement_is_refused() -> None:
    with pytest.raises(ValueError, match="count is an integer, got bool"):
        decode_value(
            {"kind": "requirement", "value": {"count": True, "criteria": []}}, REQUIREMENT_VALUE
        )
    with pytest.raises(
        ValueError, match="a criterion is a skill or an employment_type, got kind 'grade'"
    ):
        decode_value(
            {"kind": "requirement", "value": {"count": 1, "criteria": [{"kind": "grade"}]}},
            REQUIREMENT_VALUE,
        )
    with pytest.raises(ValueError, match="a skill criterion has fields"):
        decode_value(
            {"kind": "requirement", "value": {"count": 1, "criteria": [{"kind": "skill"}]}},
            REQUIREMENT_VALUE,
        )
