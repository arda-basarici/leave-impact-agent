"""The adversarial tier's classes: each scenario has the shape its class promises, the key seals
the conclusions the class exists to produce, and no admissible modifier erases them."""

from __future__ import annotations

from datetime import date, datetime
from itertools import combinations
from random import Random
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.core import (
    AssessmentReason,
    DocumentKind,
    EntityRef,
    Fact,
    ImpactSubtype,
    PredicateName,
    Source,
    Verdict,
    employee_ref,
    work_item_ref,
)
from leaveimpact.core.claims import AuthorityRule, CoverageActionKind, UnknownReason
from leaveimpact.core.ids import scenario_id
from leaveimpact.core.values import Requirement, SkillCriterion
from leaveimpact.world import (
    COMPATIBLE_MODIFIERS,
    DEFAULT_PARAMS,
    MODIFIERS,
    ConcurrentLeave,
    Draft,
    Frame,
    Minting,
    MissingInformation,
    Modifier,
    ModifierName,
    Register,
    Scenario,
    ScenarioClass,
    SectionTarget,
    StaleSourceConflict,
    StructuredDeadline,
    Uncovered,
    allocate_slices,
    construct,
    generate_org,
    unknown_skill_pairs,
)
from leaveimpact.world.adversarial import RELEASE_SKILL_CLAUSE, RUNBOOK_TITLE, unheld_skill
from leaveimpact.world.fragmented import SKILL_NAMES
from leaveimpact.world.prose import FactRole

ORG = generate_org(7, DEFAULT_PARAMS)
WORLD_START = date(2026, 1, 1)
SLICES = allocate_slices(Random(0), 30, WORLD_START)
TZ = ORG.params.reference_timezone
SEEDS = range(1, 21)
CONFLICT = StaleSourceConflict()
MISSING = MissingInformation()
UNCOVERED = Uncovered()
BLANK = {e.id for e in ORG.employees if e.skills is None}
BY_ID = {employee.id: employee for employee in ORG.employees}


def _scenario(
    seed: int, modifiers: tuple[Modifier, ...] = (), scenario_class: ScenarioClass = CONFLICT
) -> Scenario:
    return construct(
        scenario_class,
        modifiers,
        ORG,
        scenario_id=scenario_id(seed),
        window=SLICES[seed % len(SLICES)],
        world_start=WORLD_START,
        reference_timezone=TZ,
        ids=Minting(),
        rng=Random(seed),
    )


# --- stale_source_conflict --------------------------------------------------------------


def test_the_conflict_class_affords_exactly_the_deadline_cast() -> None:
    # The same constructions in the same canonical order: the class adds a section to the
    # deadline shape and changes nothing about who is cast.
    assert len(CONFLICT.admissible(ORG)) == len(StructuredDeadline().admissible(ORG))
    assert CONFLICT.affordance == StructuredDeadline.affordance


@pytest.mark.parametrize("seed", SEEDS)
def test_the_conflict_scenario_has_the_shape_the_class_promises(seed: int) -> None:
    scenario = _scenario(seed)
    leave = scenario.investigated_leave
    [ticket] = scenario.owned.work_items
    [runbook] = scenario.owned.documents
    (expected,) = scenario.key.impacts
    assert expected.key.subtype is ImpactSubtype.DEADLINE
    assert expected.key.artifact == work_item_ref(ticket.entity.id)
    assert ticket.entity.owner_id == leave.employee_id
    assert leave.span.contains(ticket.entity.due_on or date.min)
    # The runbook is the release's, titled by the ticket the book minted once per component.
    assert runbook.entity.kind is DocumentKind.RUNBOOK
    assert runbook.entity.title == RUNBOOK_TITLE.format(release=ticket.entity.title)
    assert runbook.entity.sections == ()  # the model's section, filled at materialization
    # The deadline cast, unchanged: the cover viable inside, the outsider failing by component.
    cover, outsider = expected.must_assess
    assert cover.verdict is Verdict.VIABLE
    assert outsider.verdict is Verdict.NON_VIABLE
    assert outsider.reasons == (AssessmentReason.COMPONENT,)
    component = next(c for c in ORG.components if c.id == ticket.entity.component_id)
    assert cover.employee_id in component.member_ids
    assert outsider.employee_id not in component.member_ids
    assert BY_ID[outsider.employee_id].team_id == BY_ID[leave.employee_id].team_id
    # The stale fact: the outsider owns the ticket, evidenced by the runbook's section.
    [stale] = scenario.authored_facts
    assert stale.predicate is PredicateName.OWNS_WORK_ITEM
    assert stale.subject == work_item_ref(ticket.entity.id)
    assert stale.value == employee_ref(outsider.employee_id)
    assert stale.evidence.source is Source.CORPUS


