"""The fragmented tier's two primitives over a sweep of seeds: the shape each class promises,
the canonical affordance order and determinism.

The qualification class: a meeting under a scenario-owned skill clause, the viable cover's
skill carried only by a comment brief that derives as answer-changing, a second candidate
failing the skill. The responsibility class: a client note's section, left to a model,
naming the leaver as the contact under a procedure clause requiring a skill of the contact,
one candidate viable on the HR record and one failing by skill; its key requires the tracker
with no tracker artifact, because required-source derivation is semantic rather than
provenance-based (DESIGN, the 15.2 interview's second ruling, where the probe and the
argument for why no silent-drift test exists are recorded).
"""

from datetime import date
from random import Random

import pytest

from leaveimpact.core import (
    AssessmentReason,
    DocumentKind,
    EmploymentType,
    EntityRef,
    ImpactSubtype,
    PredicateName,
    RunCondition,
    Source,
    Verdict,
    assess_impact,
    clause_ref,
    event_ref,
    work_item_ref,
)
from leaveimpact.core.ids import SkillId, scenario_id
from leaveimpact.core.values import EmploymentTypeCriterion, Requirement, SkillCriterion
from leaveimpact.world import (
    DEFAULT_PARAMS,
    Frame,
    FreeTextQualification,
    FreeTextResponsibility,
    Minting,
    Register,
    ReleaseCardinalityConstraint,
    Scenario,
    SectionTarget,
    allocate_slices,
    construct,
    generate_org,
    place_leave,
    place_now,
)
from leaveimpact.world.fragmented import (
    NOTE_TITLE,
    POLICY_CLAUSE,
    PROCEDURE_CLAUSE,
    SKILL_NAMES,
    client_of,
)
from leaveimpact.world.prose import FactRole
from leaveimpact.world.truth_facts import truth_fact_base
from leaveimpact.world.vocabulary import CLIENT_NAMES

ORG = generate_org(7, DEFAULT_PARAMS)
WORLD_START = date(2026, 1, 1)
SLICES = allocate_slices(Random(0), 30, WORLD_START)
TZ = ORG.params.reference_timezone
SEEDS = range(1, 21)
QUALIFICATION = FreeTextQualification()
RESPONSIBILITY = FreeTextResponsibility()
CARDINALITY = ReleaseCardinalityConstraint()
BY_ID = {employee.id: employee for employee in ORG.employees}


FragmentedClass = FreeTextQualification | FreeTextResponsibility | ReleaseCardinalityConstraint


def _scenario(seed: int, scenario_class: FragmentedClass = QUALIFICATION) -> Scenario:
    return construct(
        scenario_class,
        (),
        ORG,
        scenario_id=scenario_id(seed),
        window=SLICES[seed % len(SLICES)],
        world_start=WORLD_START,
        reference_timezone=TZ,
        ids=Minting(),
        rng=Random(seed),
    )


def test_the_org_affords_the_class_in_a_canonical_order() -> None:
    first, second = QUALIFICATION.admissible(ORG), QUALIFICATION.admissible(ORG)
    assert first and len(first) == len(second)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_scenario_has_the_shape_the_class_promises(seed: int) -> None:
    scenario = _scenario(seed)
    [expected] = scenario.key.impacts
    assert expected.key.subtype is ImpactSubtype.MEETING
    [meeting] = scenario.owned.events
    assert expected.key.artifact == event_ref(meeting.entity.id)
    [constraint] = scenario.key.constraints
    assert constraint.applies_to == event_ref(meeting.entity.id)
    [policy] = scenario.owned.documents
    assert policy.entity.kind is DocumentKind.POLICY
    [section] = policy.entity.sections
    assert section.id == constraint.clause_id and meeting.entity.title in section.text
    viable, failing = expected.must_assess
    assert viable.verdict is Verdict.VIABLE
    assert failing.verdict is Verdict.NON_VIABLE and failing.reasons == (AssessmentReason.SKILL,)
    [brief] = scenario.briefs
    assert brief.register is Register.TICKET_COMMENT
    [required] = brief.required
    assert required.fact.predicate is PredicateName.HAS_SKILL
    assert required.fact.subject.id == viable.employee_id
    assert required.role is FactRole.ANSWER_CHANGING
    [ticket] = scenario.owned.work_items
    assert ticket.entity.owner_id == viable.employee_id
    owns, in_component = brief.allowed
    assert owns.predicate is PredicateName.OWNS_WORK_ITEM
    assert in_component.predicate is PredicateName.IN_COMPONENT
    assert owns.subject.id == ticket.entity.id
    assert isinstance(owns.value, EntityRef) and owns.value.id == viable.employee_id
    assert {Source.CALENDAR, Source.FRAPPE, Source.JIRA, Source.CORPUS} <= set(
        scenario.key.required_sources
    )


