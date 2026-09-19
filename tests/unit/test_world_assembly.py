"""World assembly: one seed gives one world — organization, plan, slices, scenarios and the
world-level fact base agreeing with each other — equal for equal inputs; and the whole-world
re-verification catches a record one scenario plants that flips another scenario's verdict,
naming the scenario, the candidate and the foreign record with its owner."""

from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.core import (
    AssessmentReason,
    EntityRef,
    LeaveKind,
    LeaveStatus,
    PredicateName,
    Requirement,
    SkillCriterion,
    Verdict,
    clause_ref,
)
from leaveimpact.core.entities import Leave
from leaveimpact.core.ids import leave_id, work_item_id
from leaveimpact.world import (
    DEFAULT_PARAMS,
    GENERATOR_VERSION,
    Minting,
    Planted,
    ReleaseCardinalityConstraint,
    WorldContamination,
    WorldSpec,
    allocate_slices,
    assemble_semantic_world,
    assemble_world,
    construct,
    scope_handle_problems,
    verify_world,
    vocabulary_digest,
    world_fact_base,
)
from leaveimpact.world.plan import GOLDEN_SET_ROWS
from leaveimpact.world.vocabulary import (
    COMPONENT_NAMES,
    LOOK_ALIKE_MEETING_PHRASES,
    LOOK_ALIKE_TICKET_PHRASES,
    MEETING_PHRASES,
    MEETING_QUALIFIERS,
    TEAM_NAMES,
    TICKET_PHRASES,
    TICKET_QUALIFIERS,
    titles,
)

WORLD_START = date(2026, 1, 1)


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return assemble_world(7, DEFAULT_PARAMS, WORLD_START)


def test_one_seed_gives_one_world_with_its_provenance(world: WorldSpec) -> None:
    assert world.seed == 7 and world.org.seed == 7
    assert world.generator_version == GENERATOR_VERSION
    assert world.vocabulary_digest == vocabulary_digest()
    assert world.interpreter == (3, 13)
    assert len(world.scenarios) == 10


def test_plan_slices_and_scenarios_agree(world: WorldSpec) -> None:
    for row, window, scenario in zip(world.plan, world.slices, world.scenarios, strict=True):
        assert scenario.key.scenario_id == row.scenario_id
        assert scenario.key.scenario_class is row.scenario_class
        assert scenario.key.modifiers == row.modifiers
        assert scenario.spec.window == window
    for earlier, later in zip(world.slices, world.slices[1:], strict=False):
        assert earlier.end < later.start


def test_ids_are_minted_world_wide(world: WorldSpec) -> None:
    leaves = [p.entity.id for s in world.scenarios for p in s.owned.leaves]
    assert len(set(leaves)) == len(leaves)
    tickets = [p.entity.id for s in world.scenarios for p in s.owned.work_items]
    assert len(set(tickets)) == len(tickets)


def test_the_fact_base_holds_every_scenario_and_the_world_is_clean(world: WorldSpec) -> None:
    for scenario in world.scenarios:
        assert any(
            f.evidence.target.id == scenario.spec.leave_id for f in world.facts.facts
        )
    assert verify_world(world.facts, world.scenarios, world.org) == ()


def test_the_same_inputs_give_an_equal_world() -> None:
    assert assemble_world(3, DEFAULT_PARAMS, WORLD_START) == assemble_world(
        3, DEFAULT_PARAMS, WORLD_START
    )


def test_a_foreign_record_that_flips_a_verdict_is_named_with_its_owner(world: WorldSpec) -> None:
    # Scenario 2 plants a leave for scenario 1's viable cover over scenario 1's leave: locally
    # both scenarios are fine, together the cover is away and scenario 1's key is wrong.
    first, second = world.scenarios[0], world.scenarios[1]
    (expected, *_) = first.key.impacts
    cover = next(a.employee_id for a in expected.must_assess if a.verdict is Verdict.VIABLE)
    span = first.investigated_leave.span
    foreign = Leave(
        leave_id(999), cover, span.start, span.end, LeaveKind.SICK, LeaveStatus.APPROVED
    )
    planted = Planted(foreign, first.spec.window.start)
    tampered = replace(
        second, owned=replace(second.owned, leaves=(*second.owned.leaves, planted))
    )
    scenarios = (first, tampered, *world.scenarios[2:])
    facts = world_fact_base(world.org, WORLD_START, scenarios)
    findings = verify_world(facts, scenarios, world.org)
    assert findings
    # Observable from the window's start, the foreign leave contaminates both views.
    assert {f.view for f in findings} == {"dated", "runtime"}
    finding = findings[0]
    assert finding.view == "dated"
    assert finding.scenario_id == first.key.scenario_id
    assert finding.subject == cover and finding.expected == "viable"
    assert finding.actual.startswith("non_viable")
    (culprit,) = finding.foreign
    assert culprit.entity_id == "leave_999" and culprit.owner == second.key.scenario_id
    assert culprit.observable_from == first.spec.window.start
    with pytest.raises(WorldContamination, match="leave_999 \\(owned by scenario_002"):
        raise WorldContamination(findings)


