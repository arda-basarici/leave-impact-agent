"""The lexical anchors: the surface forms a text stating a fact cannot avoid, and the one test
of whether a text holds them.

Two parties ask the same cheap question of a text and may not import each other. The
world's generator asks it of a drafted comment or section before a checker is paid: a
required fact whose names are not in the text vanished in the writing. A harness asks it of
the quote a model gives for a fact it states: a quote that names neither the person nor
the skill is not where that fact was read (the contract step's ruling on the anchor
guard). The table that says which forms a statement of each predicate must show, the
spellings a count or an employment type may take, and the presence test itself are here so
that both ask it one way; it was the world's until a harness needed it, and ``agent`` may
not import ``world``.

Presence proves no relation. "Deniz has never worked with Kafka" carries both anchors of
the fact it denies, so the check is a guard against a statement with no textual footing
and never a judgement that the text entails it. A predicate with no row cannot be carried
by prose at all.

The two askers differ in one respect, the first person. A comment's author writes "I" and
never their own name. The generator knows the fact it required and who the target's author
is, so ``lexical_anchors`` drops the subject's group when the subject is that author. A
harness knows only what a model stated, so ``quote_anchors`` keeps every group and widens
the author's with the first-person words: a quote from the author's comment that names
nobody and says "I" still anchors the author, and one that says neither anchors no one.

They differ in a second respect, the count of one. A clause that asks for one person
seldom writes the number: "needs an engineer with Go experience", "the contact named in
the account notes needs React experience". The generator never asks a model to write a
requirement, so its reading has no such text to meet. A harness meets it in every clause of
that kind: with the count anchored, the guard refused 15 of the 17 requirements a truthful
reading of the suite's throwaway world holds, every one a count of one (the composer's
tests hold the count). So ``quote_anchors`` asks a requirement of one for its criteria
only, and a requirement of two or more for its number as well. A clause that names no
number asks for one, which is the plan rule's own default. The guard stays lexical: a
model that reads "two engineers" as one is admitted and graded wrong, and a requirement
of one with no criterion has no anchor at all, so what it composes is judged like any
other constraint and admission says nothing of whether it is right.

A ``Lexicon`` is the lookup both read display forms through, and where its forms come from
is the caller's and is the boundary that matters. The generator builds one from its
organization. A harness builds one from the records its run read and from the public skill
vocabulary, with ``record_forms``, and never from the generator's organization or from
anything sealed: a name the run did not read has no form, and a statement about it is
refused for that.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from leaveimpact.core.entities import (
    CalendarEvent,
    Component,
    Document,
    Employee,
    Team,
    WorkItem,
)
from leaveimpact.core.enums import EmploymentType
from leaveimpact.core.facts import Fact, Statement, statement_of
from leaveimpact.core.ids import SkillId, skill_id
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.ports.observed import KIND_BY_ENTITY_TYPE, Entity
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.values import EmploymentTypeCriterion, Requirement, SkillCriterion

# --- Surface forms --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SurfaceForm:
    """One thing a text may name and the spelling it names it by: a person, a skill, a title."""

    kind: str
    id: str
    form: str

    def __post_init__(self) -> None:
        if not self.form.strip():
            raise ValueError(f"a surface form for {self.kind} {self.id} is not blank")


SKILL_KIND = "skill"
"""The surface-form kind of a skill, which is a vocabulary term and not an entity."""

GIVEN_NAME_KIND = "given_name"
"""The surface-form kind of an employee's given name alone, keyed by the employee's id: a text
names a colleague by first name, and a guard that knew only full names would not see it."""


class Lexicon:
    """Every display form its builder afforded, by kind and id.

    A pure lookup: the anchors and the generator's namespace derivation read it, and who
    filled it decides what it can name (the module docstring).
    """

    def __init__(self, forms: Iterable[SurfaceForm]) -> None:
        self._forms: dict[tuple[str, str], str] = {}
        for form in forms:
            key = (form.kind, form.id)
            if key in self._forms and self._forms[key] != form.form:
                raise ValueError(f"{form.kind} {form.id} has two display forms")
            self._forms[key] = form.form

    def forms(self) -> tuple[SurfaceForm, ...]:
        """Every form held, in (kind, id) order — the scanner's list of what a world can name."""
        return tuple(
            SurfaceForm(kind, id, form) for (kind, id), form in sorted(self._forms.items())
        )

    def form_of(self, ref: EntityRef) -> SurfaceForm:
        return self._surface(ref.kind.value, ref.id)

    def alias(self, kind: str, id: str) -> SurfaceForm | None:
        """The form of ``kind`` for ``id`` when the world has one (a given name); else ``None``."""
        form = self._forms.get((kind, id))
        return None if form is None else SurfaceForm(kind, id, form)

    def skill(self, skill: SkillId) -> SurfaceForm:
        return self._surface(SKILL_KIND, skill_id(skill))

    def _surface(self, kind: str, id: str) -> SurfaceForm:
        try:
            return SurfaceForm(kind, id, self._forms[(kind, id)])
        except KeyError:
            raise ValueError(f"{kind} {id} has no display form in this world") from None