def test_the_same_inputs_give_an_equal_scenario() -> None:
    assert _scenario(3) == _scenario(3)


def test_the_clause_names_the_meeting_it_applies_to() -> None:
    assert "{meeting}" in POLICY_CLAUSE and "{skill}" in POLICY_CLAUSE
    scenario = _scenario(5)
    [policy] = scenario.owned.documents
    [constraint] = scenario.key.constraints
    assert clause_ref(policy.entity.sections[0].id) == clause_ref(constraint.clause_id)


# --- The responsibility class -----------------------------------------------------------


def test_the_org_affords_the_responsibility_class_in_a_canonical_order() -> None:
    first, second = RESPONSIBILITY.admissible(ORG), RESPONSIBILITY.admissible(ORG)
    assert first and len(first) == len(second)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_responsibility_scenario_has_the_shape_the_class_promises(seed: int) -> None:
    scenario = _scenario(seed, RESPONSIBILITY)
    [expected] = scenario.key.impacts
    assert expected.key.subtype is ImpactSubtype.RESPONSIBILITY
    [brief] = scenario.briefs
    assert isinstance(brief.target, SectionTarget) and brief.register is Register.CLIENT_NOTE
    section = clause_ref(brief.target.id)
    assert expected.key.artifact == section
    [constraint] = scenario.key.constraints
    assert constraint.applies_to == section
    note, procedure = scenario.owned.documents
    assert note.entity.kind is DocumentKind.CLIENT_NOTE and note.entity.sections == ()
    assert brief.target.document_id == note.entity.id and brief.target.position == 0
    assert procedure.entity.kind is DocumentKind.PROCEDURE
    [clause] = procedure.entity.sections
    assert clause.id == constraint.clause_id and note.entity.title in clause.text
    viable, failing = expected.must_assess
    assert viable.verdict is Verdict.VIABLE
    assert failing.verdict is Verdict.NON_VIABLE and failing.reasons == (AssessmentReason.SKILL,)
    [required] = brief.required
    assert required.fact.predicate is PredicateName.NAMES_RESPONSIBLE
    assert required.fact.subject == section
    leaver = scenario.owned.leaves[0].entity.employee_id
    assert isinstance(required.fact.value, EntityRef) and required.fact.value.id == leaver
    assert required.role is FactRole.ANSWER_CHANGING
    assert brief.allowed == ()
    # The skill is structured on every side: the leaver and the viable candidate hold it on
    # the record, the failing candidate's record lacks it, and no skill word reaches the
    # writer, whose namespace is the note's title, its client and the contact's name.
    skill = _required_skill(scenario)
    assert skill in (BY_ID[leaver].skills or ())
    assert skill in (BY_ID[viable.employee_id].skills or ())
    assert skill not in (BY_ID[failing.employee_id].skills or ())
    assert SKILL_NAMES[skill] in clause.text
    assert {form.form for form in brief.namespace.forms} == {
        note.entity.title,
        client_of(scenario_id(seed)),
        BY_ID[leaver].name,
        BY_ID[leaver].name.split()[0],
    }


def _required_skill(scenario: Scenario) -> SkillId:
    [requires] = [f for f in scenario.authored_facts if f.predicate is PredicateName.REQUIRES]
    assert isinstance(requires.value, Requirement)
    [criterion] = [c for c in requires.value.criteria if isinstance(c, SkillCriterion)]
    return criterion.skill


@pytest.mark.parametrize("seed", SEEDS)
def test_the_key_requires_the_tracker_the_scenario_plants_nothing_in(seed: int) -> None:
    # Required-source derivation is semantic, not provenance-based: the failing candidate is
    # known not to hold the skill only because the tracker answered, a skill in a comment
    # being in the predicate's domain, so the tracker is required by a scenario that owns
    # no ticket and no comment. An implementation that read required sources off owned
    # artifacts would drop it (DESIGN, the 15.2 interview's second ruling).
    scenario = _scenario(seed, RESPONSIBILITY)
    assert scenario.owned.work_items == () and scenario.owned.events == ()
    assert set(scenario.key.required_sources) == {Source.CORPUS, Source.FRAPPE, Source.JIRA}


def test_the_same_responsibility_inputs_give_an_equal_scenario() -> None:
    assert _scenario(3, RESPONSIBILITY) == _scenario(3, RESPONSIBILITY)


# --- release_cardinality_constraint ------------------------------------------------------


