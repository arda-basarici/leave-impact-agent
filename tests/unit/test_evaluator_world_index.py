"""The world index holds the sealed world by identity, and the scope invariant is read off the
clause's own text: a requirement clause is scoped once, by a pairing that names it, through
a document of one section, and its text names its target once the titles contained in a
longer one are set aside. Each property is shown to fail on a world mutated to break it."""

from collections.abc import Callable
from dataclasses import replace

import pytest

from leaveimpact.core import (
    CalendarEvent,
    ConstraintKey,
    Document,
    DocumentSection,
    EntityKind,
    EntityRef,
    PredicateName,
    WorkItem,
    clause_ref,
    component_ref,
    document_ref,
)
from leaveimpact.core.ids import ClauseId, clause_id
from leaveimpact.evaluator.world_index import (
    IndexProblem,
    ProblemKind,
    WorldIndex,
    index_world,
    record_ref,
    resolve_scope,
    statement_of,
)
from leaveimpact.world import Scenario, WorldSpec
from tests.unit.throwaway_world import composed_world


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return composed_world("golden")


@pytest.fixture(scope="module")
def index(world: WorldSpec) -> WorldIndex:
    built, problems = index_world(world.org, world.scenarios)
    assert problems == ()
    return built


def problems_of(world: WorldSpec, scenarios: tuple[Scenario, ...]) -> tuple[IndexProblem, ...]:
    return index_world(world.org, scenarios)[1]


def kinds(problems: tuple[IndexProblem, ...]) -> list[ProblemKind]:
    return [problem.kind for problem in problems]


# --- Mutations of a sealed world ---------------------------------------------------------


def with_document(
    scenarios: tuple[Scenario, ...], holds: ClauseId, change: Callable[[Document], Document]
) -> tuple[Scenario, ...]:
    """``scenarios`` with the document holding the section ``holds`` changed by ``change``."""
    changed: list[Scenario] = []
    for scenario in scenarios:
        documents = tuple(
            replace(planted, entity=change(planted.entity))
            if any(section.id == holds for section in planted.entity.sections)
            else planted
            for planted in scenario.owned.documents
        )
        changed.append(replace(scenario, owned=replace(scenario.owned, documents=documents)))
    return tuple(changed)


def with_clause_text(
    scenarios: tuple[Scenario, ...], clause: ClauseId, rewrite: Callable[[str], str]
) -> tuple[Scenario, ...]:
    def change(document: Document) -> Document:
        sections = tuple(
            replace(section, text=rewrite(section.text)) if section.id == clause else section
            for section in document.sections
        )
        return replace(document, sections=sections)

    return with_document(scenarios, clause, change)


def with_constraints(
    scenarios: tuple[Scenario, ...],
    owner: Scenario,
    constraints: tuple[ConstraintKey, ...],
) -> tuple[Scenario, ...]:
    return tuple(
        replace(scenario, key=replace(scenario.key, constraints=constraints))
        if scenario.spec.id == owner.spec.id
        else scenario
        for scenario in scenarios
    )


def scoped_by(world: WorldSpec, kind: EntityKind) -> tuple[Scenario, ConstraintKey]:
    """The first scenario holding a constraint whose target is of ``kind``, with it."""
    for scenario in world.scenarios:
        for constraint in scenario.key.constraints:
            if constraint.applies_to.kind is kind:
                return scenario, constraint
    raise AssertionError(f"the golden plan scopes no clause by a {kind.value}")


def title_of(index: WorldIndex, artifact: EntityRef) -> str:
    record = index.records[artifact]
    assert isinstance(record, WorkItem | CalendarEvent | Document)
    return record.title


# --- What the index holds -------------------------------------------------------------------


def test_the_index_holds_every_record_the_organization_and_the_scenarios_seal(
    world: WorldSpec, index: WorldIndex
) -> None:
    sealed = [
        *world.org.teams,
        *world.org.employees,
        *world.org.components,
        *(
            planted.entity
            for scenario in world.scenarios
            for group in (
                scenario.owned.leaves,
                scenario.owned.work_items,
                scenario.owned.events,
                scenario.owned.documents,
            )
            for planted in group
        ),
    ]
    assert len(index.records) == len(sealed)
    assert all(index.records[record_ref(entity)] == entity for entity in sealed)


def test_every_comment_and_section_is_a_part_of_the_record_it_is_read_inside(
    world: WorldSpec, index: WorldIndex
) -> None:
    for scenario in world.scenarios:
        for planted in scenario.owned.documents:
            for section in planted.entity.sections:
                part = index.parts[clause_ref(section.id)]
                assert part.parent == document_ref(planted.entity.id)
                assert part.content == section
    comments = sum(
        len(planted.entity.comments)
        for scenario in world.scenarios
        for planted in scenario.owned.work_items
    )
    sections = sum(
        len(planted.entity.sections)
        for scenario in world.scenarios
        for planted in scenario.owned.documents
    )
    assert len(index.parts) == comments + sections


