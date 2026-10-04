"""The parser of a model's fact entries: from what a model put out to a stated fact, or to the
input kept whole beside the reason no fact could be made of it.

A model states facts as a list of entries, each a small JSON object. This module reads one
entry into a ``StatedFact``, and when it cannot, returns a ``RefusedInput`` holding the
entry as canonical JSON text and a reason code, so the classification can be checked from
the export and the unreadable input is never stored as the typed fact that refused it (the
contract step's rulings on a requirement that does not decode and on what an answer
carried). A refused entry never ends a run: it is invalid model output at the level of one
fact, counted by its reason, and a later valid entry for the same statement is read like
any other.

The entry's shape is the one a real model has been shown to fill: the span probe's second
pass (the composer group's fourth point). ``carrier``, ``predicate``, ``subject``,
``value`` and ``quote`` on every entry; for a requirement ``count``, ``skills``, optionally
``employment_type``, and ``target_span``, with ``value`` left empty. How a model is asked
for entries, and under which prompt, is the investigator graph's to decide and to check
again; ``ENTRY_SCHEMA`` is what this parser reads, and ``refused_by`` names the two for a
payload it could not read at all.

Which reason an unreadable entry gets:

- ``undecodable``: the entry is not an object; a field it needs is missing or of the wrong
  JSON type; the predicate is not one a model states; the subject or the value is not an
  id of the kind the predicate takes; a requirement's count or criteria cannot make a
  requirement.
- ``malformed_carrier``: the carrier is not the id of a comment or a section, whatever
  else it is: another record's id, a title, a comment's id written short. Checked first
  among the ids, since a document's id given as the carrier is the commonest unreadable
  entry a model has produced and deserves its own count.
- ``span_not_in_quote``: a requirement with no target span, or one that is not inside its
  quote.

Fields a predicate does not use are not read: a model that fills ``count`` on a skill fact
has still stated the skill fact. An optional field left null or empty is absent: ``skills``
as null is no skill, ``employment_type`` as null or as an empty string is none stated.

An entry holding text that is not valid Unicode (a lone surrogate, which a JSON escape can
spell) is ``undecodable`` whatever else it says: nothing built from it could be written to
an export's bytes. Its raw text is kept with every such character escaped, so the envelope
itself can always be written.

Nothing here needs the run's reads; whether a readable
statement enters the view is admission's (``core.admission``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import cast

from leaveimpact.core.enums import EmploymentType, EntityKind
from leaveimpact.core.ids import SkillId
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes, canonical_json
from leaveimpact.core.model_calls import RefusedBy
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.refs import PREFIX_BY_KIND, EntityRef
from leaveimpact.core.stated import (
    CARRIER_KINDS,
    STATED_PREDICATES,
    Emission,
    FactRefusal,
    RefusedInput,
    StatedFact,
    Unstatable,
)
from leaveimpact.core.values import (
    Criterion,
    EmploymentTypeCriterion,
    FactValue,
    Requirement,
    SkillCriterion,
    ValueKind,
)

PARSER = "fact-entries-1"
"""This parser's identifier, as an export names it beside a payload it refused."""

ENTRY_SCHEMA: JsonObject = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "carrier": {"type": "string"},
                    "predicate": {
                        "type": "string",
                        "enum": [name.value for name in STATED_PREDICATES],
                    },
                    "subject": {"type": "string"},
                    "value": {"type": "string"},
                    "quote": {"type": "string"},
                    "count": {"type": "integer"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                    "employment_type": {
                        "type": "string",
                        "enum": [member.value for member in EmploymentType],
                    },
                    "target_span": {"type": "string"},
                },
                "required": ["carrier", "predicate", "subject", "value", "quote"],
            },
        }
    },
    "required": ["facts"],
}
"""The payload this parser reads: structure only. The descriptions a model is shown beside it
are the prompt's and are not part of what is parsed."""

_KIND_BY_PREFIX: Mapping[str, EntityKind] = {
    prefix: kind for kind, prefix in PREFIX_BY_KIND.items()
}


def refused_by() -> RefusedBy:
    """This parser and the digest of the schema it reads, for a payload it refused whole.

    >>> refused_by().parser
    'fact-entries-1'
    """
    return RefusedBy(PARSER, hashlib.sha256(canonical_bytes(ENTRY_SCHEMA)).hexdigest())