def test_a_key_whose_required_sources_no_longer_hold_is_named_with_no_verdict_moved(
    world: WorldSpec,
) -> None:
    # The whole-world check compares the key's required sources with the rule's answer
    # over the assembled world on every stable day, separately from verdicts and outcomes.
    # Under the structured tier's rules no foreign record can move dependence without
    # moving a verdict — the HR record and the tracker are required by every deadline
    # through the leave and the ticket themselves — so the mechanism is pinned on a key
    # whose recorded sources are stale by one; the foreign-fact case joins with the first
    # class whose dependence rests on a source no artifact of its own requires.
    first = world.scenarios[0]
    stale_key = replace(first.key, required_sources=first.key.required_sources[1:])
    stale = replace(first, key=stale_key)
    scenarios = (stale, *world.scenarios[1:])
    findings = verify_world(world.facts, scenarios, world.org)
    assert findings and all(f.subject == "required_sources" for f in findings)
    # Once per stable day under each of the two views.
    assert len(findings) == 2 * first.key.stable_interval.days
    assert {f.view for f in findings} == {"dated", "runtime"}
    finding = findings[0]
    assert finding.scenario_id == first.key.scenario_id
    assert finding.expected == "[" + ", ".join(s.value for s in stale_key.required_sources) + "]"
    assert finding.actual == "[" + ", ".join(s.value for s in first.key.required_sources) + "]"
    assert finding.foreign == ()


def test_a_foreign_undated_ticket_of_the_leaver_is_named_as_an_undeclared_impact(
    world: WorldSpec,
) -> None:
    # Scenario 2 plants an open, undated ticket owned by scenario 1's leaver: no verdict moves,
    # but the assembled world now grounds a responsibility scenario 1's key never declared.
    first, second = world.scenarios[0], world.scenarios[1]
    owned_ticket = first.owned.work_items[0].entity
    assert owned_ticket.owner_id == first.investigated_leave.employee_id
    foreign = replace(owned_ticket, id=work_item_id(999), due_on=None, comments=())
    planted = Planted(foreign, first.spec.window.start)
    tampered = replace(
        second, owned=replace(second.owned, work_items=(*second.owned.work_items, planted))
    )
    scenarios = (first, tampered, *world.scenarios[2:])
    facts = world_fact_base(world.org, WORLD_START, scenarios)
    findings = [f for f in verify_world(facts, scenarios, world.org) if f.subject == "impacts"]
    assert findings
    finding = findings[0]
    assert finding.scenario_id == first.key.scenario_id
    assert finding.artifact_id == "ticket_999" and finding.expected == "not declared"
    assert finding.actual == "a grounded responsibility impact of the leaver"
    (culprit,) = finding.foreign
    assert culprit.entity_id == "ticket_999" and culprit.owner == second.key.scenario_id


# --- Scope handles: a policy names its artifact by title, so the title names one artifact ---


def test_assembly_refuses_a_scope_handle_that_names_two_artifacts_of_its_kind() -> None:
    """The defence behind the title book: a class or helper that titled an artifact past the
    book and collided with a constraint's target is refused by name, whatever the rules say."""
    from random import Random

    from leaveimpact.core.ids import scenario_id

    org = assemble_world(7, DEFAULT_PARAMS, WORLD_START).org
    ids = Minting()
    slices = allocate_slices(Random(0), 2, WORLD_START)
    first, second = (
        construct(
            ReleaseCardinalityConstraint(),
            (),
            org,
            scenario_id=scenario_id(number),
            window=slices[number - 1],
            world_start=WORLD_START,
            reference_timezone=org.params.reference_timezone,
            ids=ids,
            rng=Random(number),
        )
        for number in (1, 2)
    )
    assert scope_handle_problems([first, second]) == []
    stolen = first.owned.work_items[0].entity.title
    [planted] = second.owned.work_items
    collided = replace(
        second,
        owned=replace(
            second.owned,
            work_items=(replace(planted, entity=replace(planted.entity, title=stolen)),),
        ),
    )
    # Both constraints now scope themselves by a title naming two tickets: one problem each.
    problems = scope_handle_problems([first, collided])
    assert [p[: len("scenario_00N")] for p in problems] == ["scenario_001", "scenario_002"]
    assert all(repr(stolen) in p and "names 2 tickets" in p for p in problems)


