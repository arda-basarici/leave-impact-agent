"""Briefs: the typed pending targets a scenario leaves for a model to write, and the contract that
binds them to the facts they carry.

A brief is a target's definition and the model's whole instruction (the step 14 rulings in
DESIGN, "Truth before prose"). The target is one comment on a work item or one section of a
document, named by the id the world minted for it, with the construction fields its part
needs once text exists — the parent, the position in the parent's order, and for a comment
its world date and author — so the model returns prose and nothing else. The brief lists
the facts the text must carry as positive ``Fact`` records, the true context facts it may
mention, the surface namespace derived from those facts through the closed vocabulary, and
the register the text is written in, which follows from the target: a comment reads as a
ticket comment, a section as its document's kind. Nothing forbidden is listed: under
containment an extra owner or cardinality is refused because no allowed proposition
matches it, and a second list would be a second source of truth.

A scenario class authors a *pending* brief — target, required, allowed — and the framework
derives the rest: the namespace, the register, and each required fact's role, found by
running the rules once with the fact removed. That is the discipline of the organization
generator applied to prose: the class states what it wants, the world computes what that
implies, and a value a class could get wrong is not a value the class writes.

Two carriers exist for an authored fact and the contract admits both. A part the class
writes itself, a template-written clause present from the start, may carry the fact with
no brief and no model — structured-shaped text by DESIGN's own definition, at no cost and
with no containment risk. A model-written part is absent until composed and carries its
fact through exactly one brief. The pre-compose contract, run before the semantic world is
sealed, is that every prose-authored fact has exactly one carrier, every brief's required
facts are exactly the authored facts naming its target, every brief names a parent the
scenario owns and a position that parent can hold, and no target is both present and
pending. The post-compose contract, the composition module's, is the bijection between
brief, prose result and composed part once the text exists.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from leaveimpact.core.entities import CalendarEvent, Document, WorkItem
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.facts import Fact, FactBase
from leaveimpact.core.ids import ClauseId, CommentId, DocumentId, EmployeeId, WorkItemId
from leaveimpact.core.refs import (
    SOURCE_BY_TARGET_KIND,
    EntityRef,
    clause_ref,
    comment_ref,
    employee_ref,
)
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.prose import (
    CLIENT_KIND,
    GIVEN_NAME_KIND,
    PROSE_CAPABLE,
    SKILL_KIND,
    FactRole,
    Lexicon,
    Namespace,
    SurfaceForm,
    derive_namespace,
    statement_of,
)
from leaveimpact.world.vocabulary import CLIENT_NAMES, SKILLS

# The planted records a scenario owns arrive as plain tuples rather than as the scenario
# module's ``OwnedEntities``: that module holds the scenario record, which carries briefs,
# so it imports this one and not the reverse.


class ProseContractError(ValueError):
    """A brief, or the set of briefs and facts of a scenario, cannot describe one world."""


# --- Targets ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommentTarget:
    """A comment to be written on a work item: where it goes, when it was said, by whom.

    ``position`` is the comment's index in the work item's final comment order; the
    template-written comments the class planted fill the other slots in their order.
    """

    id: CommentId
    work_item_id: WorkItemId
    position: int
    world_date: date
    author_id: EmployeeId

    def __post_init__(self) -> None:
        if self.position < 0:
            raise ValueError(f"{self.id}: a position is non-negative, got {self.position}")


@dataclass(frozen=True, slots=True)
class SectionTarget:
    """A section to be written in a document, at a position in the document's clause order."""

    id: ClauseId
    document_id: DocumentId
    position: int

    def __post_init__(self) -> None:
        if self.position < 0:
            raise ValueError(f"{self.id}: a position is non-negative, got {self.position}")


ProseTarget = CommentTarget | SectionTarget
"""Where a model-written part goes: a comment or a section, never a whole record."""


def target_ref(target: ProseTarget) -> EntityRef:
    """The evidence reference an authored fact carried by ``target`` names."""
    match target:
        case CommentTarget():
            return comment_ref(target.id)
        case SectionTarget():
            return clause_ref(target.id)


def parent_id(target: ProseTarget) -> str:
    match target:
        case CommentTarget():
            return target.work_item_id
        case SectionTarget():
            return target.document_id