def test_the_org_affords_the_cardinality_class_in_a_canonical_order() -> None:
    first, second = CARDINALITY.admissible(ORG), CARDINALITY.admissible(ORG)
    # Two constructions per seated paired skill: each filler the leaver in turn.
    assert first and len(first) % 2 == 0 and len(first) == len(second)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_cardinality_scenario_has_the_shape_the_class_promises(seed: int) -> None:
    scenario = _scenario(seed, CARDINALITY)
    [expected] = scenario.key.impacts
    [ticket] = scenario.owned.work_items
    assert expected.key.subtype is ImpactSubtype.DEADLINE
    assert expected.key.artifact == work_item_ref(ticket.entity.id)
    leaver = scenario.owned.leaves[0].entity.employee_id
    assert ticket.entity.owner_id == leaver
    assert ticket.entity.due_on is not None
    assert scenario.owned.leaves[0].entity.span.contains(ticket.entity.due_on)
    [constraint] = scenario.key.constraints
    assert constraint.applies_to == work_item_ref(ticket.entity.id)
    [policy] = scenario.owned.documents
    assert policy.entity.kind is DocumentKind.POLICY
    [clause] = policy.entity.sections
    assert clause.id == constraint.clause_id
    assert ticket.entity.title in policy.entity.title and ticket.entity.title in clause.text
    [requires] = scenario.authored_facts
    assert isinstance(requires.value, Requirement) and requires.value.count == 2
    skill = _required_skill(scenario)
    assert EmploymentTypeCriterion(EmploymentType.EMPLOYEE) in requires.value.criteria
    assert SKILL_NAMES[skill] in clause.text and "two" in clause.text
    first, second, contractor, failing = expected.must_assess
    assert (first.verdict, second.verdict) == (Verdict.VIABLE, Verdict.VIABLE)
    assert contractor.verdict is Verdict.NON_VIABLE
    assert contractor.reasons == (AssessmentReason.HARD_RULE,)
    assert failing.verdict is Verdict.NON_VIABLE and failing.reasons == (AssessmentReason.SKILL,)
    assert BY_ID[contractor.employee_id].employment_type is EmploymentType.CONTRACTOR
    for holder in (first, second, contractor):
        assert skill in (BY_ID[holder.employee_id].skills or ())
    for lacking in (failing.employee_id, leaver):
        assert BY_ID[lacking].skills is not None and skill not in (BY_ID[lacking].skills or ())
        assert BY_ID[lacking].employment_type is EmploymentType.EMPLOYEE
    component = next(c for c in ORG.components if c.id == ticket.entity.component_id)
    cast = {leaver, *(authored.employee_id for authored in expected.must_assess)}
    assert set(component.member_ids) == cast
    assert scenario.briefs == ()
    assert expected.outcome.value == "assign"


def test_every_cardinality_construction_has_exactly_two_viable_people() -> None:
    """The count is visibly load-bearing (the 15.3 ruling): over every admissible
    construction the rules find exactly the two employee holders viable for the release,
    which the outcome check alone does not pin (assign holds with three as well)."""
    for index, construction in enumerate(CARDINALITY.admissible(ORG)):
        rng = Random(index)
        window = SLICES[index % len(SLICES)]
        leave = place_leave(rng, window)
        frame = Frame(
            scenario_id(index + 1),
            window,
            leave,
            place_now(rng, leave, TZ),
            TZ,
            WORLD_START,
            Minting(),
        )
        draft = construction(frame, rng)
        [expected] = draft.impacts
        base = truth_fact_base(ORG, WORLD_START, [draft.owned], draft.authored_facts)
        view = base.at(frame.now.date(), RunCondition.all_reachable())
        universe = [employee.id for employee in ORG.employees]
        assessments = assess_impact(
            view, expected.key, universe, draft.constraints, frame.leave, TZ
        )
        viable = {a.employee_id for a in assessments if a.verdict is Verdict.VIABLE}
        authored_viable = {
            a.employee_id for a in expected.must_assess if a.verdict is Verdict.VIABLE
        }
        assert viable == authored_viable and len(viable) == 2


@pytest.mark.parametrize("seed", SEEDS)
def test_the_cardinality_key_requires_the_three_sources_its_artifacts_and_rules_read(
    seed: int,
) -> None:
    scenario = _scenario(seed, CARDINALITY)
    assert set(scenario.key.required_sources) == {Source.CORPUS, Source.FRAPPE, Source.JIRA}


def test_the_same_cardinality_inputs_give_an_equal_scenario() -> None:
    assert _scenario(3, CARDINALITY) == _scenario(3, CARDINALITY)


def test_the_client_is_one_name_per_scenario_number_across_a_golden_world() -> None:
    assert "{client}" in NOTE_TITLE and "{client}" in PROCEDURE_CLAUSE
    assert len(set(CLIENT_NAMES)) == len(CLIENT_NAMES) >= 30
    assert client_of(scenario_id(1)) == CLIENT_NAMES[0]
    assert client_of(scenario_id(len(CLIENT_NAMES))) == CLIENT_NAMES[-1]
    assert client_of(scenario_id(len(CLIENT_NAMES) + 1)) == CLIENT_NAMES[0]
    titles = {_scenario(seed, RESPONSIBILITY).owned.documents[0].entity.title for seed in SEEDS}
    assert len(titles) == len(SEEDS)
