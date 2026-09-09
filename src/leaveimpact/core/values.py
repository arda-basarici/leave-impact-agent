"""What a fact can say: the value union, the requirement a clause states, and the value spec a
predicate declares.

A fact pairs a subject with a predicate and a value, and the value's shape is the
predicate's to declare, not the fact's to choose: the registry row for ``due_on`` says
"a date", the row for ``requires`` says "a requirement", and a fact validates against
that spec at construction, so a skills field cannot carry a sentence and a clause
cannot carry a bare number (DESIGN, "The rules in code"). The spec is one declaration
in one place — the same row also serializes as the value's JSON tag — instead of a
Python union here, a tag table in the codec and an ``isinstance`` in every rule.

Eight kinds cover the first golden set. An *entity reference* of a declared kind (a
team, a component, an employee). *Text* for values an outside namespace owns (a city
name), the one kind with no vocabulary to check. An *enum vocabulary* ``core`` owns
(a work item's status, an employment type), checked by membership. A *skill*, a slug
the ids module shapes and only the world generator enumerates — a vocabulary term,
never an entity, since nothing in the world says anything about a skill. A *date*
(a due day), an inclusive *date span* (a leave), a half-open *instant span* (a
meeting's time). And a *requirement*, what a procedure clause asks of the people who
cover a need: a minimum count and typed criteria, where the criteria assess a
candidate and the count judges a plan, never the reverse (the viability rule reads
the criteria; the plan check reads the count). The criteria are a small tagged union
so that a sealed answer key survives a later grade or country criterion: the wire
shape is stable from the first world, the Python union grows a member when a scenario
class plants one.

``Observation`` lives here rather than with the references because it is the pairing
a conflict compares: one source's value, typed, never text flattened for convenience.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from leaveimpact.core.enums import EmploymentType, EntityKind, Source
from leaveimpact.core.ids import SkillId, skill_id
from leaveimpact.core.refs import EntityRef, with_article
from leaveimpact.core.worldtime import DateSpan, InstantSpan

# --- The requirement a clause states -------------------------------------------------


@dataclass(frozen=True, slots=True)
class SkillCriterion:
    """A person satisfies it by holding the skill; failing it reads as the ``skill`` reason."""

    skill: SkillId

    def __post_init__(self) -> None:
        skill_id(self.skill)


@dataclass(frozen=True, slots=True)
class EmploymentTypeCriterion:
    """A policy-scoped criterion — "an employee, not a contractor"; failing it is a
    ``hard_rule``."""

    employment_type: EmploymentType


Criterion = SkillCriterion | EmploymentTypeCriterion
"""What a requirement asks of each person. Grade and country join when a clause plants them."""


def criterion_order(criterion: Criterion) -> tuple[str, str]:
    """The canonical position of a criterion: by kind tag, then by value."""
    match criterion:
        case SkillCriterion():
            return ("skill", criterion.skill)
        case EmploymentTypeCriterion():
            return ("employment_type", criterion.employment_type.value)


@dataclass(frozen=True, slots=True)
class Requirement:
    """What a clause requires of coverage: at least ``count`` people, each meeting every criterion.

    ``count`` is a minimum — "two engineers must attend" is satisfied by three — and it
    never touches an individual's viability: one viable person against a two-person
    clause is a viable candidate and an invalid plan. Criteria are conjunctive, held in
    canonical order, each given once; an empty tuple is a clause about number alone.

    >>> Requirement(2, (SkillCriterion(SkillId("kafka")),)).count
    2
    >>> Requirement(0, ())
    Traceback (most recent call last):
    ...
    ValueError: a requirement asks for at least one person, got count 0
    """

    count: int
    criteria: tuple[Criterion, ...]

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError(f"a requirement asks for at least one person, got count {self.count}")
        if len(set(self.criteria)) != len(self.criteria):
            raise ValueError("a requirement states each criterion once")
        # Canonical order is the one write a frozen dataclass allows itself, so equal
        # requirements are equal in memory and in bytes (the step-3 ruling on repeated fields).
        object.__setattr__(self, "criteria", tuple(sorted(self.criteria, key=criterion_order)))


# --- The value union and the observation -----------------------------------------------

FactValue = EntityRef | str | date | DateSpan | InstantSpan | Requirement
"""What a fact can say about its subject. Which member a given predicate admits is the
registry row's ``value_spec``; the union only bounds the type."""


@dataclass(frozen=True, slots=True)
class Observation:
    """One source's value for a fact — what a conflict compares and the authority rule ranks."""

    source: Source
    value: FactValue


# --- The spec a predicate declares ---------------------------------------------------


class ValueKind(StrEnum):
    """The shape of a predicate's value; a member is the value's JSON tag."""

    ENTITY_REF = "entity_ref"
    TEXT = "text"
    ENUM = "enum"
    SKILL = "skill"
    DATE = "date"
    DATE_SPAN = "date_span"
    INSTANT_SPAN = "instant_span"
    REQUIREMENT = "requirement"


