"""The sealed world indexed: every record, every part of prose, what each part carries, and what
each requirement clause is scoped to.

A run is graded on what it read, and what it read is checked against what was sealed. Three
questions need the sealed world looked up by identity and not scenario by scenario: is
this returned record the sealed one (observation integrity); does this returned comment
or section carry a fact (a prose fact enters a run's view only through its carrier, read
with the sealed content); which statements move the answer, and where is each stated. The
index is world-wide on purpose. A run of one scenario can read a ticket another scenario
planted, and what that ticket's comment states is true whoever planted it (the
investigator milestone's fourth build step, ruling 1).

*Parts* are the comments and the sections: no read returns one alone, each is read inside
its work item or its document, and each is the unit a fact is carried by. *Carried* maps a
carrier to the sealed authored facts whose evidence it is. *Statements* maps what a fact
says, whatever carries it, to its carriers, since two parts can state one thing and a run
that read either read the statement.

The scope of a requirement is the one thing here that is not a fact. The fact base holds
what a clause requires and nothing about what it applies to; that pairing lives in the
sealed keys. It is admitted into a run's view through the clause, like a fact, and that
is sound only if the pairing is something the clause itself states. Four properties make
it so, and a world failing one is refused whole, since no run of it could be graded on a
scope it had no way to read:

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

Building the index reports problems and refuses nothing: the loader refuses, with a message
that names scenarios and counts, a problem's detail naming ids being truth.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from leaveimpact.core.entities import CalendarEvent, Comment, Document, DocumentSection, WorkItem
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.facts import Fact
from leaveimpact.core.ids import ClauseId, ScenarioId
from leaveimpact.core.ports.observed import KIND_BY_ENTITY_TYPE, Entity
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EntityRef, clause_ref, comment_ref
from leaveimpact.core.values import FactValue
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import Planted, Scenario

Statement = tuple[EntityRef, PredicateName, FactValue]
"""What a fact says, whatever carries it: the subject, the predicate and the value."""


def statement_of(fact: Fact) -> Statement:
    """The statement ``fact`` makes."""
    return (fact.subject, fact.predicate, fact.value)


@dataclass(frozen=True, slots=True)
class SealedPart:
    """A comment or a section as sealed, with the record it is read inside."""

    parent: EntityRef
    content: Comment | DocumentSection


class ProblemKind(StrEnum):
    """What can make a sealed world unreadable as an index; a member names the proof that
    failed."""

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
class WorldIndex:
    """The sealed world by identity. Every mapping is read-only and world-wide.

    ``records`` holds each record a read can return; ``parts`` each comment and section;
    ``carried`` the sealed authored facts of each carrier, a part or a record;
    ``statements`` the carriers of each statement, in reference order; ``scope`` what each
    requirement clause applies to.
    """

    records: Mapping[EntityRef, Entity]
    parts: Mapping[EntityRef, SealedPart]
    carried: Mapping[EntityRef, tuple[Fact, ...]]
    statements: Mapping[Statement, tuple[EntityRef, ...]]
    scope: Mapping[ClauseId, EntityRef]


def index_world(
    org: OrgSpec, scenarios: Sequence[Scenario], filler: Sequence[Planted[Document]] = ()
) -> tuple[WorldIndex, tuple[IndexProblem, ...]]:
    """The index of the world ``scenarios``, ``org`` and the ``filler`` pool make, and every
    problem found building it, in the order found: an empty tuple is the proof the loader
    needs.

    The index is built whatever the problems, the first sealing of an id standing, so that
    a caller measuring a world can count its problems without a refusal. Filler records
    are sealed after every scenario's and owned by none, so a run that reads one returns
    a record the index holds, and the pool's titles join the universe every requirement
    clause's scope is resolved against: a filler title inside a planted clause's text is
    refused here, which is the generator step's second guard at load.
    """
    problems: list[IndexProblem] = []
    records: dict[EntityRef, Entity] = {}
    parts: dict[EntityRef, SealedPart] = {}

    def seal(entity: Entity, scenario_id: ScenarioId | None) -> None:
        ref = record_ref(entity)
        if ref in records:
            problems.append(
                IndexProblem(ProblemKind.RECORD_SEALED_TWICE, scenario_id, f"{ref.id}")
            )
            return
        records[ref] = entity
        for part_ref, content in parts_of(entity):
            if part_ref in parts:
                problems.append(
                    IndexProblem(ProblemKind.PART_SEALED_TWICE, scenario_id, f"{part_ref.id}")
                )
                continue
            parts[part_ref] = SealedPart(ref, content)

    for entity in (*org.teams, *org.employees, *org.components):
        seal(entity, None)
    for scenario in scenarios:
        owned = scenario.owned
        for planted in (*owned.leaves, *owned.work_items, *owned.events, *owned.documents):
            seal(planted.entity, scenario.spec.id)
    for planted in filler:
        seal(planted.entity, None)

    carried: dict[EntityRef, list[Fact]] = {}
    stated: dict[Statement, list[EntityRef]] = {}
    for scenario in scenarios:
        for fact in scenario.authored_facts:
            carrier = fact.evidence.target
            if carrier not in parts and carrier not in records:
                problems.append(
                    IndexProblem(
                        ProblemKind.CARRIER_NOT_SEALED,
                        scenario.spec.id,
                        f"{fact.predicate.value} of {fact.subject.id} on {carrier.id}",
                    )
                )
                continue
            carried.setdefault(carrier, []).append(fact)
            carriers = stated.setdefault(statement_of(fact), [])
            if carrier not in carriers:
                carriers.append(carrier)

    scope, scope_problems = _scope(scenarios, records, parts)
    problems.extend(scope_problems)
    index = WorldIndex(
        records=MappingProxyType(records),
        parts=MappingProxyType(parts),
        carried=MappingProxyType({ref: tuple(facts) for ref, facts in carried.items()}),
        statements=MappingProxyType(
            {
                statement: tuple(sorted(carriers, key=_reference_order))
                for statement, carriers in stated.items()
            }
        ),
        scope=MappingProxyType(scope),
    )
    return index, tuple(problems)


def record_ref(entity: Entity) -> EntityRef:
    """The reference of a record a read returns."""
    return EntityRef(KIND_BY_ENTITY_TYPE[type(entity)], entity.id)


def parts_of(entity: Entity) -> tuple[tuple[EntityRef, Comment | DocumentSection], ...]:
    """The comments of a work item and the sections of a document, each with its reference."""
    if isinstance(entity, WorkItem):
        return tuple((comment_ref(comment.id), comment) for comment in entity.comments)
    if isinstance(entity, Document):
        return tuple((clause_ref(section.id), section) for section in entity.sections)
    return ()


def resolve_scope(
    text: str, titled: Iterable[tuple[EntityRef, str]]
) -> tuple[EntityRef, ...]:
    """The artifacts ``text`` names by title, once the titles contained in a longer found one
    are set aside: one artifact when the text states a scope, none or several when it
    does not.

    >>> from leaveimpact.core.ids import work_item_id
    >>> from leaveimpact.core.refs import work_item_ref
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


