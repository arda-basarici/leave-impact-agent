"""Admission: whether a stated fact enters a run's view, decided over what the run had read.

A model states a fact with the words it read it from (``stated``). Before the rules may
conclude from it, five gates ask where the statement came from, each over the run's own
reads and nothing else (the contract step's rulings on the provenance gates and the anchor
guard):

- *the carrier was returned*: the comment or the section the statement names is inside a
  record some operation of the run returned;
- *the quote is in the carrier*: an exact substring of the carrier's text as read, with no
  normalization;
- *the subject was read*: the run returned a record of the entity the statement is about;
- *the value has a form*: an entity the run returned, or a skill of the public vocabulary,
  for a requirement every skill it asks for. A value the run has no display form for cannot
  be looked for in a quote;
- *the anchors are present*: the quote names what the statement says it is about, by the
  table ``anchors`` holds, a first-person quote in a comment counting as its author.

They are asked in that order and the first that fails refuses the statement with its
reason, so one statement is counted under one reason. A statement that passes all five is
admitted. The gates establish where a statement came from, never that the text entails it:
a negated sentence carries both anchors of the fact it denies.

*When.* An admission is decided when the answer that carried the statement is recorded, over
the reads logged before it (the composer group's third point). A read made later never
rescues a refusal; the model can state the fact again, and a refusal is per emission. The
caller holds that boundary by what it projects: ``reads`` is the projection of the
operations logged before the answer. A requirement's target is not a gate's business: a
requirement is admitted on its own carrier and quote, and its span is bound at composition
over everything read by then.

*The lexicon* is what a harness may know, and the boundary matters (the ruling on the
guard's lexicon): the public skill vocabulary, and the names and titles of the records the
run's reads returned. Never the generator's organization, never anything sealed. A colleague
named by given name alone is therefore not anchored, a stated recall cost on text that is
not the generator's. A returned record whose name or title is blank has no form, and a
statement about it is refused for the anchor nothing could meet: what a source returned is
never a reason for the harness to stop on a model's statement.

The gates are here, in ``core``, for the reason the join is: a harness admits with them and
the evaluator reruns them over an export to tell a model's behaviour from the guard's, and
the two may not import each other.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from leaveimpact.core.anchors import (
    SKILL_KIND,
    Lexicon,
    SurfaceForm,
    missing_anchors,
    quote_anchors,
    record_forms,
)
from leaveimpact.core.entities import Document, WorkItem
from leaveimpact.core.ids import SkillId
from leaveimpact.core.read_projection import StructuredReads
from leaveimpact.core.refs import EntityRef, clause_ref, comment_ref, employee_ref
from leaveimpact.core.skills import SKILLS
from leaveimpact.core.stated import Admission, Admitted, FactRefusal, Refused, StatedFact
from leaveimpact.core.values import Requirement, SkillCriterion


@dataclass(frozen=True, slots=True)
class CarrierText:
    """A comment or a section as a run read it: its text, and who wrote it when it is a
    comment (a section has no author)."""

    text: str
    author: EntityRef | None


def carriers_read(reads: StructuredReads) -> Mapping[EntityRef, CarrierText]:
    """Every comment and section inside a record ``reads`` returned, by its reference, each as
    first returned.

    >>> from datetime import date
    >>> from leaveimpact.core.read_projection import project_reads
    >>> dict(carriers_read(project_reads((), date(2026, 3, 2))))
    {}
    """
    carriers: dict[EntityRef, CarrierText] = {}
    for record in reads.returned:
        value = record.value
        if isinstance(value, WorkItem):
            for comment in value.comments:
                carriers[comment_ref(comment.id)] = CarrierText(
                    comment.text, employee_ref(comment.author_id)
                )
        elif isinstance(value, Document):
            for section in value.sections:
                carriers[clause_ref(section.id)] = CarrierText(section.text, None)
    return carriers


def run_lexicon(reads: StructuredReads) -> Lexicon:
    """The display forms a harness may look for in a quote: the public skill names, and the
    name or the title of every record ``reads`` returned.

    >>> from datetime import date
    >>> from leaveimpact.core.ids import skill_id
    >>> from leaveimpact.core.read_projection import project_reads
    >>> run_lexicon(project_reads((), date(2026, 3, 2))).skill(skill_id("gcp")).form
    'Google Cloud'
    """
    forms = [SurfaceForm(SKILL_KIND, skill.id, skill.name) for skill in SKILLS]
    for record in reads.returned:
        try:
            forms.extend(record_forms(record.value))
        except ValueError:
            # A blank name or title: the record has no form a quote could hold.
            continue
    return Lexicon(forms)


def admit(stated: StatedFact, reads: StructuredReads, lexicon: Lexicon) -> Admission:
    """Whether ``stated`` enters the view of a run whose reads so far are ``reads``.

    ``lexicon`` is ``run_lexicon(reads)``, passed in so a batch is admitted against one
    build of it. Raises nothing for what a model stated.
    """
    carrier = carriers_read(reads).get(stated.carrier)
    if carrier is None:
        return Refused(
            stated,
            FactRefusal.CARRIER_NOT_READ,
            f"no read of this run returned {stated.carrier.id}",
        )
    if stated.quote not in carrier.text:
        return Refused(
            stated,
            FactRefusal.QUOTE_NOT_IN_CARRIER,
            f"the quote is not a substring of {stated.carrier.id} as read",
        )
    if stated.subject not in reads.reads.returned:
        return Refused(
            stated,
            FactRefusal.SUBJECT_NOT_READ,
            f"no read of this run returned {stated.subject.id}",
        )
    formless = _formless(stated, reads, lexicon)
    if formless is not None:
        return Refused(stated, FactRefusal.VALUE_NOT_READ, formless)
    try:
        anchors = quote_anchors(stated.statement, lexicon, author=carrier.author)
    except ValueError as formless_record:
        return Refused(stated, FactRefusal.MISSING_ANCHOR, str(formless_record))
    missing = missing_anchors(stated.quote, anchors)
    if missing:
        named = "; ".join(" or ".join(repr(spelling) for spelling in group) for group in missing)
        return Refused(stated, FactRefusal.MISSING_ANCHOR, f"the quote does not name {named}")
    return Admitted(stated)


def _formless(stated: StatedFact, reads: StructuredReads, lexicon: Lexicon) -> str | None:
    """What ``stated``'s value names that the run has no display form for, or ``None``."""
    value = stated.value
    if isinstance(value, EntityRef):
        if value not in reads.reads.returned:
            return f"no read of this run returned {value.id}"
        return None
    skills: tuple[SkillId, ...] = ()
    if isinstance(value, Requirement):
        skills = tuple(c.skill for c in value.criteria if isinstance(c, SkillCriterion))
    elif isinstance(value, str):
        skills = (SkillId(value),)
    for skill in skills:
        if lexicon.alias(SKILL_KIND, skill) is None:
            return f"{skill} is not a skill of the public vocabulary"
    return None


__all__ = ["CarrierText", "admit", "carriers_read", "run_lexicon"]