def test_every_authored_fact_is_carried_by_its_evidence_and_states_one_statement(
    world: WorldSpec, index: WorldIndex
) -> None:
    authored = [fact for scenario in world.scenarios for fact in scenario.authored_facts]
    assert sum(len(facts) for facts in index.carried.values()) == len(authored)
    for fact in authored:
        assert fact in index.carried[fact.evidence.target]
        assert fact.evidence.target in index.statements[statement_of(fact)]
    # World-wide: a carrier is looked up by what it is, never by the scenario that planted it.
    assert set(index.carried) <= set(index.parts)


def test_every_requirement_clause_has_its_scope_and_nothing_else_has_one(
    world: WorldSpec, index: WorldIndex
) -> None:
    pairings = {
        constraint.clause_id: constraint.applies_to
        for scenario in world.scenarios
        for constraint in scenario.key.constraints
    }
    assert dict(index.scope) == pairings
    requiring = {
        fact.subject.id
        for scenario in world.scenarios
        for fact in scenario.authored_facts
        if fact.predicate is PredicateName.REQUIRES
    }
    assert set(index.scope) == requiring
    assert {target.kind for target in index.scope.values()} == {
        EntityKind.WORK_ITEM,
        EntityKind.EVENT,
        EntityKind.CLAUSE,
    }


# --- The clause's text names its target --------------------------------------------------------


def test_titles_contained_in_a_longer_found_title_are_set_aside() -> None:
    plain = (EntityRef(EntityKind.WORK_ITEM, "ticket_001"), "Auth: rotate the keys")
    regional = (
        EntityRef(EntityKind.WORK_ITEM, "ticket_002"),
        "Auth: rotate the keys for the EU region",
    )
    sync = (EntityRef(EntityKind.EVENT, "event_001"), "Platform: sprint review")
    titled = (plain, regional, sync)
    assert resolve_scope("The Auth: rotate the keys release needs Go.", titled) == (plain[0],)
    assert resolve_scope(
        "The Auth: rotate the keys for the EU region release needs Go.", titled
    ) == (regional[0],)
    assert resolve_scope("The release needs Go.", titled) == ()
    # Two titles neither of which contains the other: the text does not state one scope.
    assert resolve_scope(
        "The Auth: rotate the keys release and the Platform: sprint review need Go.", titled
    ) == (plain[0], sync[0])


@pytest.mark.parametrize("kind", [EntityKind.WORK_ITEM, EntityKind.EVENT, EntityKind.CLAUSE])
def test_a_clause_that_stops_naming_its_target_is_reported(
    world: WorldSpec, index: WorldIndex, kind: EntityKind
) -> None:
    _, constraint = scoped_by(world, kind)
    target = constraint.applies_to
    named = index.parts[target].parent if kind is EntityKind.CLAUSE else target
    title = title_of(index, named)
    silent = with_clause_text(
        world.scenarios, constraint.clause_id, lambda text: text.replace(title, "release")
    )
    found = problems_of(world, silent)
    assert kinds(found) == [ProblemKind.SCOPE_NOT_STATED_BY_THE_CLAUSE]
    assert "names []" in found[0].detail


@pytest.mark.parametrize("kind", [EntityKind.WORK_ITEM, EntityKind.EVENT, EntityKind.CLAUSE])
def test_a_clause_naming_another_artifact_is_reported(
    world: WorldSpec, index: WorldIndex, kind: EntityKind
) -> None:
    _, constraint = scoped_by(world, kind)
    target = constraint.applies_to
    named = index.parts[target].parent if kind is EntityKind.CLAUSE else target
    title = title_of(index, named)
    other = next(
        ref
        for ref in index.records
        if ref.kind is named.kind
        and ref != named
        and title not in title_of(index, ref)
        and title_of(index, ref) not in title
    )
    swapped = with_clause_text(
        world.scenarios,
        constraint.clause_id,
        lambda text: text.replace(title, title_of(index, other)),
    )
    found = problems_of(world, swapped)
    assert kinds(found) == [ProblemKind.SCOPE_NOT_STATED_BY_THE_CLAUSE]
    assert f"names ['{other.id}']" in found[0].detail