@pytest.mark.parametrize("seed", SEEDS)
def test_the_key_seals_one_conflict_resolved_to_the_tracker_and_nothing_unknown(
    seed: int,
) -> None:
    scenario = _scenario(seed)
    [ticket] = scenario.owned.work_items
    [conflict] = scenario.key.expected_conflicts
    assert conflict.entity == work_item_ref(ticket.entity.id)
    assert conflict.predicate is PredicateName.OWNS_WORK_ITEM
    assert conflict.resolved_value == employee_ref(scenario.investigated_leave.employee_id)
    assert conflict.authority_rule is AuthorityRule.SYSTEM_OF_RECORD_WINS
    # No clause asks a skill, so the blank records are viable or fail by component: no unknown.
    assert scenario.key.expected_unknowns == ()


@pytest.mark.parametrize("seed", SEEDS)
def test_the_section_carries_the_stale_fact_alone_and_it_is_answer_changing(seed: int) -> None:
    """One required fact, no allowed context, the runbook register; the fact moves no verdict
    and no outcome, and is answer-changing through the conflict the key expects."""
    scenario = _scenario(seed)
    [brief] = scenario.briefs
    [runbook] = scenario.owned.documents
    assert isinstance(brief.target, SectionTarget) and brief.register is Register.RUNBOOK
    assert brief.target.document_id == runbook.entity.id and brief.target.position == 0
    [required] = brief.required
    assert required.fact.predicate is PredicateName.OWNS_WORK_ITEM
    assert required.role is FactRole.ANSWER_CHANGING
    assert brief.allowed == ()
    # The entity list names the ticket and the outsider, the two things the text must say.
    [ticket] = scenario.owned.work_items
    _, outsider = scenario.key.impacts[0].must_assess
    named = {(form.kind, form.id) for form in brief.namespace.forms}
    assert {("work_item", ticket.entity.id), ("employee", outsider.employee_id)} <= named
    assert isinstance(required.fact.value, EntityRef)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_conflict_key_requires_the_record_the_tracker_and_the_corpus(seed: int) -> None:
    # The leave, the impact, and the conflict: the corpus is required because the conflict
    # vanishes without it, not because it hosts a distractor.
    assert set(_scenario(seed).key.required_sources) == {Source.FRAPPE, Source.JIRA, Source.CORPUS}


def test_the_same_conflict_inputs_give_an_equal_scenario() -> None:
    assert _scenario(3) == _scenario(3)


ADMISSIBLE_PAIRS = [
    (MODIFIERS[first], MODIFIERS[second])
    for first, second in combinations(sorted(COMPATIBLE_MODIFIERS[CONFLICT.name]), 2)
]


@pytest.mark.parametrize(
    ("first", "second"),
    ADMISSIBLE_PAIRS,
    ids=[f"{a.name.value}+{b.name.value}" for a, b in ADMISSIBLE_PAIRS],
)
def test_every_admissible_pair_preserves_the_expected_conflict(
    first: Modifier, second: Modifier
) -> None:
    # Compatibility means more than the outcome surviving (the 15.5 rulings): a composition
    # that erased the section or the tracker fact would move the sealed conflict, and
    # construction's exact check would refuse it; here the sealed set is read back as well.
    for seed in range(1, 11):
        scenario = _scenario(seed, (first, second))
        assert len(scenario.key.expected_conflicts) == 1
        assert scenario.key.impacts[0].outcome.value == "assign"