@dataclass(frozen=True, slots=True)
class ValueSpec:
    """A predicate's declaration of its value: the kind, and the kind's parameter if it has one.

    ``entity_kind`` accompanies exactly the entity-reference kind and ``vocabulary``
    exactly the enum kind; the other kinds carry nothing. Build one through
    ``entity_value`` / ``enum_value`` or the module constants rather than by hand.

    >>> ValueSpec(ValueKind.DATE, entity_kind=EntityKind.TEAM)
    Traceback (most recent call last):
    ...
    ValueError: a date value carries no entity kind
    """

    kind: ValueKind
    entity_kind: EntityKind | None = None
    vocabulary: type[StrEnum] | None = None

    def __post_init__(self) -> None:
        kind = with_article(self.kind.value)
        wants_kind = self.kind is ValueKind.ENTITY_REF
        if (self.entity_kind is not None) != wants_kind:
            raise ValueError(
                "an entity_ref value names its entity kind"
                if wants_kind
                else f"{kind} value carries no entity kind"
            )
        wants_vocabulary = self.kind is ValueKind.ENUM
        if (self.vocabulary is not None) != wants_vocabulary:
            raise ValueError(
                "an enum value names its vocabulary"
                if wants_vocabulary
                else f"{kind} value carries no vocabulary"
            )

    def describe(self) -> str:
        """The spec in words, for error messages: "a date", "an entity_ref to a team"."""
        if self.entity_kind is not None:
            return f"{with_article(self.kind.value)} to {with_article(self.entity_kind.value)}"
        if self.vocabulary is not None:
            return f"{with_article(self.kind.value)} from {self.vocabulary.__name__}"
        return with_article(self.kind.value)

    def check(self, value: FactValue) -> None:
        """Refuse ``value`` unless it is what this spec declares.

        >>> entity_value(EntityKind.TEAM).check(EntityRef(EntityKind.TEAM, "team_003"))
        >>> entity_value(EntityKind.TEAM).check(EntityRef(EntityKind.EMPLOYEE, "emp_017"))
        Traceback (most recent call last):
        ...
        ValueError: expected an entity_ref to a team, got an entity_ref to an employee
        >>> SKILL_VALUE.check("Kafka")
        Traceback (most recent call last):
        ...
        ValueError: expected a skill, got 'Kafka': a skill id is a lower-case vocabulary key
        """
        if self._admits(value):
            return
        detail = _describe(value)
        if self.kind is ValueKind.SKILL and isinstance(value, str):
            detail = f"{value!r}: a skill id is a lower-case vocabulary key"
        raise ValueError(f"expected {self.describe()}, got {detail}")

    def _admits(self, value: FactValue) -> bool:
        match self.kind:
            case ValueKind.ENTITY_REF:
                return isinstance(value, EntityRef) and value.kind is self.entity_kind
            case ValueKind.TEXT:
                return isinstance(value, str) and bool(value.strip())
            case ValueKind.ENUM:
                assert self.vocabulary is not None
                return isinstance(value, str) and value in set(self.vocabulary)
            case ValueKind.SKILL:
                return isinstance(value, str) and _is_skill(value)
            case ValueKind.DATE:
                return isinstance(value, date)
            case ValueKind.DATE_SPAN:
                return isinstance(value, DateSpan)
            case ValueKind.INSTANT_SPAN:
                return isinstance(value, InstantSpan)
            case ValueKind.REQUIREMENT:
                return isinstance(value, Requirement)


def entity_value(kind: EntityKind) -> ValueSpec:
    """The spec of a value that references an entity of ``kind``."""
    return ValueSpec(ValueKind.ENTITY_REF, entity_kind=kind)


def enum_value(vocabulary: type[StrEnum]) -> ValueSpec:
    """The spec of a value drawn from a closed vocabulary ``core`` owns."""
    return ValueSpec(ValueKind.ENUM, vocabulary=vocabulary)


TEXT_VALUE = ValueSpec(ValueKind.TEXT)
SKILL_VALUE = ValueSpec(ValueKind.SKILL)
DATE_VALUE = ValueSpec(ValueKind.DATE)
DATE_SPAN_VALUE = ValueSpec(ValueKind.DATE_SPAN)
INSTANT_SPAN_VALUE = ValueSpec(ValueKind.INSTANT_SPAN)
REQUIREMENT_VALUE = ValueSpec(ValueKind.REQUIREMENT)


def _is_skill(value: str) -> bool:
    try:
        skill_id(value)
    except ValueError:
        return False
    return True


def _describe(value: FactValue) -> str:
    match value:
        case EntityRef():
            return f"an entity_ref to {with_article(value.kind.value)}"
        case Requirement():
            return "a requirement"
        case DateSpan():
            return "a date_span"
        case InstantSpan():
            return "an instant_span"
        case date():
            return "a date"
        case str():
            # An enum member is its string; its repr would show the class instead.
            return repr(str(value))