def parse_payload(payload: object) -> tuple[Emission, ...] | None:
    """The entries of ``payload``, each read or refused, in the order stated; ``None`` when
    the payload is not a batch at all (not an object holding a ``facts`` list), which the
    caller records as a malformed batch with the payload as it arrived.

    >>> parse_payload({"facts": []})
    ()
    >>> parse_payload({"fact": []}) is None
    True
    """
    if not isinstance(payload, dict):
        return None
    facts = cast("dict[str, object]", payload).get("facts")
    if not isinstance(facts, list):
        return None
    return tuple(parse_entry(entry) for entry in cast("list[object]", facts))


def parse_entry(entry: object) -> Emission:
    """``entry`` as a stated fact, or as a refused input with the reason. Raises nothing for
    what a model put out.

    >>> parse_entry("Deniz knows Kafka").reason.value
    'undecodable'
    """
    raw = canonical_json(entry)
    try:
        raw.encode("utf-8")
    except UnicodeEncodeError:
        return RefusedInput(
            json.dumps(entry, ensure_ascii=True, separators=(",", ":")),
            FactRefusal.UNDECODABLE,
            "the entry holds text that is not valid Unicode",
        )
    try:
        return _stated(entry)
    except Unstatable as refused:
        return RefusedInput(raw, refused.reason, str(refused))


def _undecodable(detail: str) -> Unstatable:
    return Unstatable(FactRefusal.UNDECODABLE, detail)


def _stated(entry: object) -> StatedFact:
    if not isinstance(entry, dict):
        raise _undecodable(f"an entry is an object, got {type(entry).__name__}")
    fields = cast("dict[str, object]", entry)
    name = _predicate(_text(fields, "predicate"))
    carrier = _carrier(_text(fields, "carrier"))
    row = predicate(name)
    subject = _reference(row.subject, _text(fields, "subject"), "subject")
    quote = _text(fields, "quote")
    if name is PredicateName.REQUIRES:
        span = fields.get("target_span")
        if span is not None and not isinstance(span, str):
            raise _undecodable(f"target_span is text, got {type(span).__name__}")
        return StatedFact(name, subject, _requirement(fields), carrier, quote, span or None)
    value: FactValue = _text(fields, "value")
    if row.value_spec.kind is ValueKind.ENTITY_REF:
        kind = row.value_spec.entity_kind
        assert kind is not None, name
        value = _reference(kind, value, "value")
    elif row.value_spec.kind is ValueKind.SKILL:
        value = SkillId(value)
    return StatedFact(name, subject, value, carrier, quote)


def _text(fields: Mapping[str, object], name: str) -> str:
    value = fields.get(name)
    if not isinstance(value, str):
        raise _undecodable(
            f"{name} is missing" if value is None else f"{name} is text, got {type(value).__name__}"
        )
    return value


def _predicate(value: str) -> PredicateName:
    try:
        return PredicateName(value)
    except ValueError:
        raise _undecodable(f"{value!r} is not a predicate") from None


def _carrier(value: str) -> EntityRef:
    kind = _KIND_BY_PREFIX.get(value.rsplit("_", 1)[0])
    if kind is not None and kind in CARRIER_KINDS:
        try:
            return EntityRef(kind, value)
        except ValueError:
            pass
    raise Unstatable(
        FactRefusal.MALFORMED_CARRIER, f"a carrier is a comment or a section id, got {value!r}"
    )


def _reference(kind: EntityKind, value: str, what: str) -> EntityRef:
    try:
        return EntityRef(kind, value)
    except ValueError as problem:
        raise _undecodable(f"{what}: {problem}") from None


def _requirement(fields: Mapping[str, object]) -> Requirement:
    skills = fields.get("skills")
    if skills is None:
        skills = []
    if not isinstance(skills, list):
        raise _undecodable(f"skills is a list, got {type(skills).__name__}")
    criteria: list[Criterion] = []
    try:
        for skill in cast("list[object]", skills):
            if not isinstance(skill, str):
                raise ValueError(f"a skill is an id, got {type(skill).__name__}")
            criteria.append(SkillCriterion(SkillId(skill)))
        employment = fields.get("employment_type")
        if employment is not None and employment != "":
            if not isinstance(employment, str):
                raise ValueError(f"employment_type is text, got {type(employment).__name__}")
            criteria.append(EmploymentTypeCriterion(EmploymentType(employment)))
        return Requirement(cast("int", fields.get("count")), tuple(criteria))
    except ValueError as problem:
        raise _undecodable(f"requires: {problem}") from None


__all__ = ["ENTRY_SCHEMA", "PARSER", "parse_entry", "parse_payload", "refused_by"]
