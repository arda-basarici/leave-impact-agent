"""Canonical JSON for claims: one encoder, one decoder, the domain constructors as the validation.

A claim set crosses the seam as text — the answer key sealed in a bucket, an agent's
report in the event log — and this module is the single place that knows the shape.
The encoding is canonical so equal claim sets produce equal bytes: fields in declared
order, compact separators, UTF-8 passed through, enum members as their values, dates
as ISO strings, every claim tagged by ``type`` and every fact value by ``kind``.
Decoding builds the domain types through their own constructors and adds nothing of
its own beyond shape: an unknown tag, a missing or surplus field, a wrong JSON type, or
a payload the domain refuses all raise ``ValueError`` from here, and the domain's
invariants are checked once, in the domain (DESIGN, "The vocabulary in code").
Pydantic stays out of ``core``; a schema for the agent's structured output is the
investigator milestone's concern, at its own edge.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
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
from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.ids import ClaimId, ClauseId, EmployeeId, LeaveId
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EntityRef, EvidenceRef, FactValue, Observation

JsonObject = dict[str, object]
"""A JSON object as Python builds it: string keys, values already JSON-ready."""


# --- Encoding ---------------------------------------------------------------------


def encode_claims(claims: Sequence[Claim]) -> str:
    """The canonical JSON text of ``claims``: a JSON array, one object per claim, in order.

    >>> encode_claims(())
    '[]'
    """
    return json.dumps(
        [encode_claim(claim) for claim in claims], ensure_ascii=False, separators=(",", ":")
    )


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
                "artifact": _encode_ref(claim.artifact),
            }
        case Constraint():
            return {"clause_id": claim.clause_id, "applies_to": _encode_ref(claim.applies_to)}
        case CandidateAssessment():
            return {
                "impact_key": _encode_impact_key(claim.impact_key),
                "employee_id": claim.employee_id,
                "verdict": claim.verdict.value,
                "reasons": [reason.value for reason in claim.reasons],
            }
        case SourceConflict():
            return {
                "entity": _encode_ref(claim.entity),
                "predicate": claim.predicate.value,
                "observations": [
                    {"source": observation.source.value, "value": _encode_value(observation.value)}
                    for observation in claim.observations
                ],
                "resolved_value": _encode_value(claim.resolved_value),
                "authority_rule": claim.authority_rule.value,
            }
        case Unknown():
            return {
                "subject": _encode_ref(claim.subject),
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


def _encode_ref(ref: EntityRef) -> JsonObject:
    return {"kind": ref.kind.value, "id": ref.id}


def _encode_evidence(evidence: EvidenceRef) -> JsonObject:
    return {
        "source": evidence.source.value,
        "target": _encode_ref(evidence.target),
        "field": evidence.field,
    }


def _encode_impact_key(key: ImpactKey) -> JsonObject:
    return {
        "leave_id": key.leave_id,
        "subtype": key.subtype.value,
        "artifact": _encode_ref(key.artifact),
    }


def _encode_value(value: FactValue) -> JsonObject:
    match value:
        case EntityRef():
            return {"kind": "entity_ref", "value": _encode_ref(value)}
        case date():
            return {"kind": "date", "value": value.isoformat()}
        case str():
            return {"kind": "text", "value": value}
        case _:
            assert_never(value)


# --- Decoding ---------------------------------------------------------------------


def decode_claims(text: str) -> tuple[Claim, ...]:
    """The claims in ``text``, an array as ``encode_claims`` writes it.

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
    return tuple(decode_claim(_object(item, "a claim")) for item in items)


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
    claim_type = ClaimType(_string(data, "type"))
    _expect_fields(data, _SHARED_FIELDS + _OWN_FIELDS[claim_type], f"a {claim_type.value} claim")
    claim_id = ClaimId(_string(data, "claim_id"))
    evidence_refs = tuple(
        _decode_evidence(_object(item, "an evidence ref")) for item in _array(data, "evidence_refs")
    )
    derived = tuple(
        ClaimId(_string_item(item, "derived_from_claim_ids"))
        for item in _array(data, "derived_from_claim_ids")
    )
    match claim_type:
        case ClaimType.IMPACT:
            return Impact(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                leave_id=LeaveId(_string(data, "leave_id")),
                subtype=ImpactSubtype(_string(data, "subtype")),
                artifact=_decode_ref(_object(data["artifact"], "artifact")),
            )
        case ClaimType.CONSTRAINT:
            return Constraint(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                clause_id=ClauseId(_string(data, "clause_id")),
                applies_to=_decode_ref(_object(data["applies_to"], "applies_to")),
            )
        case ClaimType.CANDIDATE_ASSESSMENT:
            return CandidateAssessment(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                impact_key=_decode_impact_key(_object(data["impact_key"], "impact_key")),
                employee_id=EmployeeId(_string(data, "employee_id")),
                verdict=Verdict(_string(data, "verdict")),
                reasons=tuple(
                    AssessmentReason(_string_item(item, "reasons"))
                    for item in _array(data, "reasons")
                ),
            )
        case ClaimType.SOURCE_CONFLICT:
            return SourceConflict(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                entity=_decode_ref(_object(data["entity"], "entity")),
                predicate=PredicateName(_string(data, "predicate")),
                observations=tuple(
                    _decode_observation(_object(item, "an observation"))
                    for item in _array(data, "observations")
                ),
                resolved_value=_decode_value(_object(data["resolved_value"], "resolved_value")),
                authority_rule=AuthorityRule(_string(data, "authority_rule")),
            )
        case ClaimType.UNKNOWN:
            return Unknown(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                subject=_decode_ref(_object(data["subject"], "subject")),
                required_fact=PredicateName(_string(data, "required_fact")),
                reason=UnknownReason(_string(data, "reason")),
            )
        case ClaimType.COVERAGE_ACTION:
            return CoverageAction(
                claim_id=claim_id,
                evidence_refs=evidence_refs,
                derived_from_claim_ids=derived,
                impact_key=_decode_impact_key(_object(data["impact_key"], "impact_key")),
                action=CoverageActionKind(_string(data, "action")),
                assignee_ids=tuple(
                    EmployeeId(_string_item(item, "assignee_ids"))
                    for item in _array(data, "assignee_ids")
                ),
                rationale=_optional_string(data, "rationale"),
            )
        case _:
            assert_never(claim_type)