# --- Briefs -------------------------------------------------------------------------------


class Register(StrEnum):
    """How the text reads: one register per document kind, and the ticket comment."""

    RUNBOOK = "runbook"
    CLIENT_NOTE = "client_note"
    PROCEDURE = "procedure"
    POLICY = "policy"
    TICKET_COMMENT = "ticket_comment"


@dataclass(frozen=True, slots=True)
class PendingProse:
    """What a scenario class authors for one target: the facts to carry and the facts allowed.

    Required facts name the target as their evidence and use a prose-capable predicate;
    allowed facts are context the text may mention and never restate a required one.
    """

    target: ProseTarget
    required: tuple[Fact, ...]
    allowed: tuple[Fact, ...] = ()

    def __post_init__(self) -> None:
        _check_facts(self.target, self.required, self.allowed)


@dataclass(frozen=True, slots=True)
class RequiredFact:
    """A required fact with the role the framework derived for it."""

    fact: Fact
    role: FactRole


@dataclass(frozen=True, slots=True)
class Brief:
    """A pending target with everything the materializer needs: the framework's completion
    of a class's ``PendingProse``, built through ``brief_for`` and never by hand."""

    target: ProseTarget
    required: tuple[RequiredFact, ...]
    allowed: tuple[Fact, ...]
    namespace: Namespace
    register: Register

    def __post_init__(self) -> None:
        _check_facts(self.target, self.required_facts, self.allowed)

    @property
    def required_facts(self) -> tuple[Fact, ...]:
        return tuple(required.fact for required in self.required)

    @property
    def id(self) -> str:
        return self.target.id


def _check_facts(target: ProseTarget, required: Sequence[Fact], allowed: Sequence[Fact]) -> None:
    ref = target_ref(target)
    for fact in required:
        if fact.evidence.target != ref:
            raise ProseContractError(
                f"{target.id}: a required fact names its target as evidence, got "
                f"{fact.predicate.value} of {fact.subject.id} evidenced by "
                f"{fact.evidence.target.id}"
            )
        if fact.predicate not in PROSE_CAPABLE:
            raise ProseContractError(
                f"{target.id}: {fact.predicate.value} cannot be carried by prose"
            )
    carrier_source = SOURCE_BY_TARGET_KIND[ref.kind]
    for fact in allowed:
        # A fact this text evidences is one the text must carry, which makes it required;
        # allowing it instead would let a hedge or an omission pass as context.
        if fact.evidence.target == ref:
            raise ProseContractError(
                f"{target.id}: an allowed fact is evidenced elsewhere, a fact this target "
                f"evidences is required, got {fact.predicate.value} of {fact.subject.id}"
            )
        # Allowed context is harmless only while restating it in prose opens no evidence
        # path the fact base does not model. Required sources are derived by asking the
        # rules under each single source's outage; a fact of the carrier's own source
        # vanishes with its carrier in that outage, but a fact of another source restated
        # here would survive that source's outage in this text alone, readable by the
        # agent and absent from the base (the review of 2026-09-15). Such a fact is
        # required, so the base carries its second evidence record, or stays out of the
        # text.
        if fact.evidence.source is not carrier_source:
            raise ProseContractError(
                f"{target.id}: an allowed fact shares the target's source "
                f"{carrier_source.value}, got {fact.predicate.value} of {fact.subject.id} "
                f"evidenced by {fact.evidence.source.value}"
            )
    if len(set(required)) != len(required):
        raise ProseContractError(f"{target.id}: a required fact is stated once")
    if len(set(allowed)) != len(allowed):
        raise ProseContractError(f"{target.id}: an allowed fact is stated once")
    restated = {statement_of(fact) for fact in required} & {statement_of(fact) for fact in allowed}
    if restated:
        raise ProseContractError(
            f"{target.id}: an allowed fact never restates a required one, got "
            f"{sorted(f'{p.value} of {s.id}' for s, p, _ in restated)}"
        )


# --- Derivation: the lexicon, the register, the brief -------------------------------------


