"""What a requirement clause applies to, read off the clause's own text: the one scope matcher the
generator runs at assembly and the evaluator runs at load.

The fact base holds what a clause requires and nothing about what it applies to; that
pairing lives in the sealed keys. A run's view admits it through the clause, like a fact,
and that is sound only if the pairing is something the clause itself states. Four
properties make it so, and a world failing one is refused whole, since no run of it could
be graded on a scope it had no way to read:

1. every clause with a requirement has exactly one scope target;
2. every scope pairing names a clause with a requirement;
3. the document behind a section-kind target holds that one section, a section being named
   through its document's title;
4. the clause's own text names its target: every title of a ticket, a meeting or a
   document of the world is searched in the text, the titles contained in a longer found
   title are set aside, and exactly one artifact is left, the target.

The fourth reads the text and not the pairing, which the first three cannot do: they would
all hold for a clause that named nothing, or another artifact. Containment alone does not
resolve a text, because titles nest by design (a qualified title is the plain one with a
suffix), so the longest found titles decide. Only tickets, meetings and documents are
searched, the kinds a class scopes a clause by; a pairing whose target is of another kind
has no resolver and is reported by name, never passed.

The matcher is in the world package because two sides run it over one universe of titles
(the generator step's ruling 3, 2026-10-08): the generator at assembly, over the planted
records and the filler pool, where a filler title that contains or equals a planted one
would steal a clause's resolution; and the evaluator at load, over the sealed records, as
the proof the loader needs. One function on both sides means neither can drift from the
other. What differs between the two readings is time: at assembly a model-written part has
no text yet, so its ``ScopePart`` carries ``None`` and the fourth property waits for the
load, while the first three are read in full, a pending section counting as the section
its document holds. The problem vocabulary is here with the matcher, which authors most of
it; the index adds its sealing problems in the same type so a loader reports one list.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.entities import Document
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import ClauseId, ScenarioId
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import (
    EntityRef,
    clause_ref,
    comment_ref,
    document_ref,
    event_ref,
    work_item_ref,
)
from leaveimpact.world.briefs import Brief, CommentTarget, SectionTarget
from leaveimpact.world.scenario import Planted, Scenario


class ProblemKind(StrEnum):
    """What can make a sealed world unreadable as an index; a member names the proof that
    failed. The first three are the index's own, the rest the scope matcher's."""

    RECORD_SEALED_TWICE = "record_sealed_twice"
    PART_SEALED_TWICE = "part_sealed_twice"
    CARRIER_NOT_SEALED = "carrier_not_sealed"
    REQUIREMENT_NOT_SCOPED_ONCE = "requirement_not_scoped_once"
    SCOPE_WITHOUT_REQUIREMENT = "scope_without_requirement"
    SCOPE_TARGET_NOT_SEALED = "scope_target_not_sealed"
    SCOPE_DOCUMENT_NOT_ONE_SECTION = "scope_document_not_one_section"
    SCOPE_KIND_HAS_NO_RESOLVER = "scope_kind_has_no_resolver"
    SCOPE_NOT_STATED_BY_THE_CLAUSE = "scope_not_stated_by_the_clause"


@dataclass(frozen=True, slots=True)
class IndexProblem:
    """One reason the sealed world cannot be indexed. ``detail`` names ids and is truth."""

    kind: ProblemKind
    scenario_id: ScenarioId | None
    detail: str


@dataclass(frozen=True, slots=True)
class ScopePart:
    """A comment or a section as the matcher reads it: the record it is read inside and its
    text, ``None`` while a model still owes the part, which is the assembly's reading."""

    parent: EntityRef
    text: str | None


TITLED_KINDS = frozenset({EntityKind.WORK_ITEM, EntityKind.EVENT, EntityKind.DOCUMENT})
"""The kinds a clause is scoped by, each named in prose by its title."""


def resolve_scope(text: str, titled: Iterable[tuple[EntityRef, str]]) -> tuple[EntityRef, ...]:
    """The artifacts ``text`` names by title, once the titles contained in a longer found one
    are set aside: one artifact when the text states a scope, none or several when it
    does not.

    >>> from leaveimpact.core.ids import work_item_id
    >>> plain = (work_item_ref(work_item_id(1)), "Auth: rotate the keys")
    >>> regional = (work_item_ref(work_item_id(2)), "Auth: rotate the keys for the EU region")
    >>> text = "The Auth: rotate the keys for the EU region release needs a Go engineer."
    >>> [artifact.id for artifact in resolve_scope(text, (plain, regional))]
    ['ticket_002']
    >>> [artifact.id for artifact in resolve_scope("The release needs a Go engineer.", (plain,))]
    []
    """
    found = [(artifact, title) for artifact, title in titled if title in text]
    return tuple(
        artifact
        for artifact, title in found
        if not any(title != other and title in other for _, other in found)
    )


