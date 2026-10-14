"""The target record's codec, both directions: how one brief's acceptance is written into
the truth manifest and read back from it, and the same shape the prose checkpoint keeps
beside each accepted body.

It stands apart from the truth decoder on purpose. Reading the answer key is one module
path, importable by the modules named for it (the import law), and the prose checkpoint
reads records of its own making and never a truth object; giving it the truth decoder would
hand a generator module the key's reader for the sake of six fields. The encoder left the
artifacts module for the same symmetry, so the two halves of one shape live in one place
and a field added to the record is added once. The materialization record that holds these
records stays with the manifest's own codecs.

A refusal sealed before reasons were recorded has no ``reasons`` field, and absent decodes
as unavailable, never as no reasons, so the bytes of records sealed before re-encode to
what they were (the sealed-record lesson).
"""

from __future__ import annotations

from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    expect_fields,
    field_of,
    integer_field,
    object_field,
    string_field,
)
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.values_json import decode_ref, decode_value, encode_ref, encode_value
from leaveimpact.world.prose import (
    AssertionMode,
    GuardName,
    Polarity,
    Proposition,
    ReasonCount,
    Refusal,
    RefusalReason,
    TargetRecord,
)

__all__ = ["decode_target_record", "encode_proposition", "encode_target_record"]


def encode_target_record(target: TargetRecord) -> JsonObject:
    """One target's record as the truth manifest carries it."""
    return {
        "target_id": target.target_id,
        "attempts": target.attempts,
        "refusals": [_encode_refusal(refusal) for refusal in target.refusals],
        "request_digest": target.request_digest,
        "accepted_body_digest": target.accepted_body_digest,
        "propositions": [encode_proposition(read) for read in target.propositions],
    }


def encode_proposition(read: Proposition) -> JsonObject:
    """A checker's reading of a text, its value tagged by the predicate's spec like a fact's."""
    return {
        "subject": None if read.subject is None else encode_ref(read.subject),
        "predicate": read.predicate.value,
        "value": encode_value(read.value, predicate(read.predicate).value_spec),
        "polarity": read.polarity.value,
        "assertion_mode": read.assertion_mode.value,
    }


def decode_target_record(item: object) -> TargetRecord:
    """The inverse of ``encode_target_record``, refusing a missing or malformed field by name."""
    data = as_object(item, "a target record")
    expect_fields(
        data,
        (
            "target_id",
            "attempts",
            "refusals",
            "request_digest",
            "accepted_body_digest",
            "propositions",
        ),
        "a target record",
    )
    return TargetRecord(
        target_id=string_field(data, "target_id"),
        attempts=integer_field(data, "attempts"),
        refusals=tuple(_decode_refusal(entry) for entry in array_field(data, "refusals")),
        request_digest=string_field(data, "request_digest"),
        accepted_body_digest=string_field(data, "accepted_body_digest"),
        propositions=tuple(
            _decode_proposition(entry) for entry in array_field(data, "propositions")
        ),
    )


def _encode_refusal(refusal: Refusal) -> JsonObject:
    encoded: JsonObject = {
        "attempt": refusal.attempt,
        "guard": refusal.guard.value,
        "count": refusal.count,
    }
    # Absent, never empty, on a refusal recorded before reasons were: the decoder reads the
    # difference back, and the bytes of records sealed before stay what they were.
    if refusal.reasons is not None:
        encoded["reasons"] = [
            {"reason": reason.value, "count": count} for reason, count in refusal.reasons
        ]
    return encoded


def _decode_refusal(item: object) -> Refusal:
    data = as_object(item, "a refusal")
    # Reasons joined the refusal after the measurement world was sealed; their field is the
    # one allowed to be absent, and absent decodes as unavailable, never as no reasons.
    reasoned = "reasons" in data
    expect_fields(
        data, ("attempt", "guard", "count") + (("reasons",) if reasoned else ()), "a refusal"
    )
    return Refusal(
        integer_field(data, "attempt"),
        GuardName(string_field(data, "guard")),
        integer_field(data, "count"),
        tuple(_decode_reason(entry) for entry in array_field(data, "reasons"))
        if reasoned
        else None,
    )


def _decode_reason(item: object) -> ReasonCount:
    data = as_object(item, "a reason count")
    expect_fields(data, ("reason", "count"), "a reason count")
    return (RefusalReason(string_field(data, "reason")), integer_field(data, "count"))


def _decode_proposition(item: object) -> Proposition:
    data = as_object(item, "a proposition")
    expect_fields(
        data, ("subject", "predicate", "value", "polarity", "assertion_mode"), "a proposition"
    )
    name = PredicateName(string_field(data, "predicate"))
    raw_subject = field_of(data, "subject")
    subject: EntityRef | None = None
    if raw_subject is not None:
        subject = decode_ref(as_object(raw_subject, "a proposition's subject"))
    return Proposition(
        subject,
        name,
        decode_value(object_field(data, "value"), predicate(name).value_spec),
        Polarity(string_field(data, "polarity")),
        AssertionMode(string_field(data, "assertion_mode")),
    )
