"""The fragmented tier's qualification class over a sweep of seeds: the shape the class promises —
a meeting under a scenario-owned skill clause, the viable cover's skill carried only by a
comment brief that derives as answer-changing, a second candidate failing the skill — plus the
canonical affordance order and determinism."""

from datetime import date
from random import Random

import pytest

from leaveimpact.core import (
    AssessmentReason,
    DocumentKind,
    ImpactSubtype,
    PredicateName,
    Source,
    Verdict,
    clause_ref,
    event_ref,
)
from leaveimpact.core.ids import scenario_id
from leaveimpact.world import (
    DEFAULT_PARAMS,
    FreeTextQualification,
    Minting,
    Register,
    Scenario,
    allocate_slices,
    construct,
    generate_org,
)
from leaveimpact.world.fragmented import POLICY_CLAUSE
from leaveimpact.world.prose import FactRole

ORG = generate_org(7, DEFAULT_PARAMS)
WORLD_START = date(2026, 1, 1)
SLICES = allocate_slices(Random(0), 30, WORLD_START)
TZ = ORG.params.reference_timezone
SEEDS = range(1, 21)
QUALIFICATION = FreeTextQualification()


def _scenario(seed: int) -> Scenario:
    return construct(
        QUALIFICATION,
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