_TITLED_KINDS = frozenset({EntityKind.WORK_ITEM, EntityKind.EVENT, EntityKind.DOCUMENT})
"""The kinds a clause is scoped by, each named in prose by its title."""


def _scope(
    scenarios: Sequence[Scenario],
    records: Mapping[EntityRef, Entity],
    parts: Mapping[EntityRef, SealedPart],
) -> tuple[dict[ClauseId, EntityRef], list[IndexProblem]]:
    """Each requirement clause's scope target, and what the four properties find wrong."""
    problems: list[IndexProblem] = []
    titled = tuple(
        (ref, entity.title)
        for ref, entity in records.items()
        if isinstance(entity, WorkItem | CalendarEvent | Document)
    )
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

    for clause, target in scope.items():
        scenario_id = requiring[clause]
        named = _named_through(target, parts, records)
        if isinstance(named, IndexProblem):
            problems.append(IndexProblem(named.kind, scenario_id, f"{clause}: {named.detail}"))
            continue
        sealed = parts.get(clause_ref(clause))
        resolved = () if sealed is None else resolve_scope(_text_of(sealed.content), titled)
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
    target: EntityRef, parts: Mapping[EntityRef, SealedPart], records: Mapping[EntityRef, Entity]
) -> EntityRef | IndexProblem:
    """The titled artifact prose names ``target`` by: itself for a ticket or a meeting, its
    document for a section, which must then be the document's only one."""
    if target.kind is EntityKind.CLAUSE:
        sealed = parts.get(target)
        if sealed is None:
            return IndexProblem(ProblemKind.SCOPE_TARGET_NOT_SEALED, None, target.id)
        document = records[sealed.parent]
        assert isinstance(document, Document)
        if len(document.sections) != 1:
            return IndexProblem(
                ProblemKind.SCOPE_DOCUMENT_NOT_ONE_SECTION,
                None,
                f"{sealed.parent.id} holds {len(document.sections)} sections",
            )
        return sealed.parent
    if target.kind not in _TITLED_KINDS:
        return IndexProblem(
            ProblemKind.SCOPE_KIND_HAS_NO_RESOLVER, None, f"{target.id} is a {target.kind.value}"
        )
    if target not in records:
        return IndexProblem(ProblemKind.SCOPE_TARGET_NOT_SEALED, None, target.id)
    return target


def _text_of(content: Comment | DocumentSection) -> str:
    return content.text


def _reference_order(ref: EntityRef) -> tuple[str, str]:
    return (ref.kind.value, ref.id)


__all__ = [
    "IndexProblem",
    "ProblemKind",
    "SealedPart",
    "Statement",
    "WorldIndex",
    "index_world",
    "parts_of",
    "record_ref",
    "resolve_scope",
    "statement_of",
]