# --- missing_information and uncovered -------------------------------------------------


def _clause_fact(scenario: Scenario) -> Fact:
    [requires] = scenario.authored_facts
    assert requires.predicate is PredicateName.REQUIRES
    return requires


def _required_skill(scenario: Scenario) -> object:
    requirement = _clause_fact(scenario).value
    assert isinstance(requirement, Requirement)
    [criterion] = requirement.criteria
    assert isinstance(criterion, SkillCriterion)
    return criterion.skill


@pytest.mark.parametrize("seed", range(1, 41))
def test_every_organization_affords_both_placements(seed: int) -> None:
    # The org guarantees: exactly one blank-record member in the first component, none in the
    # cardinality cast's, and a skill nobody holds.
    org = generate_org(seed, DEFAULT_PARAMS)
    assert MISSING.admissible(org) and UNCOVERED.admissible(org)
    assert not org.holders_of(unheld_skill(org))


@pytest.mark.parametrize("seed", SEEDS)
def test_the_missing_information_scenario_has_the_shape_the_class_promises(seed: int) -> None:
    scenario = _scenario(seed, scenario_class=MISSING)
    leave = scenario.investigated_leave
    [ticket] = scenario.owned.work_items
    [policy] = scenario.owned.documents
    (expected,) = scenario.key.impacts
    assert expected.outcome is CoverageActionKind.UNKNOWN
    assert ticket.entity.owner_id == leave.employee_id and leave.employee_id not in BLANK
    assert leave.span.contains(ticket.entity.due_on or date.min)
    component = next(c for c in ORG.components if c.id == ticket.entity.component_id)
    assert len(BLANK & set(component.member_ids)) == 1
    unknown, failing = expected.must_assess
    assert unknown.verdict is Verdict.UNKNOWN and unknown.reasons == ()
    assert unknown.employee_id in BLANK and unknown.employee_id in component.member_ids
    assert failing.verdict is Verdict.NON_VIABLE and failing.reasons == (AssessmentReason.SKILL,)
    assert failing.employee_id in component.member_ids and failing.employee_id not in BLANK
    # The clause names the release and requires the skill nobody holds.
    assert _required_skill(scenario) == unheld_skill(ORG)
    [section] = policy.entity.sections
    assert section.text == RELEASE_SKILL_CLAUSE.format(
        release=ticket.entity.title, skill=SKILL_NAMES[unheld_skill(ORG)]
    )
    [constraint] = scenario.key.constraints
    assert constraint.clause_id == section.id
    assert constraint.applies_to == work_item_ref(ticket.entity.id)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_missing_information_key_seals_exactly_the_one_unknown(seed: int) -> None:
    # Every other blank record fails by component, a known failure dominating the open
    # question, so the complete derived set is the one the class asserted.
    scenario = _scenario(seed, scenario_class=MISSING)
    (expected,) = scenario.key.impacts
    unknown, _ = expected.must_assess
    [sealed] = scenario.key.expected_unknowns
    assert sealed.employee_id == unknown.employee_id
    assert sealed.subject == employee_ref(unknown.employee_id)
    assert sealed.required_fact is PredicateName.HAS_SKILL
    assert sealed.reason is UnknownReason.ABSENT
    assert scenario.key.expected_conflicts == ()


def test_the_missing_information_unknown_is_an_absence_claim_on_the_book() -> None:
    plant = MISSING.admissible(ORG)[0]
    now = datetime(2026, 3, 3, 9, tzinfo=ZoneInfo(TZ))
    window = SLICES[3]
    frame = Frame(scenario_id(1), window, window, now, TZ, WORLD_START, Minting())
    draft = plant(frame, Random(1))
    [required] = draft.required_unknowns
    pairs = unknown_skill_pairs(draft, ORG, WORLD_START, frame)
    assert pairs == {(required.employee_id, unheld_skill(ORG))}


