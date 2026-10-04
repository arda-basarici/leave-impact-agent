"""Stated facts and their statuses round-trip through canonical JSON with their meaning: a
refused input never reads back as a fact, and an absent field is absent, never empty."""

import pytest

from leaveimpact.core import PredicateName, Requirement, SkillCriterion
from leaveimpact.core.ids import skill_id
from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.stated import (
    Admitted,
    FactRefusal,
    PlacementState,
    Refused,
    RefusedInput,
    SpanPlacement,
    StatedFact,
    Unstatable,
)
from leaveimpact.core.stated_json import (
    decode_admission,
    decode_emission,
    decode_excluded,
    decode_placement,
    decode_stated_fact,
    encode_admission,
    encode_emission,
    encode_excluded,
    encode_placement,
    encode_stated_fact,
)
from leaveimpact.core.stated_view import Excluded, Exclusion
from tests.unit import stated_fixture as f

SKILL = StatedFact(PredicateName.HAS_SKILL, f.DENIZ_REF, "kafka", f.COMMENT_REF, f.REMARK)
REQUIRES = StatedFact(
    PredicateName.REQUIRES,
    f.CLAUSE_REF,
    Requirement(2, (SkillCriterion(skill_id("kafka")),)),
    f.CLAUSE_REF,
    f.CLAUSE_TEXT,
    f.TITLE,
)


def test_a_stated_fact_round_trips_and_only_a_requirement_has_a_span() -> None:
    for stated in (SKILL, REQUIRES):
        assert decode_stated_fact(encode_stated_fact(stated)) == stated
    assert "target_span" not in encode_stated_fact(SKILL)
    assert encode_stated_fact(REQUIRES)["target_span"] == f.TITLE
    assert canonical_json(encode_stated_fact(SKILL)) == (
        '{"predicate":"has_skill","subject":{"kind":"employee","id":"emp_023"},'
        '"value":{"kind":"skill","value":"kafka"},'
        '"carrier":{"kind":"comment","id":"comment_001"},'
        '"quote":"I ran the Kafka migration last year and can take this one."}'
    )


def test_a_span_on_anything_else_and_a_requirement_without_one_are_refused_as_shape() -> None:
    with pytest.raises(ValueError, match=r"surplus \['target_span'\]"):
        decode_stated_fact(encode_stated_fact(SKILL) | {"target_span": "Kafka"})
    without = {k: v for k, v in encode_stated_fact(REQUIRES).items() if k != "target_span"}
    with pytest.raises(ValueError, match=r"missing \['target_span'\]"):
        decode_stated_fact(without)


def test_a_decoded_fact_is_built_through_its_constructor() -> None:
    cut = encode_stated_fact(REQUIRES) | {"target_span": f.REGIONAL_TITLE}
    with pytest.raises(Unstatable, match="a substring of its quote"):
        decode_stated_fact(cut)


def test_an_emission_is_a_statement_or_a_refused_input_and_never_both() -> None:
    refused = RefusedInput('{"carrier":"LIA-42"}', FactRefusal.MALFORMED_CARRIER, "LIA-42")
    for emission in (SKILL, refused):
        assert decode_emission(encode_emission(emission)) == emission
    encoded = encode_emission(refused)
    assert encoded == {
        "emission": "refused_input",
        "raw": '{"carrier":"LIA-42"}',
        "reason": "malformed_carrier",
        "detail": "LIA-42",
    }
    with pytest.raises(ValueError, match="surplus"):
        decode_emission(encoded | {"fact": encode_stated_fact(SKILL)})
    with pytest.raises(ValueError, match="an emission is stated or refused_input"):
        decode_emission({"emission": "withdrawn"})


def test_an_admission_keeps_the_fact_whole_in_both_cases() -> None:
    refused = Refused(SKILL, FactRefusal.MISSING_ANCHOR, "none of ('Deniz Kaya',) appears")
    for admission in (Admitted(SKILL), refused):
        assert decode_admission(encode_admission(admission)) == admission
    assert encode_admission(refused)["fact"] == encode_stated_fact(SKILL)
    assert set(encode_admission(Admitted(SKILL))) == {"admission", "fact"}
    # A reason no fact can exist under does not decode as a refused fact.
    undecodable = encode_admission(refused) | {"reason": "undecodable"}
    with pytest.raises(ValueError, match="no stated fact can exist under"):
        decode_admission(undecodable)


def test_a_placement_writes_only_the_fields_its_state_has() -> None:
    placed = SpanPlacement(PlacementState.PLACED, artifact=f.TICKET_REF)
    unplaced = SpanPlacement(PlacementState.UNPLACED)
    ambiguous = SpanPlacement(PlacementState.AMBIGUOUS, among=(f.TICKET_REF, f.REGIONAL_REF))
    for placement in (placed, unplaced, ambiguous):
        assert decode_placement(encode_placement(placement)) == placement
    assert set(encode_placement(placed)) == {"state", "artifact"}
    assert encode_placement(unplaced) == {"state": "unplaced"}
    assert set(encode_placement(ambiguous)) == {"state", "among"}
    # Absent is not empty: an unplaced span with an empty list is another shape.
    with pytest.raises(ValueError, match=r"surplus \['among'\]"):
        decode_placement({"state": "unplaced", "among": []})
    with pytest.raises(ValueError, match="names the artifacts it lay among"):
        decode_placement({"state": "ambiguous", "among": []})


def test_an_exclusion_round_trips_with_its_reason() -> None:
    owner = StatedFact(
        PredicateName.OWNS_WORK_ITEM, f.TICKET_REF, f.DENIZ_REF, f.CLAUSE_REF, f.CLAUSE_TEXT
    )
    for excluded in (
        Excluded(owner, Exclusion.CONFLICTING_CARRIERS),
        Excluded(SKILL, Exclusion.CARRIER_WITHDRAWN),
    ):
        assert decode_excluded(encode_excluded(excluded)) == excluded
    assert encode_excluded(Excluded(owner, Exclusion.CONFLICTING_CARRIERS))["reason"] == (
        "conflicting_carriers"
    )
    # A reason the fact cannot have does not decode: a set-valued predicate has no conflict.
    with pytest.raises(ValueError, match="has_skill holds a set"):
        decode_excluded({"fact": encode_stated_fact(SKILL), "reason": "conflicting_readings"})


def test_a_placement_on_something_prose_does_not_title_does_not_decode() -> None:
    with pytest.raises(ValueError, match="binds a ticket, a meeting or a document"):
        decode_placement({"state": "placed", "artifact": {"kind": "employee", "id": "emp_017"}})
