"""The materialization record read back from a sealed truth manifest: the generator's own decoder,
for the one reader the truth manifest has before the evaluator arrives — a resume.

The truth manifest has no decoder in ``world`` on purpose: its first consumer is the
evaluator, and a decoder the validator is forbidden to use would be one the import law
could not keep out of its reach. This one lives in the generator, which the validator can
never import, and reads exactly one section — the record of how each model-written text
was accepted — since a resume reconstructs everything else from the seed and the sealed
world spec and needs the record only to re-compose the world it is continuing (the step 14
rulings in DESIGN, "Materialization": after sealing, a restart resumes the named
realization). Strict in the decoders' manner: exactly the declared fields, values through
the same specs a fact's pass, an enumeration by its value; the rest of the file is checked
for its discriminator and otherwise left unread.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from leaveimpact.core.jsonshape import (
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
from leaveimpact.core.values_json import decode_ref, decode_value
from leaveimpact.world.artifacts import TRUTH_MANIFEST
from leaveimpact.world.prose import (
    AssertionMode,
    GuardName,
    MaterializationMetrics,
    MaterializationRecord,
    ModelConfiguration,
    Polarity,
    Proposition,
    ReasonCount,
    Refusal,
    RefusalReason,
    Setting,
    TargetRecord,
)


def decode_materialization(content: bytes | str) -> MaterializationRecord | None:
    """The record the truth manifest ``content`` seals, or ``None`` when no model wrote anything."""
    data = as_object(json.loads(content), "the truth manifest")
    if field_of(data, "artifact") != TRUTH_MANIFEST:
        raise ValueError(f"the truth manifest is sealed as {TRUTH_MANIFEST}")
    record = field_of(data, "materialization")
    if record is None:
        return None
    return _record(as_object(record, "the materialization record"))


def _record(data: Mapping[str, object]) -> MaterializationRecord:
    # The counters joined the record after the first prose worlds were sealed, so their
    # field is the one the decoder allows to be absent; present, it is read whole.
    counted = "metrics" in data
    expect_fields(
        data,
        ("writer", "checker", "prompt_digests", "attempt_cap", "targets")
        + (("metrics",) if counted else ()),
        "the materialization record",
    )
    return MaterializationRecord(
        writer=_model(object_field(data, "writer")),
        checker=_model(object_field(data, "checker")),
        prompt_digests=tuple(_prompt(item) for item in array_field(data, "prompt_digests")),
        attempt_cap=integer_field(data, "attempt_cap"),
        targets=tuple(_target(item) for item in array_field(data, "targets")),
        metrics=_metrics(object_field(data, "metrics")) if counted else None,
    )


def _metrics(data: Mapping[str, object]) -> MaterializationMetrics:
    names = tuple(MaterializationMetrics.__slots__)
    expect_fields(data, names, "the materialization metrics")
    return MaterializationMetrics(**{name: integer_field(data, name) for name in names})


def _model(data: Mapping[str, object]) -> ModelConfiguration:
    expect_fields(data, ("model_id", "settings"), "a model configuration")
    return ModelConfiguration(
        string_field(data, "model_id"),
        tuple(_setting(item) for item in array_field(data, "settings")),
    )


def _setting(item: object) -> Setting:
    data = as_object(item, "a setting")
    expect_fields(data, ("name", "value"), "a setting")
    value = field_of(data, "value")
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError(f"a setting's value is a number or a string, got {value!r}")
    return Setting(string_field(data, "name"), value)


def _prompt(item: object) -> tuple[str, str]:
    data = as_object(item, "a prompt digest")
    expect_fields(data, ("name", "digest"), "a prompt digest")
    return (string_field(data, "name"), string_field(data, "digest"))


def _target(item: object) -> TargetRecord:
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
        refusals=tuple(_refusal(entry) for entry in array_field(data, "refusals")),
        request_digest=string_field(data, "request_digest"),
        accepted_body_digest=string_field(data, "accepted_body_digest"),
        propositions=tuple(_proposition(entry) for entry in array_field(data, "propositions")),
    )


def _refusal(item: object) -> Refusal:
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
        tuple(_reason(entry) for entry in array_field(data, "reasons")) if reasoned else None,
    )


def _reason(item: object) -> ReasonCount:
    data = as_object(item, "a reason count")
    expect_fields(data, ("reason", "count"), "a reason count")
    return (RefusalReason(string_field(data, "reason")), integer_field(data, "count"))


def _proposition(item: object) -> Proposition:
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


__all__ = ["decode_materialization"]
