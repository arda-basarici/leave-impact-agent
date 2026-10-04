"""Canonical JSON for stated facts and their statuses: one encoder and one decoder each, the
domain constructors as the validation.

A run's export holds what a model stated and what became of each statement, and the
evaluator reads it back to replay the run's view, so the shapes are here once, beside the
claims codec and under the same byte rule (``jsonshape``): fields in a fixed order, enum
members as their values, a fact's value tagged by its predicate's value kind.

Absent is kept apart from empty. A stated fact has a ``target_span`` field exactly when it
is a requirement, a placement an ``artifact`` exactly when placed and an ``among`` exactly
when ambiguous; no field is written as null or as an empty list to fill a shape, and the
decoder refuses a field its tag does not call for. A status is tagged, so an emission that
was refused as input can never be read back as a fact: its raw text sits under its own
tag, as the string the model's entry was kept as.

This codec reads back what a harness stored. It is not the parser of a model's output: an
entry a model wrote is read by the harness, which builds the fact through its constructor
and maps whatever stops it to a refused input with a reason. A stored fact that lacks a
field is a broken export and raises here as shape, with no reason code.

Decoding adds nothing beyond shape. An unknown tag, a missing or surplus field or a wrong
JSON type raises ``ValueError`` here, and a value the domain refuses raises from its
constructor (``Unstatable`` is a ``ValueError``).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import assert_never

from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    expect_fields,
    object_field,
    string_field,
)
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.stated import (
    Admission,
    Admitted,
    Emission,
    FactRefusal,
    PlacementState,
    Refused,
    RefusedInput,
    SpanPlacement,
    StatedFact,
)
from leaveimpact.core.stated_view import Excluded, Exclusion
from leaveimpact.core.values_json import decode_ref, decode_value, encode_ref, encode_value

_FACT_FIELDS = ("predicate", "subject", "value", "carrier", "quote")

# --- The stated fact ------------------------------------------------------------------------


def encode_stated_fact(stated: StatedFact) -> JsonObject:
    """The JSON object of a stated fact; ``target_span`` is written only for a requirement.

    >>> from leaveimpact.core.ids import comment_id, employee_id
    >>> from leaveimpact.core.refs import comment_ref, employee_ref
    >>> encode_stated_fact(StatedFact(PredicateName.HAS_SKILL, employee_ref(employee_id(23)),
    ...     "kafka", comment_ref(comment_id(5)), "I ran Kafka"))["value"]
    {'kind': 'skill', 'value': 'kafka'}
    """
    encoded: JsonObject = {
        "predicate": stated.predicate.value,
        "subject": encode_ref(stated.subject),
        "value": encode_value(stated.value, predicate(stated.predicate).value_spec),
        "carrier": encode_ref(stated.carrier),
        "quote": stated.quote,
    }
    if stated.target_span is not None:
        encoded["target_span"] = stated.target_span
    return encoded


def decode_stated_fact(data: Mapping[str, object]) -> StatedFact:
    """The stated fact ``data`` describes, built through its constructor."""
    name = PredicateName(string_field(data, "predicate"))
    requirement = name is PredicateName.REQUIRES
    expect_fields(
        data, (*_FACT_FIELDS, "target_span") if requirement else _FACT_FIELDS, "a stated fact"
    )
    return StatedFact(
        predicate=name,
        subject=decode_ref(object_field(data, "subject")),
        value=decode_value(object_field(data, "value"), predicate(name).value_spec),
        carrier=decode_ref(object_field(data, "carrier")),
        quote=string_field(data, "quote"),
        target_span=string_field(data, "target_span") if requirement else None,
    )


# --- Emission -------------------------------------------------------------------------------

_STATED = "stated"
_REFUSED_INPUT = "refused_input"


def encode_emission(emission: Emission) -> JsonObject:
    """One entry of a model's output: a statement, or the input no statement was made of."""
    match emission:
        case StatedFact():
            return {"emission": _STATED, "fact": encode_stated_fact(emission)}
        case RefusedInput():
            return {
                "emission": _REFUSED_INPUT,
                "raw": emission.raw,
                "reason": emission.reason.value,
                "detail": emission.detail,
            }
        case _:
            assert_never(emission)


