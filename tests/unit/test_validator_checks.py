"""The validator's three checks over the reference world: a faithful projection into the in-memory
ports passes every layer, each layer names what a specific corruption breaks, exactness for the
windowed kinds is scoped by the horizon through the ports' own window rule, the horizon holds the
gaps between slices, and the view of a run is taken under the runtime rule on both sides — every
fact dated to the run day, other slices' tickets visible, no planting date anywhere."""

from dataclasses import replace
from datetime import date, timedelta
from itertools import pairwise

import pytest

from leaveimpact.core.derivation import Derived
from leaveimpact.core.entities import Leave, WorkItem
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import leave_id, work_item_id
from leaveimpact.validator.checks import (
    CheckStatus,
    compare_identities,
    compare_records,
    compare_views,
    derive_live,
    expected_view,
    world_horizon,
)
from leaveimpact.world import (
    DEFAULT_PARAMS,
    PlantedWorldSpec,
    ScenarioSpec,
    WorldSpec,
    assemble_world,
    bundle,
    events_within,
    leaves_within,
    planted_world_spec,
    window_instants,
)
from tests.unit.in_memory_ports import InMemoryCalendar, InMemoryPeople, InMemoryWork

WORLD_START = date(2026, 1, 1)
REFERENCE_SEED = 7


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return assemble_world(REFERENCE_SEED, DEFAULT_PARAMS, WORLD_START)


@pytest.fixture(scope="module")
def planted(world: WorldSpec) -> PlantedWorldSpec:
    sealed = bundle(world)
    return planted_world_spec(world, sealed.scenario_specs.digest, sealed.truth_manifest.digest)


@pytest.fixture(scope="module")
def specs(world: WorldSpec) -> tuple[ScenarioSpec, ...]:
    return tuple(scenario.spec for scenario in world.scenarios)


def projected(planted: PlantedWorldSpec) -> tuple[InMemoryPeople, InMemoryWork, InMemoryCalendar]:
    """The plantings written into the in-memory ports, the way a faithful projection lands."""
    people, work, calendar = InMemoryPeople(), InMemoryWork(), InMemoryCalendar()
    for team in planted.org.teams:
        people.add_team(team)
    for employee in planted.org.employees:
        people.add_employee(employee)
    for component in planted.org.components:
        work.add_component(component)
    for row in planted.scenarios:
        for leave in row.owned.leaves:
            people.add_leave(leave.entity)
        for item in row.owned.work_items:
            work.add_work_item(item.entity)
        for event in row.owned.events:
            calendar.add_event(event.entity)
    return people, work, calendar


def live_view(
    spec: ScenarioSpec, people: InMemoryPeople, work: InMemoryWork, calendar: InMemoryCalendar
) -> frozenset[Derived]:
    """The facts the investigator's reads yield for one scenario, dated to its run day."""
    today = spec.today
    instants = window_instants(spec.window, spec.reference_timezone)
    return frozenset(
        [
            *derive_live(people.employees(), today),
            *derive_live(work.components(), today),
            *derive_live(work.work_items(), today),
            *derive_live(people.leaves_within(spec.window), today),
            *derive_live(calendar.events_within(instants), today),
        ]
    )


# --- Identity exactness -------------------------------------------------------------------


