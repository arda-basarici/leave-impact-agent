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

The scope of a requirement is the one thing here that is not a fact: the pairing lives in the
sealed keys and is admitted through the clause only because the clause's own text states it.
The four properties that make it so, and the matcher that reads them, are the world package's
(``world/scope.py``), run here at load over the sealed records and by the generator at
assembly over the planted ones with the filler pool, one function on both sides (the
generator step's ruling 3). The index builds the titled universe and the parts the matcher
reads and adds its own three sealing problems to the matcher's vocabulary.

Building the index reports problems and refuses nothing: the loader refuses, with a message
that names scenarios and counts, a problem's detail naming ids being truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from leaveimpact.core.entities import CalendarEvent, Comment, Document, DocumentSection, WorkItem
from leaveimpact.core.facts import Fact
from leaveimpact.core.ids import ClauseId, ScenarioId
from leaveimpact.core.ports.observed import KIND_BY_ENTITY_TYPE, Entity
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EntityRef, clause_ref, comment_ref
from leaveimpact.core.values import FactValue
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import Planted, Scenario
from leaveimpact.world.scope import (
    IndexProblem,
    ProblemKind,
    ScopePart,
    resolve_scope,
    scope_problems,
)

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

    titles = {
        ref: entity.title
        for ref, entity in records.items()
        if isinstance(entity, WorkItem | CalendarEvent | Document)
    }
    scope, found = scope_problems(
        scenarios,
        titles,
        {ref: ScopePart(part.parent, part.content.text) for ref, part in parts.items()},
    )
    problems.extend(found)
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
