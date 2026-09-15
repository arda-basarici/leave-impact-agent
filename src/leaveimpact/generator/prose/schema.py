"""The checker's tool: its schema generated from the predicate registry, and the parse of what
the model filled into propositions.

The extraction check hands a second model family the text and a tool to fill, and the tool's
shape is the registry's: one entry per proposition with the subject as an entity id from the
brief's namespace or the word ``unknown``, a predicate from the registry, a value in the form
the predicate's spec declares, the polarity and the assertion mode the text carries — plus
``other_claims``, the provisional bucket for an asserted benchmark-relevant statement the
schema cannot express (the step 14 rulings in DESIGN, "Materialization"). Generated and not
hand-written, so a predicate added to the registry reaches the checker with no edit here.

The parse is strict and belongs to the generator because the generator wrote the schema: an
entry missing a field, naming a predicate the registry lacks, or carrying a polarity or
mode outside the enums is ``ExtractionMalformed`` — the checker's protocol failure, retried
and then fatal, never a writer's refusal. A value the predicate's spec refuses is not: the
schema fixes the tool's shape and only the message describes each value's form, so a
value in the wrong form is the checker misreading the text — the second measurement world
read "let me take a look" as the author owning the ticket, subject and value reversed,
and three retries at temperature zero repeated it (2026-09-14). Such a proposition is
kept as *untyped*, named by its predicate only, and the extraction guard refuses the
attempt so the writer is resampled. A subject id outside the brief's namespace is an
unknown subject by definition, since the namespace is the whole list the checker was
given. Values pass through the same specs a fact's do, so no second parser exists.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from leaveimpact.core.enums import EmploymentType
from leaveimpact.core.ids import skill_id
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    field_of,
    integer_field,
    string_item,
)
from leaveimpact.core.predicates import ROWS, Predicate, PredicateName, predicate
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.values import (
    EmploymentTypeCriterion,
    FactValue,
    Requirement,
    SkillCriterion,
    ValueKind,
    ValueSpec,
)
from leaveimpact.core.worldtime import DateSpan, InstantSpan
from leaveimpact.world.prose import CARRIER_KINDS, AssertionMode, Namespace, Polarity, Proposition

TOOL_NAME = "record_propositions"
UNKNOWN_SUBJECT = "unknown"


class ExtractionMalformed(Exception):
    """The checker's tool input is not what the schema asks: a protocol failure of the checker."""


@dataclass(frozen=True, slots=True)
class Extraction:
    """What the checker read: the propositions, how many named a subject outside the list, the
    claims it could not express, and the predicates of the propositions it could not type
    (a value in the wrong form — the checker's misreading, never the text's content)."""

    propositions: tuple[Proposition, ...]
    other_claims: tuple[str, ...]
    untyped: tuple[PredicateName, ...] = ()
    canonicalized: int = 0
    """How many propositions arrived with subject and value reversed and were put the
    registry's way round — the checker's normalization, counted as a signal of its reading."""

    @property
    def unknown_subjects(self) -> int:
        return sum(1 for read in self.propositions if read.subject is None)


def tool_schema() -> JsonObject:
    """The JSON schema of the tool's input, generated from the registry's predicates."""
    return {
        "type": "object",
        "properties": {
            "propositions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subject": {
                            "type": "string",
                            "description": (
                                "The subject's id from the entity list, or the word unknown"
                            ),
                        },
                        "predicate": {
                            "type": "string",
                            "enum": [row.name.value for row in ROWS],
                        },
                        "value": {
                            "description": "The value in the form the predicate takes",
                        },
                        "polarity": {"type": "string", "enum": [p.value for p in Polarity]},
                        "mode": {"type": "string", "enum": [m.value for m in AssertionMode]},
                    },
                    "required": ["subject", "predicate", "value", "polarity", "mode"],
                },
            },
            "other_claims": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["propositions", "other_claims"],
    }


def value_forms() -> tuple[str, ...]:
    """One line per predicate saying what value form it takes, for the checker's message."""
    lines: list[str] = []
    for row in ROWS:
        lines.append(
            f"- {row.name.value}: the subject is the {row.subject.value.replace('_', ' ')}; "
            f"the value is {_form(row.value_spec)}"
        )
    return tuple(lines)


def _form(spec: ValueSpec) -> str:
    match spec.kind:
        case ValueKind.ENTITY_REF:
            assert spec.entity_kind is not None
            return f"the id of {spec.entity_kind.value} from the entity list"
        case ValueKind.SKILL:
            return "the skill's id from the entity list"
        case ValueKind.DATE:
            return "a date as YYYY-MM-DD"
        case ValueKind.DATE_SPAN:
            return 'an object {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}'
        case ValueKind.INSTANT_SPAN:
            return 'an object {"start": ISO-8601 instant, "end": ISO-8601 instant}'
        case ValueKind.ENUM:
            assert spec.vocabulary is not None
            return "one of " + ", ".join(member.value for member in spec.vocabulary)
        case ValueKind.TEXT:
            return "free text"
        case ValueKind.REQUIREMENT:
            return (
                'an object {"count": integer, "skills": [skill ids], '
                '"employment_type": "employee" | "contractor" | null}'
            )