def record_forms(entity: Entity) -> tuple[SurfaceForm, ...]:
    """The display forms one returned record affords: its name or its title, nothing else.

    What a harness fills its lexicon from, one record at a time; a leave names nothing, and
    a comment or a section is text and has no form.

    >>> from leaveimpact.core.ids import team_id
    >>> record_forms(Team(team_id(2), "Payments"))
    (SurfaceForm(kind='team', id='team_002', form='Payments'),)
    """
    match entity:
        case Employee() | Team() | Component():
            return (SurfaceForm(KIND_BY_ENTITY_TYPE[type(entity)].value, entity.id, entity.name),)
        case WorkItem() | CalendarEvent() | Document():
            return (SurfaceForm(KIND_BY_ENTITY_TYPE[type(entity)].value, entity.id, entity.title),)
        case _:
            return ()


# --- The table ------------------------------------------------------------------------------

Anchor = tuple[str, ...]
"""One thing a text stating a fact cannot avoid, as its alternative spellings; one must appear."""

NUMBER_WORDS: Mapping[int, str] = MappingProxyType(
    {
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
    }
)
"""A count may be written as a digit or a word; a text is not refused for choosing either."""

EMPLOYMENT_FORMS: Mapping[EmploymentType, Anchor] = MappingProxyType(
    {
        EmploymentType.EMPLOYEE: ("employee", "employees"),
        EmploymentType.CONTRACTOR: ("contractor", "contractors"),
    }
)

FIRST_PERSON: Anchor = ("I", "my", "me")
"""The words by which a comment's author names themself; they widen the author's group in a
quote's anchors and are never anchors on their own."""


class AnchorShape(StrEnum):
    """What a statement of a predicate must show; a member is the registered form of a row."""

    SUBJECT_AND_ENTITY = "subject_and_entity"
    SUBJECT_AND_SKILL = "subject_and_skill"
    NAMED_ENTITY = "named_entity"
    REQUIREMENT = "requirement"


ANCHOR_ROWS: Mapping[PredicateName, AnchorShape] = MappingProxyType(
    {
        PredicateName.HAS_SKILL: AnchorShape.SUBJECT_AND_SKILL,
        PredicateName.MEMBER_OF_COMPONENT: AnchorShape.SUBJECT_AND_ENTITY,
        PredicateName.OWNS_WORK_ITEM: AnchorShape.SUBJECT_AND_ENTITY,
        PredicateName.REQUIRES: AnchorShape.REQUIREMENT,
        PredicateName.NAMES_RESPONSIBLE: AnchorShape.NAMED_ENTITY,
    }
)
"""The predicates prose can carry, each with the shape of its anchors. A subject-first shape
puts the subject's group first, which the generator's first-person drop relies on."""

PRESENCE_RULE = "whole_word_ignoring_case"
"""The name of the presence test, the part of it the table's digest can hold: the digest covers
this name and not ``word_pattern``'s code, so whoever changes how a spelling is looked for
renames the rule with it, and the pinned digest in the tests is what makes that a decision."""


