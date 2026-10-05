"""The review payload an approval's digest is over, and the two parts whose encoding carries
a check of its own: a usage's counters against its raw object, a batch entry by its tag. The
parts' round trips are the export codec's tests and the format's acceptance fixtures."""

import json
from typing import cast

import pytest

from leaveimpact.core import (
    Abandonment,
    AbandonmentReason,
    Admitted,
    ClaimAuthor,
    ClientErrorKind,
    ComposingPolicy,
    Composition,
    Cost,
    CountClientError,
    Counted,
    CountingOperation,
    CountingOperationId,
    CountLocalError,
    CountResult,
    CountServiceError,
    InputBoundSite,
    KeptReason,
    NoRecordedOutcome,
    PlacementState,
    PredicateName,
    RegisteredInputBound,
    ReportedUsage,
    RequirementPlacement,
    Reservation,
    ReservationState,
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
from leaveimpact.core.jsonshape import JsonObject, canonical_json
from leaveimpact.core.run_parts_json import (
    decode_abandonment,
    decode_cost,
    decode_counting_operation,
    decode_failure_site,
    decode_reservation,
    decode_usage,
    encode_abandonment,
    encode_cost,
    encode_counting_operation,
    encode_failure_site,
    encode_reservation,
    encode_usage,
)
from leaveimpact.core.stated_json import encode_admission, encode_emission
from tests.unit import format_fixtures as cases
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


def test_a_counting_operation_is_written_with_its_outcome_by_kind_and_the_workers_reading() -> None:
    method = RegisteredInputBound("provider_count", 1)
    outcomes = (
        Counted(4_096, "req-1", 100),
        CountServiceError(429, "ThrottlingException", "rate exceeded", None, 80),
        CountClientError(ClientErrorKind.CONNECTION, 1_200),
        CountLocalError("builtins.KeyError"),
        NoRecordedOutcome(),
    )
    readings = (
        CountResult.COUNTED,
        CountResult.FAILED,
        CountResult.FAILED,
        CountResult.UNCLASSIFIED,
        CountResult.UNRESOLVED,
    )
    kinds: list[str] = []
    encoded: JsonObject = {}
    for outcome, reading in zip(outcomes, readings, strict=True):
        recorded = not isinstance(outcome, NoRecordedOutcome)
        count = CountingOperation(
            CountingOperationId("count-1"), method, "model-a-base", "a" * 64, 1, 4,
            5 if recorded else None, outcome, reading,
        )
        encoded = cast(JsonObject, json.loads(canonical_json(encode_counting_operation(count))))
        kinds.append(str(cast(JsonObject, encoded["outcome"])["kind"]))
        assert encoded["reading"] == reading.value
        assert encoded["method"] == {"method": "provider_count", "version": 1}
        assert decode_counting_operation(encoded) == count
    assert kinds == [
        "counted", "service_error", "client_error", "local_error", "no_recorded_outcome"
    ]
    with pytest.raises(ValueError, match="a count outcome is counted, service_error"):
        decode_counting_operation({**encoded, "outcome": {"kind": "estimated"}})
    with pytest.raises(ValueError, match="provider_count is registered at version 1, got 2"):
        decode_counting_operation({**encoded, "method": {"method": "provider_count", "version": 2}})


def test_the_input_bound_site_the_reason_and_the_charge_are_in_the_wire_format() -> None:
    site = InputBoundSite(CountingOperationId("count-3"))
    assert encode_failure_site(site) == {"kind": "input_bound", "counting_operation": "count-3"}
    assert decode_failure_site(encode_failure_site(site)) == site
    with pytest.raises(ValueError, match="operation, dispatch, input_bound or harness"):
        decode_failure_site({"kind": "ledger"})
    command = Abandonment("operator", 2, AbandonmentReason.INTERRUPTED)
    assert encode_abandonment(command) == {
        "authority": "operator",
        "ownership_generation": 2,
        "reason": "interrupted",
    }
    assert decode_abandonment(encode_abandonment(command)) == command
    with pytest.raises(ValueError, match=r"an abandonment has fields .*missing \['reason'\]"):
        decode_abandonment({"authority": "operator", "ownership_generation": 2})
    held = Reservation(5_000_000_000, ReservationState.KEPT, KeptReason.USAGE_INCOMPLETE, 7, 4_000)
    assert encode_reservation(held) == {
        "pico_usd": 5_000_000_000,
        "state": "kept",
        "kept_reason": "usage_incomplete",
        "ledger_revision": 7,
        "charged_pico_usd": 4_000,
    }
    assert decode_reservation(encode_reservation(held)) == held