def test_a_qualified_title_cut_to_the_plain_one_it_contains_names_the_other_ticket(
    world: WorldSpec, index: WorldIndex
) -> None:
    # The case that separates the rule from plain containment: the clause's sealed text
    # holds both titles and resolves to the longer; cut back, it holds only the shorter,
    # which is another ticket's.
    titles = {
        ref: title_of(index, ref) for ref in index.records if ref.kind is EntityKind.WORK_ITEM
    }
    clause, target, shorter = next(
        (clause, target, ref)
        for clause, target in index.scope.items()
        if target.kind is EntityKind.WORK_ITEM
        for ref, title in titles.items()
        if ref != target and title in titles[target]
    )
    sealed_text = index.parts[clause_ref(clause)].content.text
    assert titles[shorter] in sealed_text and titles[target] in sealed_text
    cut = with_clause_text(
        world.scenarios, clause, lambda text: text.replace(titles[target], titles[shorter])
    )
    found = problems_of(world, cut)
    assert kinds(found) == [ProblemKind.SCOPE_NOT_STATED_BY_THE_CLAUSE]
    assert f"names ['{shorter.id}']" in found[0].detail


def test_a_problem_names_ids_and_never_the_clauses_text(
    world: WorldSpec, index: WorldIndex
) -> None:
    _, constraint = scoped_by(world, EntityKind.EVENT)
    title = title_of(index, constraint.applies_to)
    silent = with_clause_text(
        world.scenarios, constraint.clause_id, lambda text: text.replace(title, "release")
    )
    (problem,) = problems_of(world, silent)
    assert "release" not in problem.detail
    assert title not in problem.detail


# --- The pairing is a function of the clause ---------------------------------------------------


def test_a_requirement_clause_with_no_scope_or_with_two_is_reported(world: WorldSpec) -> None:
    owner, constraint = scoped_by(world, EntityKind.WORK_ITEM)
    unscoped = with_constraints(world.scenarios, owner, ())
    assert ProblemKind.REQUIREMENT_NOT_SCOPED_ONCE in kinds(problems_of(world, unscoped))
    _, elsewhere = scoped_by(world, EntityKind.EVENT)
    twice = with_constraints(
        world.scenarios,
        owner,
        (*owner.key.constraints, ConstraintKey(constraint.clause_id, elsewhere.applies_to)),
    )
    assert kinds(problems_of(world, twice)) == [ProblemKind.REQUIREMENT_NOT_SCOPED_ONCE]


def test_a_scope_pairing_whose_clause_states_no_requirement_is_reported(
    world: WorldSpec, index: WorldIndex
) -> None:
    owner, constraint = scoped_by(world, EntityKind.WORK_ITEM)
    no_requirement = next(
        ClauseId(ref.id)
        for ref in index.parts
        if ref.kind is EntityKind.CLAUSE and ClauseId(ref.id) not in index.scope
    )
    extra = with_constraints(
        world.scenarios,
        owner,
        (*owner.key.constraints, ConstraintKey(no_requirement, constraint.applies_to)),
    )
    assert kinds(problems_of(world, extra)) == [ProblemKind.SCOPE_WITHOUT_REQUIREMENT]


def test_a_section_scope_whose_document_holds_two_sections_is_reported(
    world: WorldSpec,
) -> None:
    _, constraint = scoped_by(world, EntityKind.CLAUSE)
    target = ClauseId(constraint.applies_to.id)
    second = DocumentSection(clause_id(999), "A second section, which the title could also mean.")
    two = with_document(
        world.scenarios,
        target,
        lambda document: replace(document, sections=(*document.sections, second)),
    )
    assert kinds(problems_of(world, two)) == [ProblemKind.SCOPE_DOCUMENT_NOT_ONE_SECTION]


def test_a_scope_of_a_kind_no_clause_is_scoped_by_has_no_resolver(world: WorldSpec) -> None:
    owner, constraint = scoped_by(world, EntityKind.WORK_ITEM)
    component = component_ref(world.org.components[0].id)
    rescoped = with_constraints(
        world.scenarios,
        owner,
        tuple(
            ConstraintKey(each.clause_id, component) if each == constraint else each
            for each in owner.key.constraints
        ),
    )
    assert kinds(problems_of(world, rescoped)) == [ProblemKind.SCOPE_KIND_HAS_NO_RESOLVER]


# --- The index's own identity ------------------------------------------------------------------


def test_a_record_or_a_part_sealed_twice_is_reported(world: WorldSpec) -> None:
    found = kinds(problems_of(world, (*world.scenarios, world.scenarios[0])))
    assert ProblemKind.RECORD_SEALED_TWICE in found
    assert set(found) <= {ProblemKind.RECORD_SEALED_TWICE, ProblemKind.PART_SEALED_TWICE}


def test_an_authored_fact_whose_carrier_no_sealed_record_holds_is_reported(
    world: WorldSpec,
) -> None:
    _, constraint = scoped_by(world, EntityKind.WORK_ITEM)
    emptied = with_document(
        world.scenarios, constraint.clause_id, lambda document: replace(document, sections=())
    )
    found = kinds(problems_of(world, emptied))
    assert ProblemKind.CARRIER_NOT_SEALED in found
