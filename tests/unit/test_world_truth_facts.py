"""The truth base: every record goes through core's derivation from the day the world made it
visible, the authored facts join it, and an incoherent world fails at the base's construction."""

from datetime import date

import pytest

from leaveimpact.core import (
    EvidenceRef,
    Fact,
    Gap,
    Leave,
    LeaveKind,
    LeaveStatus,
    PredicateName,
    Source,
    comment_ref,
    employee_ref,
)
from leaveimpact.core.ids import comment_id, leave_id, skill_id
from leaveimpact.world import DEFAULT_PARAMS, OwnedEntities, Planted, generate_org
from leaveimpact.world.truth_facts import derive_org, derive_owned, truth_fact_base

WORLD_START = date(2026, 1, 1)
ORG = generate_org(7, DEFAULT_PARAMS)


def test_the_org_derives_from_the_world_start_with_each_kind_read_from_its_system() -> None:
    derived = derive_org(ORG, WORLD_START)
    assert derived and all(item.observable_from == WORLD_START for item in derived)
    skills = [d for d in derived if d.predicate is PredicateName.HAS_SKILL]
    memberships = [d for d in derived if d.predicate is PredicateName.MEMBER_OF_COMPONENT]
    assert {d.source for d in skills} == {Source.FRAPPE}
    assert {d.source for d in memberships} == {Source.JIRA}
    assert len(memberships) == sum(len(component.member_ids) for component in ORG.components)


def test_a_blank_skills_record_derives_as_a_gap_and_nothing_else_does() -> None:
    gaps = [item for item in derive_org(ORG, WORLD_START) if isinstance(item, Gap)]
    assert len(gaps) == DEFAULT_PARAMS.blank_skill_records
    assert {gap.predicate for gap in gaps} == {PredicateName.HAS_SKILL}


def test_an_owned_record_derives_from_the_day_it_was_planted() -> None:
    leave = Leave(
        leave_id(1), ORG.employees[0].id, date(2026, 3, 10), date(2026, 3, 12),
        LeaveKind.ANNUAL, LeaveStatus.APPROVED,
    )
    (on_leave,) = derive_owned(OwnedEntities(leaves=(Planted(leave, date(2026, 3, 1)),)))
    assert on_leave.predicate is PredicateName.ON_LEAVE
    assert on_leave.observable_from == date(2026, 3, 1)
    assert on_leave.source is Source.FRAPPE


def test_authored_facts_join_the_base_and_a_duplicate_is_refused() -> None:
    authored = Fact(
        employee_ref(ORG.employees[0].id),
        PredicateName.HAS_SKILL,
        skill_id("kafka"),
        EvidenceRef(Source.JIRA, comment_ref(comment_id(1))),
        date(2026, 2, 1),
    )
    base = truth_fact_base(ORG, WORLD_START, [], [authored])
    assert authored in base.facts
    with pytest.raises(ValueError, match="stated once"):
        truth_fact_base(ORG, WORLD_START, [], [authored, authored])