REQUIREMENT_OF_ONE = "count_not_anchored_in_a_quote"
"""The name of the quote guard's rule for a requirement that asks for one person, held by the
table's digest as the presence rule's name is."""


def anchor_table_digest() -> str:
    """The SHA-256 of the table as data: the rows, the spellings, the first-person words and
    the presence rule, in canonical JSON. What a registration records beside the fact
    vocabulary, so a changed guard is a changed registration.

    >>> len(anchor_table_digest())
    64
    """
    table: JsonObject = {
        "rows": {name.value: shape.value for name, shape in ANCHOR_ROWS.items()},
        "number_words": {str(count): word for count, word in NUMBER_WORDS.items()},
        "employment_forms": {kind.value: list(forms) for kind, forms in EMPLOYMENT_FORMS.items()},
        "first_person": list(FIRST_PERSON),
        "presence": PRESENCE_RULE,
        "requirement_of_one": REQUIREMENT_OF_ONE,
    }
    return hashlib.sha256(canonical_bytes(table)).hexdigest()


def _groups(statement: Statement, lexicon: Lexicon) -> tuple[Anchor, ...]:
    subject, name, value = statement
    shape = ANCHOR_ROWS.get(name)
    if shape is None:
        raise ValueError(f"{name.value} cannot be carried by prose: no anchor row")
    match shape:
        case AnchorShape.SUBJECT_AND_ENTITY:
            assert isinstance(value, EntityRef)
            return ((lexicon.form_of(subject).form,), (lexicon.form_of(value).form,))
        case AnchorShape.SUBJECT_AND_SKILL:
            assert isinstance(value, str)
            return ((lexicon.form_of(subject).form,), (lexicon.skill(SkillId(value)).form,))
        case AnchorShape.NAMED_ENTITY:
            # The subject is the carrier itself: the named entity is the only anchor.
            assert isinstance(value, EntityRef)
            return ((lexicon.form_of(value).form,),)
        case AnchorShape.REQUIREMENT:
            # A clause's requirement: its count in either spelling and every criterion's form.
            assert isinstance(value, Requirement)
            count = value.count
            spellings = (
                (str(count), NUMBER_WORDS[count]) if count in NUMBER_WORDS else (str(count),)
            )
            anchors: list[Anchor] = [spellings]
            for criterion in value.criteria:
                match criterion:
                    case SkillCriterion():
                        anchors.append((lexicon.skill(criterion.skill).form,))
                    case EmploymentTypeCriterion():
                        anchors.append(EMPLOYMENT_FORMS[criterion.employment_type])
            return tuple(anchors)


def lexical_anchors(
    fact: Fact, lexicon: Lexicon, *, first_person: EntityRef | None = None
) -> tuple[Anchor, ...]:
    """The anchors a text carrying ``fact`` must contain, one alternative group per named thing.

    Lexical only: presence proves no relation ("Deniz has never worked with Kafka" carries
    both anchors), which is the extraction check's job; absence proves the fact vanished
    in the writing, which is worth catching before a checker is paid. ``first_person``
    is the text's author when it has one — a comment's. When a required fact's subject
    is that author, the target supplies the subject's identity and the anchors are the
    fact's value-side groups only, since the author writes "I" and never their own name:
    the first measurement world refused twelve of twelve attempts on exactly that anchor
    (2026-09-14). The exemption is that narrow on purpose: a fact about anyone else keeps
    its subject anchor, and a row whose subject is a clause or the carrier never matches
    an author. The drop is positional, so every row with an employee subject puts the
    subject's group first; a row that broke that order would drop a value anchor
    unnoticed.

    >>> from datetime import date
    >>> from leaveimpact.core.enums import Source
    >>> from leaveimpact.core.ids import comment_id, employee_id
    >>> from leaveimpact.core.refs import EvidenceRef, comment_ref, employee_ref
    >>> deniz = employee_ref(employee_id(23))
    >>> lexicon = Lexicon([SurfaceForm("employee", "emp_023", "Deniz Kaya"),
    ...                    SurfaceForm(SKILL_KIND, "kafka", "Kafka")])
    >>> fact = Fact(deniz, PredicateName.HAS_SKILL, "kafka",
    ...             EvidenceRef(Source.JIRA, comment_ref(comment_id(5))), date(2026, 3, 1))
    >>> lexical_anchors(fact, lexicon)
    (('Deniz Kaya',), ('Kafka',))
    """
    anchors = _groups(statement_of(fact), lexicon)
    if first_person is not None and fact.subject == first_person:
        return anchors[1:]
    return anchors