@pytest.mark.parametrize("seed", SEEDS)
def test_the_uncovered_scenario_has_the_shape_the_class_promises(seed: int) -> None:
    scenario = _scenario(seed, scenario_class=UNCOVERED)
    leave = scenario.investigated_leave
    [ticket] = scenario.owned.work_items
    (expected,) = scenario.key.impacts
    assert expected.outcome is CoverageActionKind.UNCOVERED
    component = next(c for c in ORG.components if c.id == ticket.entity.component_id)
    assert not BLANK & set(component.member_ids)
    failing, outsider, blank_outsider = expected.must_assess
    assert failing.reasons == (AssessmentReason.SKILL,)
    assert failing.employee_id in component.member_ids
    assert outsider.reasons == (AssessmentReason.COMPONENT, AssessmentReason.SKILL)
    assert outsider.employee_id not in component.member_ids and outsider.employee_id not in BLANK
    assert BY_ID[outsider.employee_id].team_id == BY_ID[leave.employee_id].team_id
    # The dominance rule made visible: a blank record outside fails by component alone, the
    # skill question their record cannot answer dominated, never unknown.
    assert blank_outsider.reasons == (AssessmentReason.COMPONENT,)
    assert blank_outsider.employee_id in BLANK
    assert scenario.key.expected_unknowns == ()
    assert scenario.key.expected_conflicts == ()
    assert _required_skill(scenario) == unheld_skill(ORG)


@pytest.mark.parametrize("scenario_class", [MISSING, UNCOVERED], ids=["missing", "uncovered"])
@pytest.mark.parametrize("seed", SEEDS)
def test_the_pair_requires_the_record_the_tracker_and_the_corpus(
    seed: int, scenario_class: ScenarioClass
) -> None:
    # A skill known false needs every source in the predicate's domain answered.
    scenario = _scenario(seed, scenario_class=scenario_class)
    assert set(scenario.key.required_sources) == {Source.FRAPPE, Source.JIRA, Source.CORPUS}


@pytest.mark.parametrize("scenario_class", [MISSING, UNCOVERED], ids=["missing", "uncovered"])
def test_the_same_pair_inputs_give_an_equal_scenario(scenario_class: ScenarioClass) -> None:
    assert _scenario(3, scenario_class=scenario_class) == _scenario(
        3, scenario_class=scenario_class
    )


@pytest.mark.parametrize("scenario_class", [MISSING, UNCOVERED], ids=["missing", "uncovered"])
def test_a_concurrent_leave_has_nothing_to_send_away_in_the_pair(
    scenario_class: ScenarioClass,
) -> None:
    assert ModifierName.CONCURRENT_LEAVE not in COMPATIBLE_MODIFIERS[scenario_class.name]
    scenario = _scenario(1, scenario_class=scenario_class)
    draft = Draft(scenario.owned, scenario.spec.leave_id, scenario.key.impacts)
    assert ConcurrentLeave().admissible(ORG, draft) == ()


MISSING_PAIRS = [
    (MODIFIERS[first], MODIFIERS[second])
    for first, second in combinations(sorted(COMPATIBLE_MODIFIERS[MISSING.name]), 2)
]


@pytest.mark.parametrize(
    ("first", "second"),
    MISSING_PAIRS,
    ids=[f"{a.name.value}+{b.name.value}" for a, b in MISSING_PAIRS],
)
def test_every_admissible_pair_keeps_the_one_unknown_and_the_unknown_outcome(
    first: Modifier, second: Modifier
) -> None:
    for seed in range(1, 11):
        scenario = _scenario(seed, (first, second), MISSING)
        assert len(scenario.key.expected_unknowns) == 1
        assert scenario.key.impacts[0].outcome is CoverageActionKind.UNKNOWN
