"""The review payload an approval's digest is over, and the two parts whose encoding carries
a check of its own: a usage's counters against its raw object, a batch entry by its tag. The
parts' round trips are the export codec's tests and the format's acceptance fixtures."""

import json
from typing import cast

import pytest

from leaveimpact.core import (
    Admitted,
    ClaimAuthor,
    ComposingPolicy,
    Composition,
    Cost,
    PlacementState,
    PredicateName,
    ReportedUsage,
    RequirementPlacement,
    SpanPlacement,
    Unknown,
    UnknownReason,
    decode_run_export,
    employee_ref,
    encode_run_export,
    review_payload,
    review_payload_digest,
)
from leaveimpact.core.ids import claim_id, employee_id
from leaveimpact.core.jsonshape import canonical_json
from leaveimpact.core.run_parts_json import decode_cost, decode_usage, encode_cost, encode_usage
from leaveimpact.core.stated_json import encode_admission, encode_emission
from tests.unit import format2_fixtures as cases
from tests.unit import stated_fixture as f

POLICY = ComposingPolicy("stated-fact-composer", "a" * 64)
EMPTY = Composition(ClaimAuthor.RULES, POLICY, (), ())


def unknown(number: int) -> Unknown:
    return Unknown(
        claim_id=claim_id(number),
        evidence_refs=(),
        subject=employee_ref(employee_id(17)),
        required_fact=PredicateName.HAS_SKILL,
        reason=UnknownReason.ABSENT,
    )


def test_an_abstentions_empty_payload_is_a_payload_with_a_digest_of_its_own() -> None:
    payload = review_payload((), EMPTY)
    assert payload == {
        "claims": [],
        "author": "rules",
        "policy": {"identifier": "stated-fact-composer", "digest": "a" * 64},
        "unbound": [],
        "exclusions": [],
    }
    assert review_payload_digest((), EMPTY) != review_payload_digest((unknown(1),), EMPTY)


def test_the_payload_is_the_claims_in_id_order_whatever_order_they_were_given_in() -> None:
    forward = review_payload_digest((unknown(1), unknown(2)), EMPTY)
    assert forward == review_payload_digest((unknown(2), unknown(1)), EMPTY)


def test_who_composed_and_under_which_policy_is_part_of_what_was_approved() -> None:
    claims = (unknown(1),)
    by_model = Composition(ClaimAuthor.MODEL, POLICY, (), ())
    other_policy = Composition(ClaimAuthor.RULES, ComposingPolicy("other", "a" * 64), (), ())
    digests = {
        review_payload_digest(claims, composed) for composed in (EMPTY, by_model, other_policy)
    }
    assert len(digests) == 3


def test_an_unbound_requirement_is_in_the_payload_and_a_placed_one_is_in_its_claims() -> None:
    placed = RequirementPlacement(
        cases.requirement(f.TITLE),
        SpanPlacement(PlacementState.PLACED, artifact=f.TICKET_REF),
    )
    ambiguous = RequirementPlacement(
        cases.requirement("Release review"),
        SpanPlacement(PlacementState.AMBIGUOUS, among=(f.TICKET_REF, f.REGIONAL_REF)),
    )
    composed = Composition(ClaimAuthor.RULES, POLICY, (placed, ambiguous), ())
    unbound = cast(list[object], review_payload((), composed)["unbound"])
    assert len(unbound) == 1
    assert '"state":"ambiguous"' in canonical_json(unbound)
    only_placed = Composition(ClaimAuthor.RULES, POLICY, (placed,), ())
    assert review_payload((), only_placed)["unbound"] == []


def test_a_usage_is_written_with_its_reading_and_refused_when_the_two_disagree() -> None:
    usage = ReportedUsage({"inputTokens": 13, "cacheWriteInputTokens": 7270, "outputTokens": 4})
    encoded = json.loads(canonical_json(encode_usage(usage)))
    assert encoded["counters"] == [
        {"name": "input_tokens", "value": 13},
        {"name": "output_tokens", "value": 4},
        {"name": "cache_write_input_tokens", "value": 7270},
    ]
    assert decode_usage(encoded) == usage
    encoded["counters"].pop()
    with pytest.raises(ValueError, match="counters are the reading of its raw object"):
        decode_usage(encoded)
    with pytest.raises(ValueError, match=r"a usage has fields .*missing \['counters'\]"):
        decode_usage({"raw": {}})


def test_a_cost_is_pico_dollars_with_a_boolean_completeness_or_null() -> None:
    assert encode_cost(None) is None and decode_cost(None) is None
    assert encode_cost(Cost(297_000_000, True)) == {"pico_usd": 297_000_000, "complete": True}
    assert decode_cost({"pico_usd": 5, "complete": False}) == Cost(5, False)
    with pytest.raises(ValueError, match="complete is a boolean, got 1"):
        decode_cost({"pico_usd": 5, "complete": 1})
    with pytest.raises(ValueError, match=r"a cost has fields .*surplus \['nano_usd'\]"):
        decode_cost({"nano_usd": 5, "pico_usd": 5, "complete": True})


def test_a_stated_fact_outside_an_admission_is_no_batch_entry() -> None:
    """An entry is a refused input or an admission; a bare stated fact says nothing of
    whether it entered the view, so the codec refuses it where a batch is decoded."""
    data = json.loads(canonical_json(encode_run_export(cases.handled_fact_tool())))
    batch = data["trace"]["model_calls"][0]["answer"]["fact_batches"][0]
    assert batch["entries"] == [json.loads(canonical_json(encode_admission(Admitted(cases.SKILL))))]
    batch["entries"] = [encode_emission(cases.SKILL)]
    with pytest.raises(ValueError, match="a stated fact is held inside its admission"):
        decode_run_export(data)