def _decode_ref(data: Mapping[str, object]) -> EntityRef:
    _expect_fields(data, ("kind", "id"), "an entity ref")
    return EntityRef(EntityKind(_string(data, "kind")), _string(data, "id"))


def _decode_evidence(data: Mapping[str, object]) -> EvidenceRef:
    _expect_fields(data, ("source", "target", "field"), "an evidence ref")
    return EvidenceRef(
        Source(_string(data, "source")),
        _decode_ref(_object(data["target"], "target")),
        _optional_string(data, "field"),
    )


def _decode_impact_key(data: Mapping[str, object]) -> ImpactKey:
    _expect_fields(data, ("leave_id", "subtype", "artifact"), "an impact key")
    return ImpactKey(
        LeaveId(_string(data, "leave_id")),
        ImpactSubtype(_string(data, "subtype")),
        _decode_ref(_object(data["artifact"], "artifact")),
    )


def _decode_observation(data: Mapping[str, object]) -> Observation:
    _expect_fields(data, ("source", "value"), "an observation")
    return Observation(
        Source(_string(data, "source")), _decode_value(_object(data["value"], "value"))
    )


def _decode_value(data: Mapping[str, object]) -> FactValue:
    _expect_fields(data, ("kind", "value"), "a fact value")
    kind = _string(data, "kind")
    if kind == "entity_ref":
        return _decode_ref(_object(data["value"], "an entity_ref value"))
    if kind == "date":
        return date.fromisoformat(_string(data, "value"))
    if kind == "text":
        return _string(data, "value")
    raise ValueError(f"a fact value is an entity_ref, a date or text, got kind {kind!r}")


# --- Shape helpers: the JSON type of each field, nothing about its meaning ------------


def _expect_fields(data: Mapping[str, object], fields: tuple[str, ...], what: str) -> None:
    expected = set(fields)
    if set(data) != expected:
        missing = sorted(expected - set(data))
        surplus = sorted(set(data) - expected)
        raise ValueError(
            f"{what} has fields {sorted(expected)}; missing {missing}, surplus {surplus}"
        )


def _object(value: object, what: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{what} is a JSON object, got {type(value).__name__}")
    return cast(dict[str, object], value)


def _string(data: Mapping[str, object], key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} is a string, got {type(value).__name__}")
    return value


def _optional_string(data: Mapping[str, object], key: str) -> str | None:
    value = data[key]
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} is a string or null, got {type(value).__name__}")
    return value


def _string_item(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"an item of {key} is a string, got {type(value).__name__}")
    return value


def _array(data: Mapping[str, object], key: str) -> list[object]:
    value = data[key]
    if not isinstance(value, list):
        raise ValueError(f"{key} is a JSON array, got {type(value).__name__}")
    return cast(list[object], value)