def decode_emission(data: Mapping[str, object]) -> Emission:
    tag = string_field(data, "emission")
    if tag == _STATED:
        expect_fields(data, ("emission", "fact"), "a stated emission")
        return decode_stated_fact(object_field(data, "fact"))
    if tag == _REFUSED_INPUT:
        expect_fields(data, ("emission", "raw", "reason", "detail"), "a refused input")
        return RefusedInput(
            raw=string_field(data, "raw"),
            reason=FactRefusal(string_field(data, "reason")),
            detail=string_field(data, "detail"),
        )
    raise ValueError(f"an emission is {_STATED} or {_REFUSED_INPUT}, got {tag!r}")


# --- Admission ------------------------------------------------------------------------------

_ADMITTED = "admitted"
_REFUSED = "refused"


def encode_admission(admission: Admission) -> JsonObject:
    """Whether a stated fact entered the view, the fact whole in both cases."""
    match admission:
        case Admitted():
            return {"admission": _ADMITTED, "fact": encode_stated_fact(admission.fact)}
        case Refused():
            return {
                "admission": _REFUSED,
                "fact": encode_stated_fact(admission.fact),
                "reason": admission.reason.value,
                "detail": admission.detail,
            }
        case _:
            assert_never(admission)


def decode_admission(data: Mapping[str, object]) -> Admission:
    tag = string_field(data, "admission")
    if tag == _ADMITTED:
        expect_fields(data, ("admission", "fact"), "an admitted fact")
        return Admitted(decode_stated_fact(object_field(data, "fact")))
    if tag == _REFUSED:
        expect_fields(data, ("admission", "fact", "reason", "detail"), "a refused fact")
        return Refused(
            fact=decode_stated_fact(object_field(data, "fact")),
            reason=FactRefusal(string_field(data, "reason")),
            detail=string_field(data, "detail"),
        )
    raise ValueError(f"an admission is {_ADMITTED} or {_REFUSED}, got {tag!r}")


# --- Placement ------------------------------------------------------------------------------


def encode_placement(placement: SpanPlacement) -> JsonObject:
    """A span's binding: ``artifact`` only when placed, ``among`` only when ambiguous.

    >>> encode_placement(SpanPlacement(PlacementState.UNPLACED))
    {'state': 'unplaced'}
    """
    encoded: JsonObject = {"state": placement.state.value}
    if placement.artifact is not None:
        encoded["artifact"] = encode_ref(placement.artifact)
    if placement.among:
        encoded["among"] = [encode_ref(artifact) for artifact in placement.among]
    return encoded


def decode_placement(data: Mapping[str, object]) -> SpanPlacement:
    state = PlacementState(string_field(data, "state"))
    match state:
        case PlacementState.PLACED:
            expect_fields(data, ("state", "artifact"), "a placed span")
            return SpanPlacement(state, artifact=decode_ref(object_field(data, "artifact")))
        case PlacementState.UNPLACED:
            expect_fields(data, ("state",), "an unplaced span")
            return SpanPlacement(state)
        case PlacementState.AMBIGUOUS:
            expect_fields(data, ("state", "among"), "an ambiguous span")
            return SpanPlacement(
                state,
                among=tuple(
                    decode_ref(as_object(item, "an artifact of among"))
                    for item in array_field(data, "among")
                ),
            )


# --- Exclusion ------------------------------------------------------------------------------


def encode_excluded(excluded: Excluded) -> JsonObject:
    """An admitted statement the view left out, with the reason."""
    return {"fact": encode_stated_fact(excluded.fact), "reason": excluded.reason.value}


def decode_excluded(data: Mapping[str, object]) -> Excluded:
    expect_fields(data, ("fact", "reason"), "an excluded fact")
    return Excluded(
        decode_stated_fact(object_field(data, "fact")), Exclusion(string_field(data, "reason"))
    )


__all__ = [
    "decode_admission",
    "decode_emission",
    "decode_excluded",
    "decode_placement",
    "decode_stated_fact",
    "encode_admission",
    "encode_emission",
    "encode_excluded",
    "encode_placement",
    "encode_stated_fact",
]