def scope_problems(
    scenarios: Sequence[Scenario],
    titles: Mapping[EntityRef, str],
    parts: Mapping[EntityRef, ScopePart],
) -> tuple[dict[ClauseId, EntityRef], list[IndexProblem]]:
    """Each requirement clause's scope target, and what the four properties find wrong.

    ``titles`` is every titled record of the world, the filler pool's included, since a title
    is searched wherever it is sealed; ``parts`` every comment and section with its parent,
    the pending ones with no text. A pending requirement clause passes the fourth property
    here and is read at load; a pending section is still the section its document holds.
    """
    problems: list[IndexProblem] = []
    titled = tuple(titles.items())
    requiring: dict[ClauseId, ScenarioId] = {}
    for scenario in scenarios:
        for fact in scenario.authored_facts:
            if fact.predicate is PredicateName.REQUIRES:
                requiring.setdefault(ClauseId(fact.subject.id), scenario.spec.id)
    targets: dict[ClauseId, list[EntityRef]] = {}
    paired_in: dict[ClauseId, ScenarioId] = {}
    for scenario in scenarios:
        for constraint in scenario.key.constraints:
            paired_in.setdefault(constraint.clause_id, scenario.spec.id)
            held = targets.setdefault(constraint.clause_id, [])
            if constraint.applies_to not in held:
                held.append(constraint.applies_to)

    scope: dict[ClauseId, EntityRef] = {}
    for clause, scenario_id in requiring.items():
        found = targets.get(clause, [])
        if len(found) != 1:
            problems.append(
                IndexProblem(
                    ProblemKind.REQUIREMENT_NOT_SCOPED_ONCE,
                    scenario_id,
                    f"{clause} has {len(found)} scope targets",
                )
            )
            continue
        scope[clause] = found[0]
    for clause, scenario_id in paired_in.items():
        if clause not in requiring:
            problems.append(
                IndexProblem(
                    ProblemKind.SCOPE_WITHOUT_REQUIREMENT,
                    scenario_id,
                    f"{clause} is scoped and states no requirement",
                )
            )

    sections = Counter(part.parent for ref, part in parts.items() if ref.kind is EntityKind.CLAUSE)
    for clause, target in scope.items():
        scenario_id = requiring[clause]
        named = _named_through(target, parts, titles, sections)
        if isinstance(named, IndexProblem):
            problems.append(IndexProblem(named.kind, scenario_id, f"{clause}: {named.detail}"))
            continue
        part = parts.get(clause_ref(clause))
        if part is not None and part.text is None:
            continue
        resolved = () if part is None else resolve_scope(part.text or "", titled)
        if resolved != (named,):
            problems.append(
                IndexProblem(
                    ProblemKind.SCOPE_NOT_STATED_BY_THE_CLAUSE,
                    scenario_id,
                    f"{clause} is scoped to {target.id} and its text names "
                    f"{[artifact.id for artifact in resolved]}",
                )
            )
    return scope, problems


def _named_through(
    target: EntityRef,
    parts: Mapping[EntityRef, ScopePart],
    titles: Mapping[EntityRef, str],
    sections: Mapping[EntityRef, int],
) -> EntityRef | IndexProblem:
    """The titled artifact prose names ``target`` by: itself for a ticket or a meeting, its
    document for a section, which must then be the document's only one."""
    if target.kind is EntityKind.CLAUSE:
        part = parts.get(target)
        if part is None:
            return IndexProblem(ProblemKind.SCOPE_TARGET_NOT_SEALED, None, target.id)
        if sections[part.parent] != 1:
            return IndexProblem(
                ProblemKind.SCOPE_DOCUMENT_NOT_ONE_SECTION,
                None,
                f"{part.parent.id} holds {sections[part.parent]} sections",
            )
        return part.parent
    if target.kind not in TITLED_KINDS:
        return IndexProblem(
            ProblemKind.SCOPE_KIND_HAS_NO_RESOLVER, None, f"{target.id} is a {target.kind.value}"
        )
    if target not in titles:
        return IndexProblem(ProblemKind.SCOPE_TARGET_NOT_SEALED, None, target.id)
    return target


# --- The assembly's reading of a semantic world ---------------------------------------------


def planted_titles(
    scenarios: Sequence[Scenario], filler: Sequence[Planted[Document]] = ()
) -> dict[EntityRef, str]:
    """Every titled record the scenarios plant and the ``filler`` pool adds, by reference."""
    titles: dict[EntityRef, str] = {}
    for scenario in scenarios:
        owned = scenario.owned
        for item in owned.work_items:
            titles[work_item_ref(item.entity.id)] = item.entity.title
        for event in owned.events:
            titles[event_ref(event.entity.id)] = event.entity.title
        for document in owned.documents:
            titles[document_ref(document.entity.id)] = document.entity.title
    for document in filler:
        titles[document_ref(document.entity.id)] = document.entity.title
    return titles


def planted_parts(
    scenarios: Sequence[Scenario],
    filler: Sequence[Planted[Document]] = (),
    filler_briefs: Sequence[Brief] = (),
) -> dict[EntityRef, ScopePart]:
    """Every comment and section of the semantic world: the planted ones with their text, the
    briefed ones with ``None``, under the parent each brief's target names."""
    parts: dict[EntityRef, ScopePart] = {}
    for scenario in scenarios:
        owned = scenario.owned
        for item in owned.work_items:
            for comment in item.entity.comments:
                parts[comment_ref(comment.id)] = ScopePart(
                    work_item_ref(item.entity.id), comment.text
                )
        for document in owned.documents:
            for section in document.entity.sections:
                parts[clause_ref(section.id)] = ScopePart(
                    document_ref(document.entity.id), section.text
                )
        _pending(parts, scenario.briefs)
    for document in filler:
        for section in document.entity.sections:
            parts[clause_ref(section.id)] = ScopePart(
                document_ref(document.entity.id), section.text
            )
    _pending(parts, filler_briefs)
    return parts


def _pending(parts: dict[EntityRef, ScopePart], briefs: Sequence[Brief]) -> None:
    for brief in briefs:
        match brief.target:
            case CommentTarget(id=id, work_item_id=parent):
                parts[comment_ref(id)] = ScopePart(work_item_ref(parent), None)
            case SectionTarget(id=id, document_id=parent):
                parts[clause_ref(id)] = ScopePart(document_ref(parent), None)


__all__ = [
    "IndexProblem",
    "ProblemKind",
    "ScopePart",
    "TITLED_KINDS",
    "planted_parts",
    "planted_titles",
    "resolve_scope",
    "scope_problems",
]
