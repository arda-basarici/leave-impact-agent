"""Org generation: deterministic from its three inputs, honouring its parameters, and shaped so
the golden set's classes can select what they need instead of mutating the organization.

The shape tests run over a sweep of seeds, because a guarantee "by construction" is a
claim about every seed, not about the one a fixture happens to use.
"""

import math
from collections import Counter

import pytest

from leaveimpact.core import Employee, EmploymentType, Grade
from leaveimpact.core.ids import employee_id
from leaveimpact.world import (
    CITIES,
    DEFAULT_PARAMS,
    GENERATOR_VERSION,
    SKILLS,
    OrgParams,
    OrgSpec,
    generate_org,
)

SEEDS = range(1, 41)


@pytest.fixture(scope="module")
def spec() -> OrgSpec:
    return generate_org(7, DEFAULT_PARAMS)


def _root(spec: OrgSpec) -> Employee:
    (root,) = [employee for employee in spec.employees if employee.manager_id is None]
    return root


def test_the_same_inputs_give_an_equal_organization() -> None:
    assert generate_org(7, DEFAULT_PARAMS) == generate_org(7, DEFAULT_PARAMS)


def test_another_seed_gives_another_realization_of_the_same_regime() -> None:
    first, second = generate_org(7, DEFAULT_PARAMS), generate_org(8, DEFAULT_PARAMS)
    assert first != second
    assert first.params == second.params and first.generator_version == second.generator_version
    assert {e.name for e in first.employees} != {e.name for e in second.employees}


def test_the_spec_carries_the_inputs_that_produced_it(spec: OrgSpec) -> None:
    assert spec.seed == 7
    assert spec.params == DEFAULT_PARAMS
    assert spec.generator_version == GENERATOR_VERSION


def test_sizes_follow_the_parameters(spec: OrgSpec) -> None:
    assert len(spec.employees) == DEFAULT_PARAMS.org_size
    assert len(spec.teams) == DEFAULT_PARAMS.team_count
    assert len(spec.components) == DEFAULT_PARAMS.component_count
    blank = [employee for employee in spec.employees if employee.skills is None]
    assert len(blank) == DEFAULT_PARAMS.blank_skill_records
    assert spec.skills == tuple(skill.id for skill in SKILLS)


def test_ids_are_contiguous_and_names_unique(spec: OrgSpec) -> None:
    assert [e.id for e in spec.employees] == [employee_id(n) for n in range(1, 29)]
    assert len({e.name for e in spec.employees}) == len(spec.employees)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_reporting_line_is_one_tree_of_team_leads(seed: int) -> None:
    spec = generate_org(seed, DEFAULT_PARAMS)
    root = _root(spec)
    assert root.grade is Grade.LEAD
    for team in spec.teams:
        members = spec.members_of(team.id)
        assert members, team
        (lead,) = [member for member in members if member.grade is Grade.LEAD]
        assert lead.employment_type is EmploymentType.EMPLOYEE
        assert lead.manager_id == (None if lead is root else root.id)
        for member in members:
            if member is not lead:
                assert member.manager_id == lead.id, (member, lead)


@pytest.mark.parametrize("seed", SEEDS)
def test_team_sizes_differ_by_a_few_and_never_leave_a_lead_alone(seed: int) -> None:
    spec = generate_org(seed, DEFAULT_PARAMS)
    sizes = [len(spec.members_of(team.id)) for team in spec.teams]
    assert min(sizes) >= 2
    # round-robin dealing differs by at most one; each of the at most two moves widens
    # the spread by at most two
    assert max(sizes) - min(sizes) <= 5, sizes


@pytest.mark.parametrize("seed", SEEDS)
def test_a_contractor_exists_whenever_the_share_is_above_zero(seed: int) -> None:
    spec = generate_org(seed, DEFAULT_PARAMS)
    assert any(e.employment_type is EmploymentType.CONTRACTOR for e in spec.employees)
    none = generate_org(seed, OrgParams(contractor_share=0.0))
    assert not any(e.employment_type is EmploymentType.CONTRACTOR for e in none.employees)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_skill_distribution_holds_the_shapes_scenarios_select_on(seed: int) -> None:
    spec = generate_org(seed, DEFAULT_PARAMS)
    skilled = [e for e in spec.employees if e.skills is not None]
    holders = Counter(skill for e in skilled for skill in e.skills or ())
    assert set(holders) <= set(spec.skills)
    assert any(holders[skill] == 0 for skill in spec.skills), "no unheld skill"
    assert any(count == 1 for count in holders.values()), "no singleton skill"
    assert max(holders.values()) >= math.ceil(len(skilled) / 3), "no broadly held skill"
    low, high = DEFAULT_PARAMS.skills_per_person
    for employee in skilled:
        assert employee.skills is not None
        assert low <= len(employee.skills) <= high + 2  # the draw plus at most two anchors
        assert len(set(employee.skills)) == len(employee.skills)


@pytest.mark.parametrize("seed", SEEDS)
def test_every_component_crosses_team_lines(seed: int) -> None:
    spec = generate_org(seed, DEFAULT_PARAMS)
    team_of = {e.id: e.team_id for e in spec.employees}
    rosters = {frozenset(e.id for e in spec.members_of(team.id)) for team in spec.teams}
    for component in spec.components:
        assert 3 <= len(component.member_ids) <= 6
        assert len({team_of[member] for member in component.member_ids}) >= 2, component
        assert frozenset(component.member_ids) not in rosters


def test_location_country_and_timezone_belong_to_one_city(spec: OrgSpec) -> None:
    by_name = {city.name: city for city in CITIES}
    for employee in spec.employees:
        city = by_name[employee.location]
        assert (employee.country, employee.timezone) == (city.country, city.timezone)


def test_the_helpers_read_the_organization_the_way_a_scenario_will(spec: OrgSpec) -> None:
    for team in spec.teams:
        assert all(e.team_id == team.id for e in spec.members_of(team.id))
    for skill in spec.skills:
        holders = spec.holders_of(skill)
        assert all(e.skills is not None and skill in e.skills for e in holders)


def test_params_reject_shapes_the_generator_cannot_honour() -> None:
    with pytest.raises(ValueError, match="team_count"):
        OrgParams(team_count=1)
    with pytest.raises(ValueError, match="org_size"):
        OrgParams(org_size=9, team_count=5)
    with pytest.raises(ValueError, match="distinct names"):
        OrgParams(org_size=601)
    assert len(generate_org(1, OrgParams(org_size=600)).employees) == 600
    with pytest.raises(ValueError, match="component_count"):
        OrgParams(component_count=0)
    with pytest.raises(ValueError, match="blank_skill_records"):
        OrgParams(org_size=10, team_count=2, blank_skill_records=9)
    with pytest.raises(ValueError, match="skills_per_person"):
        OrgParams(skills_per_person=(0, 3))
    with pytest.raises(ValueError, match="skills_per_person"):
        OrgParams(skills_per_person=(2, len(SKILLS)))
    with pytest.raises(ValueError, match="contractor_share"):
        OrgParams(contractor_share=1.5)


def test_a_small_organization_still_honours_every_shape() -> None:
    params = OrgParams(org_size=6, team_count=2, component_count=1, blank_skill_records=1)
    for seed in SEEDS:
        spec = generate_org(seed, params)
        assert len(spec.employees) == 6 and len(spec.teams) == 2
        assert sum(e.skills is None for e in spec.employees) == 1
        (component,) = spec.components
        assert len({e.team_id for e in spec.employees if e.id in component.member_ids}) == 2
