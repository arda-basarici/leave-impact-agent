"""Canonical JSON for claims: one encoder, one decoder, the domain constructors as the validation.

A claim set crosses the seam as text — the answer key sealed in a bucket, an agent's
report in the event log — and this module is the single place that knows the shape.
The encoding is canonical so equal claim sets from one emitter produce equal bytes:
claims sorted by claim id, fields in declared order, compact separators, UTF-8 passed
through, enum members as their values, dates as ISO strings, every claim tagged by
``type`` and every fact value by its predicate's value kind (the value codec's rule).
Claim order carries no meaning — identity is the grading key, dependency is
``derived_from_claim_ids``, and the order a reader sees is the report view's to
compute — so a permutation of a set is the same set here. (Two emitters mint
different claim ids for the same facts, which is why "equal bytes" holds within one
emitter's numbering: sealing and replay need that, grading does not.) Decoding
builds the domain types through their own constructors and adds nothing of its own
beyond shape: an unknown tag, a missing or surplus field, a wrong JSON type, or a
payload the domain refuses all raise ``ValueError`` from here, and the domain's
invariants are checked once, in the domain (DESIGN, "The vocabulary in code").
Pydantic stays out of ``core``; a schema for the agent's structured output is the
investigator milestone's concern, at its own edge.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import assert_never, cast

from leaveimpact.core.claims import (
    AssessmentReason,
    AuthorityRule,
    CandidateAssessment,
    Claim,
    ClaimType,
    Constraint,
    CoverageAction,
    CoverageActionKind,
    Impact,
    ImpactKey,
    ImpactSubtype,
    SourceConflict,
    Unknown,
    UnknownReason,
    Verdict,
)
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import ClaimId, ClauseId, EmployeeId, LeaveId
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    canonical_json,
    expect_fields,
    object_field,
    optional_string_field,
    string_field,
    string_item,
)
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.refs import EvidenceRef
from leaveimpact.core.values import Observation, ValueSpec
from leaveimpact.core.values_json import decode_ref, decode_value, encode_ref, encode_value

# --- Encoding ---------------------------------------------------------------------


def encode_claims(claims: Sequence[Claim]) -> str:
    """The canonical JSON text of ``claims``: one object per claim, sorted by claim id.

    >>> encode_claims(())
    '[]'
    """
    ordered = sorted(claims, key=lambda claim: claim.claim_id)
    return canonical_json([encode_claim(claim) for claim in ordered])


def encode_claim(claim: Claim) -> JsonObject:
    """The JSON object of one claim, ``type`` first, shared fields next, own fields last."""
    shared: JsonObject = {
        "type": claim.claim_type.value,
        "claim_id": claim.claim_id,
        "evidence_refs": [_encode_evidence(evidence) for evidence in claim.evidence_refs],
        "derived_from_claim_ids": list(claim.derived_from_claim_ids),
    }
    return shared | _encode_payload(claim)


def _encode_payload(claim: Claim) -> JsonObject:
    match claim:
        case Impact():
            return {
                "leave_id": claim.leave_id,
                "subtype": claim.subtype.value,
                "artifact": encode_ref(claim.artifact),
            }
        case Constraint():
            return {"clause_id": claim.clause_id, "applies_to": encode_ref(claim.applies_to)}
        case CandidateAssessment():
            return {
                "impact_key": _encode_impact_key(claim.impact_key),
                "employee_id": claim.employee_id,
                "verdict": claim.verdict.value,
                "reasons": [reason.value for reason in claim.reasons],
            }
        case SourceConflict():
            spec = predicate(claim.predicate).value_spec
            return {
                "entity": encode_ref(claim.entity),
                "predicate": claim.predicate.value,
                "observations": [
                    {
                        "source": observation.source.value,
                        "value": encode_value(observation.value, spec),
                    }
                    for observation in claim.observations
                ],
                "resolved_value": encode_value(claim.resolved_value, spec),
                "authority_rule": claim.authority_rule.value,
            }
        case Unknown():
            return {
                "subject": encode_ref(claim.subject),
                "required_fact": claim.required_fact.value,
                "reason": claim.reason.value,
            }
        case CoverageAction():
            return {
                "impact_key": _encode_impact_key(claim.impact_key),
                "action": claim.action.value,
                "assignee_ids": list(claim.assignee_ids),
                "rationale": claim.rationale,
            }
        case _:
            assert_never(claim)


def _encode_evidence(evidence: EvidenceRef) -> JsonObject:
    return {
        "source": evidence.source.value,
        "target": encode_ref(evidence.target),
        "field": evidence.field,
    }


def _encode_impact_key(key: ImpactKey) -> JsonObject:
    return {
        "leave_id": key.leave_id,
        "subtype": key.subtype.value,
        "artifact": encode_ref(key.artifact),
    }


# --- Decoding ---------------------------------------------------------------------


def decode_claims(text: str) -> tuple[Claim, ...]:
    """The claims in ``text``, an array as ``encode_claims`` writes it, in the array's order.

    >>> decode_claims("[]")
    ()
    >>> decode_claims('{"type": "impact"}')
    Traceback (most recent call last):
    ...
    ValueError: a claim set is a JSON array, got dict
    """
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(f"a claim set is a JSON array, got {type(data).__name__}")
    items = cast(list[object], data)
    return tuple(decode_claim(as_object(item, "a claim")) for item in items)


_SHARED_FIELDS = ("type", "claim_id", "evidence_refs", "derived_from_claim_ids")
_OWN_FIELDS: Mapping[ClaimType, tuple[str, ...]] = {
    ClaimType.IMPACT: ("leave_id", "subtype", "artifact"),
    ClaimType.CONSTRAINT: ("clause_id", "applies_to"),
    ClaimType.CANDIDATE_ASSESSMENT: ("impact_key", "employee_id", "verdict", "reasons"),
    ClaimType.SOURCE_CONFLICT: (
        "entity",
        "predicate",
        "observations",
        "resolved_value",
        "authority_rule",
    ),
    ClaimType.UNKNOWN: ("subject", "required_fact", "reason"),
    ClaimType.COVERAGE_ACTION: ("impact_key", "action", "assignee_ids", "rationale"),
}


def decode_claim(data: Mapping[str, object]) -> Claim:
    """The claim ``data`` describes.

    ``ValueError`` on an unknown type, a field mismatch, a wrong JSON type, or a
    payload the domain refuses.
    """
    claim_type = ClaimType(string_field(data, "type"))
    expect_fields(data, _SHARED_FIELDS + _OWN_FIELDS[claim_type], f"a {claim_type.value} claim")
    claim_id = ClaimId(string_field(data, "claim_id"))
    evidence_refs = tuple(
        _decode_evidence(as_object(item, "an evidence ref"))
        for item in array_field(data, "evidence_refs")
    )
    derived = tuple(
        ClaimId(string_item(item, "derived_from_claim_ids"))
        for item in array_field(data, "derived_from_claim_ids")
    )
    match claim_type:
        case ClaimType.IMPACT:
            return Impact(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                leave_id=LeaveId(string_field(data, "leave_id")),
                subtype=ImpactSubtype(string_field(data, "subtype")),
                artifact=decode_ref(object_field(data, "artifact")),
            )
        case ClaimType.CONSTRAINT:
            return Constraint(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                clause_id=ClauseId(string_field(data, "clause_id")),
                applies_to=decode_ref(object_field(data, "applies_to")),
            )
        case ClaimType.CANDIDATE_ASSESSMENT:
            return CandidateAssessment(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                impact_key=_decode_impact_key(object_field(data, "impact_key")),
                employee_id=EmployeeId(string_field(data, "employee_id")),
                verdict=Verdict(string_field(data, "verdict")),
                reasons=tuple(
                    AssessmentReason(string_item(item, "reasons"))
                    for item in array_field(data, "reasons")
                ),
            )
        case ClaimType.SOURCE_CONFLICT:
            name = PredicateName(string_field(data, "predicate"))
            spec = predicate(name).value_spec
            return SourceConflict(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                entity=decode_ref(object_field(data, "entity")),
                predicate=name,
                observations=tuple(
                    _decode_observation(as_object(item, "an observation"), spec)
                    for item in array_field(data, "observations")
                ),
                resolved_value=decode_value(object_field(data, "resolved_value"), spec),
                authority_rule=AuthorityRule(string_field(data, "authority_rule")),
            )
        case ClaimType.UNKNOWN:
            return Unknown(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                subject=decode_ref(object_field(data, "subject")),
                required_fact=PredicateName(string_field(data, "required_fact")),
                reason=UnknownReason(string_field(data, "reason")),
            )
        case ClaimType.COVERAGE_ACTION:
            return CoverageAction(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                impact_key=_decode_impact_key(object_field(data, "impact_key")),
                action=CoverageActionKind(string_field(data, "action")),
                assignee_ids=tuple(
                    EmployeeId(string_item(item, "assignee_ids"))
                    for item in array_field(data, "assignee_ids")
                ),
                rationale=optional_string_field(data, "rationale"),
            )
        case _:
            assert_never(claim_type)


def _decode_evidence(data: Mapping[str, object]) -> EvidenceRef:
    expect_fields(data, ("source", "target", "field"), "an evidence ref")
    return EvidenceRef(
        Source(string_field(data, "source")),
        decode_ref(object_field(data, "target")),
        optional_string_field(data, "field"),
    )


def _decode_impact_key(data: Mapping[str, object]) -> ImpactKey:
    expect_fields(data, ("leave_id", "subtype", "artifact"), "an impact key")
    return ImpactKey(
        LeaveId(string_field(data, "leave_id")),
        ImpactSubtype(string_field(data, "subtype")),
        decode_ref(object_field(data, "artifact")),
    )


def _decode_observation(data: Mapping[str, object], spec: ValueSpec) -> Observation:
    expect_fields(data, ("source", "value"), "an observation")
    return Observation(
        Source(string_field(data, "source")), decode_value(object_field(data, "value"), spec)
    )