def parse_extraction(filled: JsonObject, namespace: Namespace, target: EntityRef) -> Extraction:
    """The propositions and other claims in the checker's tool input, or ``ExtractionMalformed``.

    ``target`` is the text's own carrier — the comment or the section being checked. A
    predicate whose subject is a carrier (a clause's requirement, the person a section
    names) is about the text itself, which a text never names and the entity list never
    holds; its subject is bound here to the target when the kinds agree, and left
    unknown when they do not — a comment cannot state a requirement of itself (the
    step 15 rulings). The checker still reads the relation, value, polarity and mode;
    only the subject a model could never extract is supplied by construction.
    """
    try:
        entries = array_field(filled, "propositions")
        others = [
            string_item(claim, "other_claims") for claim in array_field(filled, "other_claims")
        ]
    except ValueError as problem:
        raise ExtractionMalformed(f"the tool input: {problem}") from None
    known = {(form.kind, form.id) for form in namespace.forms}
    propositions: list[Proposition] = []
    untyped: list[PredicateName] = []
    canonicalized = 0
    for entry in entries:
        read, swapped = _proposition(entry, known, target)
        canonicalized += swapped
        match read:
            case Proposition():
                propositions.append(read)
            case PredicateName():
                untyped.append(read)
    return Extraction(tuple(propositions), tuple(others), tuple(untyped), canonicalized)


def _proposition(
    entry: object, known: set[tuple[str, str]], target: EntityRef
) -> tuple[Proposition | PredicateName, bool]:
    """The entry as a proposition, or its predicate alone when its value could not be typed;
    and whether its entity pair arrived reversed."""
    try:
        item = as_object(entry, "a proposition")
        fields = {
            key: field_of(item, key)
            for key in ("subject", "predicate", "value", "polarity", "mode")
        }
        name = PredicateName(_string(fields["predicate"]))
        polarity = Polarity(_string(fields["polarity"]))
        mode = AssertionMode(_string(fields["mode"]))
        subject_id = _string(fields["subject"])
    except ValueError as problem:
        raise ExtractionMalformed(f"a proposition: {problem}") from None
    row = predicate(name)
    subject_id, raw_value, swapped = _canonical_pair(row, subject_id, fields["value"], known)
    subject: EntityRef | None = None
    if row.subject in CARRIER_KINDS:
        subject = target if target.kind is row.subject else None
    elif subject_id != UNKNOWN_SUBJECT and (row.subject.value, subject_id) in known:
        subject = EntityRef(row.subject, subject_id)
    try:
        value = _value(raw_value, row.value_spec)
        return Proposition(subject, name, value, polarity, mode), swapped
    except ValueError:
        return name, swapped


def _canonical_pair(
    row: Predicate, subject_id: str, raw_value: object, known: set[tuple[str, str]]
) -> tuple[str, object, bool]:
    """The (subject, value) pair with a reversed entity pair put the registry's way round,
    and whether it was.

    The third measurement world's checker wrote ownership as the person owning the ticket
    — subject and value swapped — in three of three samples (2026-09-14). When the value
    is an entity, the subject given is a listed entity of the value's kind and the value
    given is a listed entity of the subject's kind, the pair is unambiguous and the
    proposition's content is the same; anything short of that is left for the untyped
    rule, never guessed.
    """
    spec = row.value_spec
    if spec.kind is not ValueKind.ENTITY_REF or not isinstance(raw_value, str):
        return subject_id, raw_value, False
    assert spec.entity_kind is not None
    reversed_pair = (
        (spec.entity_kind.value, subject_id) in known
        and (row.subject.value, raw_value) in known
        and (row.subject.value, subject_id) not in known
    )
    return (raw_value, subject_id, True) if reversed_pair else (subject_id, raw_value, False)


def _value(raw: object, spec: ValueSpec) -> FactValue:
    match spec.kind:
        case ValueKind.ENTITY_REF:
            assert spec.entity_kind is not None
            return EntityRef(spec.entity_kind, _string(raw))
        case ValueKind.SKILL:
            return skill_id(_string(raw))
        case ValueKind.DATE:
            return date.fromisoformat(_string(raw))
        case ValueKind.ENUM | ValueKind.TEXT:
            return _string(raw)
        case ValueKind.DATE_SPAN:
            span = _object(raw)
            return DateSpan(
                date.fromisoformat(_string(span.get("start"))),
                date.fromisoformat(_string(span.get("end"))),
            )
        case ValueKind.INSTANT_SPAN:
            span = _object(raw)
            return InstantSpan(
                datetime.fromisoformat(_string(span.get("start"))),
                datetime.fromisoformat(_string(span.get("end"))),
            )
        case ValueKind.REQUIREMENT:
            return _requirement(_object(raw))


def _requirement(raw: Mapping[str, object]) -> Requirement:
    count = integer_field(raw, "count")
    skills = array_field(raw, "skills") if "skills" in raw else []
    criteria: list[SkillCriterion | EmploymentTypeCriterion] = [
        SkillCriterion(skill_id(string_item(skill, "skills"))) for skill in skills
    ]
    employment = raw.get("employment_type")
    if employment is not None:
        criteria.append(EmploymentTypeCriterion(EmploymentType(_string(employment))))
    return Requirement(count, tuple(criteria))


def _string(raw: object) -> str:
    if not isinstance(raw, str):
        raise ValueError(f"expected a string, got {type(raw).__name__}")
    return raw


def _object(raw: object) -> Mapping[str, object]:
    return as_object(raw, "a value")


__all__ = [
    "TOOL_NAME",
    "UNKNOWN_SUBJECT",
    "Extraction",
    "ExtractionMalformed",
    "parse_extraction",
    "tool_schema",
    "value_forms",
]
