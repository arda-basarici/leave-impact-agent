"""The codec: every type round-trips, the encoding is canonical and byte-stable, non-ASCII
text passes through, and every malformed input — an unknown tag, a field mismatch, a
wrong JSON type, an id outside its namespace, a payload the domain refuses — fails
loudly at decode."""

import json
from dataclasses import replace
from datetime import date
from typing import cast

import pytest

from leaveimpact.core import (
    Claim,
    CoverageAction,
    CoverageActionKind,
    Observation,
    Source,
    SourceConflict,
    decode_claim,
    decode_claims,
    encode_claim,
    encode_claims,
)


def test_every_type_round_trips(sample_claims: tuple[Claim, ...]) -> None:
    assert decode_claims(encode_claims(sample_claims)) == sample_claims


def test_the_canonical_encoding_is_byte_stable_under_permutation(
    sample_claims: tuple[Claim, ...],
) -> None:
    text = encode_claims(sample_claims)
    assert encode_claims(decode_claims(text)) == text
    permuted = sample_claims[3:] + sample_claims[:3]
    assert permuted != sample_claims
    assert encode_claims(permuted) == text
    assert " " not in text.split('"rationale"')[0]


def test_a_claim_built_in_any_field_order_round_trips_to_itself(
    sample_claims: tuple[Claim, ...],
) -> None:
    action = sample_claims[-1]
    assert isinstance(action, CoverageAction)
    built = replace(action, derived_from_claim_ids=tuple(reversed(action.derived_from_claim_ids)))
    assert built == action
    assert decode_claim(encode_claim(built)) == built


def test_decoding_keeps_the_array_order(sample_claims: tuple[Claim, ...]) -> None:
    permuted = sample_claims[3:] + sample_claims[:3]
    assert decode_claims(encode_claims(permuted)) == sample_claims


def test_the_type_tag_comes_first_then_the_shared_fields(sample_claims: tuple[Claim, ...]) -> None:
    for claim in sample_claims:
        keys = list(encode_claim(claim))
        assert keys[:4] == ["type", "claim_id", "evidence_refs", "derived_from_claim_ids"]
        assert keys[0] == "type" and encode_claim(claim)["type"] == claim.claim_type.value


def test_non_ascii_text_passes_through_unescaped(sample_claims: tuple[Claim, ...]) -> None:
    text = encode_claims(sample_claims)
    assert "İK" in text and "\\u" not in text


def test_fact_values_are_tagged_by_kind(sample_claims: tuple[Claim, ...], a_date: date) -> None:
    conflict = next(claim for claim in sample_claims if isinstance(claim, SourceConflict))
    encoded = encode_claim(conflict)
    leaver = {"kind": "employee", "id": "emp_017"}
    assert encoded["resolved_value"] == {"kind": "entity_ref", "value": leaver}
    dated = SourceConflict(
        claim_id=conflict.claim_id,
        evidence_refs=(),
        entity=conflict.entity,
        predicate=conflict.predicate,
        observations=(Observation(Source.JIRA, a_date), Observation(Source.CORPUS, "2026-09-14")),
        resolved_value=a_date,
        authority_rule=conflict.authority_rule,
    )
    encoded = encode_claim(dated)
    assert encoded["resolved_value"] == {"kind": "date", "value": "2026-09-14"}
    decoded = decode_claim(encoded)
    assert isinstance(decoded, SourceConflict)
    assert decoded == dated and decoded.resolved_value == a_date


def _mutated(claim: Claim, **changes: object) -> dict[str, object]:
    data = encode_claim(claim)
    for key, value in changes.items():
        if value is ...:
            del data[key]
        else:
            data[key] = value
    return data


def test_an_unknown_type_tag_is_refused(sample_claims: tuple[Claim, ...]) -> None:
    with pytest.raises(ValueError, match="'risk' is not a valid ClaimType"):
        decode_claim(_mutated(sample_claims[0], type="risk"))


def test_a_missing_or_surplus_field_is_refused(sample_claims: tuple[Claim, ...]) -> None:
    with pytest.raises(ValueError, match="type is missing"):
        decode_claim(_mutated(sample_claims[0], type=...))
    with pytest.raises(ValueError, match=r"missing \['subtype'\], surplus \[\]"):
        decode_claim(_mutated(sample_claims[0], subtype=...))
    with pytest.raises(ValueError, match=r"missing \[\], surplus \['reasoning'\]"):
        decode_claim(_mutated(sample_claims[0], reasoning="because"))


def test_a_wrong_json_type_is_refused(sample_claims: tuple[Claim, ...]) -> None:
    with pytest.raises(ValueError, match="claim_id is a string, got int"):
        decode_claim(_mutated(sample_claims[0], claim_id=1))
    with pytest.raises(ValueError, match="evidence_refs is a JSON array, got dict"):
        decode_claim(_mutated(sample_claims[0], evidence_refs={}))
    with pytest.raises(ValueError, match="artifact is a JSON object, got str"):
        decode_claim(_mutated(sample_claims[0], artifact="ticket_042"))
    with pytest.raises(ValueError, match="a claim set is a JSON array, got dict"):
        decode_claims("{}")


def test_an_unknown_fact_value_kind_is_refused(sample_claims: tuple[Claim, ...]) -> None:
    conflict = next(claim for claim in sample_claims if isinstance(claim, SourceConflict))
    with pytest.raises(ValueError, match="an entity_ref, a date or text, got kind 'int'"):
        decode_claim(_mutated(conflict, resolved_value={"kind": "int", "value": 3}))


def test_a_reference_outside_its_namespace_is_refused_by_the_domain(
    sample_claims: tuple[Claim, ...],
) -> None:
    with pytest.raises(ValueError, match="a work_item id has the form ticket_NNN, got 'LIA-42'"):
        decode_claim(_mutated(sample_claims[0], artifact={"kind": "work_item", "id": "LIA-42"}))
    with pytest.raises(ValueError, match="'issue' is not a valid EntityKind"):
        decode_claim(_mutated(sample_claims[0], artifact={"kind": "issue", "id": "ticket_042"}))


def test_a_payload_the_domain_refuses_fails_at_decode(sample_claims: tuple[Claim, ...]) -> None:
    action = sample_claims[-1]
    with pytest.raises(ValueError, match="an assign action names at least one assignee"):
        decode_claim(_mutated(action, action=CoverageActionKind.ASSIGN.value))


def test_the_text_is_plain_json(sample_claims: tuple[Claim, ...]) -> None:
    parsed = cast(object, json.loads(encode_claims(sample_claims)))
    assert isinstance(parsed, list)
    assert len(cast(list[object], parsed)) == len(sample_claims)