def test_assembly_refuses_two_runbooks_headed_by_one_ticket_title_with_no_constraint() -> None:
    """A stale-source row carries no constraint: its ticket is named by title only through the
    runbook's brief, and two such rows sharing a release title passed both assembly guards
    (the M1 audit's F-007). The handle check reads the briefs' referents too."""
    from random import Random

    from leaveimpact.core.ids import scenario_id
    from leaveimpact.world import Reservations, StaleSourceConflict
    from leaveimpact.world.adversarial import RUNBOOK_TITLE

    org = assemble_world(7, DEFAULT_PARAMS, WORLD_START).org
    ids, book = Minting(), Reservations()
    slices = allocate_slices(Random(0), 2, WORLD_START)
    first, second = (
        construct(
            StaleSourceConflict(),
            (),
            org,
            scenario_id=scenario_id(number),
            window=slices[number - 1],
            world_start=WORLD_START,
            reference_timezone=org.params.reference_timezone,
            ids=ids,
            rng=Random(number),
            reservations=book,
        )
        for number in (1, 2)
    )
    assert first.key.constraints == () and second.key.constraints == ()
    assert scope_handle_problems([first, second]) == []
    stolen = first.owned.work_items[0].entity.title
    [ticket] = second.owned.work_items
    [runbook] = second.owned.documents
    collided = replace(
        second,
        owned=replace(
            second.owned,
            work_items=(replace(ticket, entity=replace(ticket.entity, title=stolen)),),
            documents=(
                replace(
                    runbook,
                    entity=replace(runbook.entity, title=RUNBOOK_TITLE.format(release=stolen)),
                ),
            ),
        ),
    )
    problems = scope_handle_problems([first, collided])
    assert [p[: len("scenario_00N")] for p in problems] == ["scenario_001", "scenario_002"]
    assert all(
        "names the ticket title" in p and repr(stolen) in p and "names 2 tickets" in p
        for p in problems
    )


def test_every_title_supply_covers_the_golden_set_in_one_context() -> None:
    """Capacity as a tested relationship: a row plants at most one scope-handle artifact of a
    kind, so a context needs at most the golden set's row count of titles."""
    for phrases, qualifiers in (
        (TICKET_PHRASES, TICKET_QUALIFIERS),
        (MEETING_PHRASES, MEETING_QUALIFIERS),
        (LOOK_ALIKE_TICKET_PHRASES, TICKET_QUALIFIERS),
        (LOOK_ALIKE_MEETING_PHRASES, MEETING_QUALIFIERS),
    ):
        supply = titles("x", phrases, qualifiers)
        assert len(supply) == len(set(supply)) >= GOLDEN_SET_ROWS


def test_unique_per_kind_is_the_whole_resolver_contract() -> None:
    """Ticket titles carry a component name and meeting titles a team name from disjoint
    tables, real and look-alike phrases are disjoint, and no qualifier begins with the comma
    the modifiers' derived suffixes begin with: so a title names one artifact across kinds
    and across distractors once it names one within its kind."""
    assert not set(TEAM_NAMES) & set(COMPONENT_NAMES)
    assert not set(TICKET_PHRASES) & set(LOOK_ALIKE_TICKET_PHRASES)
    assert not set(MEETING_PHRASES) & set(LOOK_ALIKE_MEETING_PHRASES)
    assert all(not q.startswith(",") for q in TICKET_QUALIFIERS + MEETING_QUALIFIERS)
    assert "" in TICKET_QUALIFIERS and "" in MEETING_QUALIFIERS


@pytest.mark.parametrize("seed", range(1, 9))
def test_the_twenty_row_plan_assembles_under_the_reservation_book(seed: int) -> None:
    """The world the golden set's two tiers make: every prose class beside every other row,
    the reservation book admitting a construction for every row and the whole-world
    re-verification passing behind it, with no scope handle naming two artifacts of its
    kind (the 15.3 regression, re-pointed here). Eight seeds in the suite at about three
    seconds each; the two-hundred-seed sweep is recorded in FINDINGS (`reservation-book`)."""
    world = assemble_semantic_world(seed, DEFAULT_PARAMS, WORLD_START, "tier1-plus-tier2")
    assert len(world.scenarios) == 20
    assert scope_handle_problems(world.scenarios) == []
    # The book's two rules, read back off the assembled world: no person one scenario names
    # responsible is the leave subject of another, and no (person, skill) one scenario
    # evidences in prose is assumed absent by another's verdict.
    contacts: dict[str, str] = {}
    provided: set[tuple[str, str]] = set()
    assumed_absent: set[tuple[str, str]] = set()
    for scenario in world.scenarios:
        stated = {
            fact.subject: fact.value
            for fact in scenario.authored_facts
            if fact.predicate is PredicateName.REQUIRES and isinstance(fact.value, Requirement)
        }
        for fact in scenario.authored_facts:
            names = fact.predicate is PredicateName.NAMES_RESPONSIBLE
            if names and isinstance(fact.value, EntityRef):
                contacts.setdefault(fact.value.id, scenario.spec.id)
            elif fact.predicate is PredicateName.HAS_SKILL and isinstance(fact.value, str):
                provided.add((fact.subject.id, fact.value))
        for expected in scenario.key.impacts:
            skills = [
                criterion.skill
                for constraint in scenario.key.constraints
                if constraint.applies_to == expected.key.artifact
                for criterion in stated[clause_ref(constraint.clause_id)].criteria
                if isinstance(criterion, SkillCriterion)
            ]
            for authored in expected.must_assess:
                failing = authored.verdict is Verdict.NON_VIABLE
                if failing and AssessmentReason.SKILL in authored.reasons:
                    assumed_absent.update((authored.employee_id, skill) for skill in skills)
    for scenario in world.scenarios:
        leaver = scenario.owned.leaves[0].entity.employee_id
        assert contacts.get(leaver) in (None, scenario.spec.id)
    assert provided.isdisjoint(assumed_absent)