def lexicon_of(
    org: OrgSpec,
    work_items: Iterable[WorkItem] = (),
    documents: Iterable[Document] = (),
    events: Iterable[CalendarEvent] = (),
) -> Lexicon:
    """Every display form ``org`` and the planted records afford: names, skills, titles, and
    every client of the vocabulary.

    The clients are the whole table and not a world's own list, because a world has no
    client list: a client exists only as a note's title. The scanner can police a name only
    if it is a form, so the closed table is what makes a foreign client refusable.
    """
    forms: list[SurfaceForm] = [
        *(SurfaceForm(CLIENT_KIND, client_id(name), name) for name in CLIENT_NAMES),
        *(SurfaceForm(EntityKind.EMPLOYEE.value, e.id, e.name) for e in org.employees),
        *(SurfaceForm(GIVEN_NAME_KIND, e.id, e.name.split()[0]) for e in org.employees),
        *(SurfaceForm(EntityKind.TEAM.value, t.id, t.name) for t in org.teams),
        *(SurfaceForm(EntityKind.COMPONENT.value, c.id, c.name) for c in org.components),
        *(SurfaceForm(SKILL_KIND, s.id, s.name) for s in SKILLS if s.id in org.skills),
        *(SurfaceForm(EntityKind.WORK_ITEM.value, w.id, w.title) for w in work_items),
        *(SurfaceForm(EntityKind.DOCUMENT.value, d.id, d.title) for d in documents),
        *(SurfaceForm(EntityKind.EVENT.value, e.id, e.title) for e in events),
    ]
    return Lexicon(forms)


def client_id(name: str) -> str:
    """The lexicon id of a client, from its one representation: the name, lowered, spaces joined.

    >>> client_id("Quarry Hill")
    'quarry_hill'
    """
    return name.casefold().replace(" ", "_")


def clients_named_by(title: str, lexicon: Lexicon) -> tuple[SurfaceForm, ...]:
    """The client forms ``title`` names at word boundaries, in the lexicon's order.

    A client's only representation is a note's title, so a section's brief learns its
    client from the title and nowhere else; the match is by whole word so no client's
    name is found inside another's.
    """
    return tuple(
        form
        for form in lexicon.forms()
        if form.kind == CLIENT_KIND
        and re.search(rf"(?<!\w){re.escape(form.form)}(?!\w)", title) is not None
    )


def brief_for(
    pending: PendingProse,
    work_items: Sequence[WorkItem],
    documents: Sequence[Document],
    lexicon: Lexicon,
    roles: Mapping[Fact, FactRole],
) -> Brief:
    """The brief of ``pending``: register from the target, namespace from the facts, roles as given.

    ``roles`` must name every required fact; the parent must be among the records given.
    The namespace also admits the parent's title and, for a comment, the author's name,
    which no fact mentions and a text naturally does; a section's admits the client its
    document's title names, so a client note may say which client it is about while every
    other client stays a foreign name.
    """
    parent = _parent(pending.target, work_items, documents)
    extra = [lexicon.form_of(EntityRef(_parent_kind(pending.target), parent.id))]
    register = Register.TICKET_COMMENT
    match pending.target:
        case CommentTarget():
            extra.append(lexicon.form_of(employee_ref(pending.target.author_id)))
        case SectionTarget():
            assert isinstance(parent, Document)
            register = Register(parent.kind.value)
            extra.extend(clients_named_by(parent.title, lexicon))
    missing = [f for f in pending.required if f not in roles]
    if missing:
        raise ProseContractError(
            f"{pending.target.id}: no role derived for "
            f"{[f'{f.predicate.value} of {f.subject.id}' for f in missing]}"
        )
    return Brief(
        target=pending.target,
        required=tuple(RequiredFact(fact, roles[fact]) for fact in pending.required),
        allowed=pending.allowed,
        namespace=derive_namespace([*pending.required, *pending.allowed], lexicon, extra),
        register=register,
    )


def _parent_kind(target: ProseTarget) -> EntityKind:
    return EntityKind.WORK_ITEM if isinstance(target, CommentTarget) else EntityKind.DOCUMENT