def quote_anchors(
    statement: Statement, lexicon: Lexicon, *, author: EntityRef | None = None
) -> tuple[Anchor, ...]:
    """The anchors the quote given for ``statement`` must contain, when the quote's carrier was
    written by ``author`` (a comment's; ``None`` for a section).

    Every group of the table stays, but for the count of a requirement that asks for one
    person, which such a clause seldom writes. A group that names ``author``, as the
    subject or as the value, also admits the first-person words, so "I have run Kafka for
    years" anchors its author and the same words in anyone else's comment anchor nobody.
    ``ValueError`` when
    the lexicon holds no form for something the statement names: the caller's lexicon is
    what the run read, and a statement about a thing it did not read is refused there.

    >>> from leaveimpact.core.ids import employee_id
    >>> from leaveimpact.core.refs import employee_ref
    >>> deniz = employee_ref(employee_id(23))
    >>> lexicon = Lexicon([SurfaceForm("employee", "emp_023", "Deniz Kaya"),
    ...                    SurfaceForm(SKILL_KIND, "kafka", "Kafka")])
    >>> quote_anchors((deniz, PredicateName.HAS_SKILL, "kafka"), lexicon, author=deniz)
    (('Deniz Kaya', 'I', 'my', 'me'), ('Kafka',))
    """
    groups = _groups(statement, lexicon)
    subject, name, value = statement
    if isinstance(value, Requirement):
        # A requirement names no person, so it has no first person, whoever wrote it. The
        # count's group is the first; one person is asked for without a number.
        return groups[1:] if value.count == 1 else groups
    if author is None:
        return groups
    named: tuple[object, ...]
    match ANCHOR_ROWS[name]:
        case AnchorShape.SUBJECT_AND_ENTITY:
            named = (subject, value)
        case AnchorShape.SUBJECT_AND_SKILL:
            named = (subject, None)
        case AnchorShape.NAMED_ENTITY | AnchorShape.REQUIREMENT:
            # A requirement returned above; its row is named here for the match to be whole.
            named = (value,)
    return tuple(
        (*group, *FIRST_PERSON) if who == author else group
        for group, who in zip(groups, named, strict=True)
    )


# --- Presence -------------------------------------------------------------------------------


def word_pattern(spelling: str, flags: int) -> re.Pattern[str]:
    """``spelling`` as a whole word: not preceded and not followed by a word character."""
    return re.compile(rf"(?<!\w){re.escape(spelling)}(?!\w)", flags)


def missing_anchors(text: str, groups: Iterable[Anchor]) -> tuple[Anchor, ...]:
    """The groups none of whose spellings appears in ``text`` as a whole word, case ignored.

    >>> missing_anchors("Deniz Kaya ran the kafka migration.", (("Deniz Kaya",), ("Kafka",)))
    ()
    >>> missing_anchors("She ran the migration.", (("Deniz Kaya",), ("Kafka",)))
    (('Deniz Kaya',), ('Kafka',))
    """
    return tuple(
        group
        for group in groups
        if not any(word_pattern(spelling, re.IGNORECASE).search(text) for spelling in group)
    )


__all__ = [
    "ANCHOR_ROWS",
    "EMPLOYMENT_FORMS",
    "FIRST_PERSON",
    "GIVEN_NAME_KIND",
    "NUMBER_WORDS",
    "PRESENCE_RULE",
    "REQUIREMENT_OF_ONE",
    "SKILL_KIND",
    "Anchor",
    "AnchorShape",
    "Lexicon",
    "SurfaceForm",
    "anchor_table_digest",
    "lexical_anchors",
    "missing_anchors",
    "quote_anchors",
    "record_forms",
    "word_pattern",
]