def test_a_faithful_projection_is_exact_in_every_enumerable_kind(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    people, work, calendar = projected(planted)
    days, instants = world_horizon(specs)
    leaves = [p for r in planted.scenarios for p in r.owned.leaves]
    events = [p for r in planted.scenarios for p in r.owned.events]
    checks = [
        compare_identities(
            EntityKind.EMPLOYEE,
            [e.id for e in planted.org.employees],
            [o.value.id for o in people.employees()],
        ),
        compare_identities(
            EntityKind.COMPONENT,
            [c.id for c in planted.org.components],
            [o.value.id for o in work.components()],
        ),
        compare_identities(
            EntityKind.WORK_ITEM,
            [p.entity.id for r in planted.scenarios for p in r.owned.work_items],
            [o.value.id for o in work.work_items()],
        ),
        # The windowed kinds are scoped by the horizon on both sides, through the port's rule.
        compare_identities(
            EntityKind.LEAVE,
            [leave.id for leave in leaves_within(leaves, days)],
            [o.value.id for o in people.leaves_within(days)],
        ),
        compare_identities(
            EntityKind.EVENT,
            [event.id for event in events_within(events, instants)],
            [o.value.id for o in calendar.events_within(instants)],
        ),
    ]
    assert all(check.status is CheckStatus.PASSED for check in checks)
    assert sum(len(c.missing) + len(c.foreign) for c in checks) == 0
    assert len(leaves_within(leaves, days)) == len(leaves), "every planting lies inside the horizon"


def test_a_missing_and_a_foreign_identity_are_both_named_sorted(planted: PlantedWorldSpec) -> None:
    people, _, _ = projected(planted)
    expected = [p.entity.id for r in planted.scenarios for p in r.owned.leaves]
    lost = expected[0]
    del people.leaves[leave_id(int(lost.split("_")[1]))]
    stray = replace(planted.scenarios[0].owned.leaves[0].entity, id=leave_id(999))
    people.add_leave(stray)
    check = compare_identities(
        EntityKind.LEAVE, expected, [leave.id for leave in people.leaves.values()]
    )
    assert check.status is CheckStatus.FAILED
    assert check.missing == (lost,) and check.foreign == ("leave_999",)


def test_the_horizon_bounds_every_window_and_holds_the_gaps_between_them(
    specs: tuple[ScenarioSpec, ...],
) -> None:
    days, instants = world_horizon(specs)
    assert days.start == min(s.window.start for s in specs)
    assert days.end == max(s.window.end for s in specs)
    for spec in specs:
        span = window_instants(spec.window, spec.reference_timezone)
        assert instants.contains(span.start)
        assert instants.overlaps(span)
    ordered = sorted(specs, key=lambda s: s.window.start)
    gaps = [
        (a.window.end + timedelta(days=1), b.window.start - timedelta(days=1))
        for a, b in pairwise(ordered)
        if b.window.start - a.window.end > timedelta(days=1)
    ]
    assert gaps, "the reference world has a gap between two slices"
    for start, end in gaps:
        assert days.contains(start) and days.contains(end)
    with pytest.raises(ValueError, match="no scenarios"):
        world_horizon([])


# --- Record fidelity ----------------------------------------------------------------------


def test_records_read_back_equal_their_plantings_and_a_changed_field_is_named(
    planted: PlantedWorldSpec,
) -> None:
    _, work, _ = projected(planted)
    expected = {p.entity.id: p.entity for r in planted.scenarios for p in r.owned.work_items}
    read_back = {o.value.id: o.value for o in work.work_items()}
    assert compare_records(expected, read_back) == ()
    first = next(iter(expected))
    work.tickets[work_item_id(int(first.split("_")[1]))] = replace(
        read_back[first], title="renamed by hand", due_on=date(2030, 1, 1)
    )
    (mismatch,) = compare_records(expected, {o.value.id: o.value for o in work.work_items()})
    assert mismatch.ref.kind is EntityKind.WORK_ITEM and mismatch.ref.id == first
    assert mismatch.differing_fields == ("title", "due_on")


def test_identities_on_one_side_only_are_not_repeated_as_mismatches() -> None:
    planted_only: dict[str, WorkItem] = {}
    assert compare_records(planted_only, {}) == ()


# --- View agreement -----------------------------------------------------------------------


def test_the_live_view_equals_the_expected_view_for_every_scenario(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    people, work, calendar = projected(planted)
    for spec in specs:
        live = live_view(spec, people, work, calendar)
        assert compare_views(spec.id, spec.today, expected_view(planted, spec), live) is None
        assert live, f"{spec.id}: a run observes something"


def test_the_view_obeys_the_runtime_rule_on_both_sides(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    # Every fact is dated to the run day, and the tickets of other slices are in the view,
    # because the tracker enumerates whole and the harness knows no planting date.
    people, work, calendar = projected(planted)
    first = specs[0]
    live, expected = live_view(first, people, work, calendar), expected_view(planted, first)
    assert {item.observable_from for item in live} == {first.today}
    assert {item.observable_from for item in expected} == {first.today}
    other_tickets = {p.entity.id for r in planted.scenarios[1:] for p in r.owned.work_items}
    assert other_tickets & {item.evidence.target.id for item in live}
    # The dated truth would have hidden them: the two rules really differ.
    dated = {p.observable_from for r in planted.scenarios[1:] for p in r.owned.work_items}
    assert all(day > first.today for day in dated)


def test_a_leave_read_back_with_other_dates_is_a_disagreement_naming_both_sides(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    people, work, calendar = projected(planted)
    row, spec = planted.scenarios[0], specs[0]
    investigated: Leave = next(p.entity for p in row.owned.leaves if p.entity.id == spec.leave_id)
    people.leaves[investigated.id] = replace(investigated, end=investigated.end + timedelta(days=2))
    finding = compare_views(
        spec.id, spec.today, expected_view(planted, spec), live_view(spec, people, work, calendar)
    )
    assert finding is not None and finding.scenario_id == spec.id
    assert finding.missing and finding.surplus
    assert all(item.subject.id == investigated.employee_id for item in finding.missing)
    assert all(item.subject.id == investigated.employee_id for item in finding.surplus)


def test_an_event_read_back_an_hour_late_is_a_disagreement(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    # The layer that record equality cannot replace: a window read whose timezone handling
    # shifted an instant changes the derived schedule and shows here.
    people, work, calendar = projected(planted)
    spec = next(s for s, r in zip(specs, planted.scenarios, strict=True) if r.owned.events)
    row = next(r for r in planted.scenarios if r.scenario_id == spec.id)
    event = row.owned.events[0].entity
    shifted = replace(
        event, start=event.start + timedelta(hours=1), end=event.end + timedelta(hours=1)
    )
    calendar.events[event.id] = shifted
    finding = compare_views(
        spec.id, spec.today, expected_view(planted, spec), live_view(spec, people, work, calendar)
    )
    assert finding is not None
    assert {item.evidence.target.id for item in (*finding.missing, *finding.surplus)} == {event.id}