def _parent(
    target: ProseTarget, work_items: Sequence[WorkItem], documents: Sequence[Document]
) -> WorkItem | Document:
    match target:
        case CommentTarget():
            for item in work_items:
                if item.id == target.work_item_id:
                    return item
            raise ProseContractError(
                f"{target.id}: its work item {target.work_item_id} is not one the scenario owns"
            )
        case SectionTarget():
            for document in documents:
                if document.id == target.document_id:
                    return document
            raise ProseContractError(
                f"{target.id}: its document {target.document_id} is not one the scenario owns"
            )


# --- The pre-compose contract -------------------------------------------------------------


def parts_of(work_items: Iterable[WorkItem], documents: Iterable[Document]) -> Mapping[str, str]:
    """Every comment and section present in the records, by id, to the id of its parent."""
    parts: dict[str, str] = {}
    for item in work_items:
        for comment in item.comments:
            parts[comment.id] = item.id
    for document in documents:
        for section in document.sections:
            parts[section.id] = document.id
    return parts


def check_pending(
    work_items: Sequence[WorkItem],
    documents: Sequence[Document],
    briefs: Sequence[Brief],
    authored: Sequence[Fact],
) -> None:
    """Refuse ``briefs`` and ``authored`` unless every fact has one carrier and every brief fits.

    Each brief's target is pending — absent from the records — under a parent the scenario
    owns, at a position the parent's final order can hold, with no two briefs on one
    target; each brief requires exactly the authored facts that name its target; and each
    authored fact evidenced by a comment or a clause is carried either by a part present in
    the records or by exactly one brief.
    """
    present = parts_of(work_items, documents)
    ids = [brief.id for brief in briefs]
    if len(set(ids)) != len(ids):
        raise ProseContractError(f"a target has one brief, got {ids}")
    pending_by_parent: dict[str, list[int]] = {}
    for brief in briefs:
        if brief.id in present:
            raise ProseContractError(
                f"{brief.id}: pending under a brief and already present in the scenario"
            )
        _parent(brief.target, work_items, documents)
        pending_by_parent.setdefault(parent_id(brief.target), []).append(brief.target.position)
    for parent, positions in pending_by_parent.items():
        slots = sum(1 for owner in present.values() if owner == parent) + len(positions)
        if len(set(positions)) != len(positions) or any(p >= slots for p in positions):
            raise ProseContractError(
                f"{parent}: pending positions {sorted(positions)} do not fit an order of "
                f"{slots} parts"
            )
    by_target: dict[EntityRef, set[Fact]] = {}
    for fact in authored:
        target = fact.evidence.target
        if target.kind not in (EntityKind.COMMENT, EntityKind.CLAUSE):
            continue
        by_target.setdefault(target, set()).add(fact)
        if target.id not in present and target.id not in ids:
            raise ProseContractError(
                f"{fact.predicate.value} of {fact.subject.id} is evidenced by {target.id}, "
                "which is neither a part the scenario planted nor a brief's target"
            )
    for brief in briefs:
        named = by_target.get(target_ref(brief.target), set())
        if named != set(brief.required_facts):
            raise ProseContractError(
                f"{brief.id}: the brief requires {_names(brief.required_facts)} and the "
                f"authored facts naming it are {_names(named)}"
            )


def check_allowed(briefs: Sequence[Brief], base: FactBase) -> None:
    """Refuse a brief whose allowed context is not a fact of the world it belongs to."""
    truths = {statement_of(fact) for fact in base.facts}
    for brief in briefs:
        foreign = [fact for fact in brief.allowed if statement_of(fact) not in truths]
        if foreign:
            raise ProseContractError(
                f"{brief.id}: an allowed fact is a fact of the world, got {_names(foreign)}"
            )


def _names(facts: Iterable[Fact]) -> list[str]:
    return sorted(f"{fact.predicate.value} of {fact.subject.id}" for fact in facts)


__all__ = [
    "Brief",
    "CommentTarget",
    "client_id",
    "clients_named_by",
    "PendingProse",
    "ProseContractError",
    "ProseTarget",
    "Register",
    "RequiredFact",
    "SectionTarget",
    "brief_for",
    "check_allowed",
    "check_pending",
    "lexicon_of",
    "parent_id",
    "parts_of",
    "target_ref",
]
