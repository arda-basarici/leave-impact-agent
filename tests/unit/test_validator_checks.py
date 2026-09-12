"""The validator's three checks over the reference world: a faithful projection into the in-memory
ports passes every layer, each layer names what a specific corruption breaks, the expected side's
window rules are the ports' own, the boundary instants sit at ``now``'s wall-clock time on the
interval's ends, and the horizon bounds every window with a gap inside it."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import date, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.core.derivation import Derived
from leaveimpact.core.entities import Leave, WorkItem
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import leave_id, work_item_id
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.worldtime import DateSpan, local_date
from leaveimpact.validator.checks import (
    CheckStatus,
    boundary_instants,
    compare_identities,
    compare_records,
    compare_views,
    derive_stamped,
    events_overlapping,
    leaves_overlapping,
    observable_dates,
    view_at,
    window_instants,
    world_horizon,
)
from leaveimpact.world import (
    DEFAULT_PARAMS,
    PlantedWorldSpec,
    ScenarioPlanting,
    ScenarioSpec,
    WorldSpec,
    assemble_world,
    bundle,
    planted_world_spec,
)
from leaveimpact.world.truth_facts import observed
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


def dates(planted: PlantedWorldSpec) -> dict[EntityRef, date]:
    org_refs = [
        observed(record).ref
        for record in (*planted.org.teams, *planted.org.employees, *planted.org.components)
    ]
    return observable_dates(org_refs, planted.world_start, (r.owned for r in planted.scenarios))


def live_view(
    spec: ScenarioSpec,
    people: InMemoryPeople,
    work: InMemoryWork,
    calendar: InMemoryCalendar,
    stamps: Mapping[EntityRef, date],
) -> tuple[Derived, ...]:
    """The facts the investigator's reads yield for one scenario's window, stamped by planting."""
    instants = window_instants(spec.window, spec.reference_timezone)
    return (
        *derive_stamped(people.employees(), stamps),
        *derive_stamped(work.components(), stamps),
        *derive_stamped(work.work_items(), stamps),
        *derive_stamped(people.leaves_within(spec.window), stamps),
        *derive_stamped(calendar.events_within(instants), stamps),
    )


def expected_view(
    planted: PlantedWorldSpec, spec: ScenarioSpec, stamps: Mapping[EntityRef, date]
) -> tuple[Derived, ...]:
    """The plantings' facts under the same window rule, as the systems would return them."""
    leaves = [leave for row in planted.scenarios for leave in row.owned.leaves]
    events = [event for row in planted.scenarios for event in row.owned.events]
    items = [item for row in planted.scenarios for item in row.owned.work_items]
    instants = window_instants(spec.window, spec.reference_timezone)
    return (
        *derive_stamped([observed(e) for e in planted.org.employees], stamps),
        *derive_stamped([observed(c) for c in planted.org.components], stamps),
        *derive_stamped([observed(p.entity) for p in items], stamps),
        *derive_stamped(
            [observed(p.entity) for p in leaves_overlapping(leaves, spec.window)], stamps
        ),
        *derive_stamped(
            [observed(p.entity) for p in events_overlapping(events, instants)], stamps
        ),
    )


# --- Identity exactness -------------------------------------------------------------------


def test_a_faithful_projection_is_exact_in_every_enumerable_kind(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    people, work, calendar = projected(planted)
    days, instants = world_horizon(specs)
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
        compare_identities(
            EntityKind.LEAVE,
            [p.entity.id for r in planted.scenarios for p in r.owned.leaves],
            [o.value.id for o in people.leaves_within(days)],
        ),
        compare_identities(
            EntityKind.EVENT,
            [p.entity.id for r in planted.scenarios for p in r.owned.events],
            [o.value.id for o in calendar.events_within(instants)],
        ),
    ]
    assert all(check.status is CheckStatus.PASSED for check in checks)
    assert sum(len(c.missing) + len(c.foreign) for c in checks) == 0


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


# --- The instants and the horizon ---------------------------------------------------------


def test_the_boundary_instants_sit_on_the_interval_ends_at_nows_wall_clock(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    for row, spec in zip(planted.scenarios, specs, strict=True):
        first, last = boundary_instants(row, spec)
        zone = spec.reference_timezone
        assert local_date(first, zone) == row.stable_interval.start
        assert local_date(last, zone) == row.stable_interval.end
        now_local = spec.now.astimezone(ZoneInfo(zone))
        assert (first.hour, first.minute) == (now_local.hour, now_local.minute)
        assert first.tzinfo is not None and first.tzinfo.utcoffset(first) is not None


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


def test_the_expected_window_rules_are_the_ports_own(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    people, _, calendar = projected(planted)
    leaves = [leave for row in planted.scenarios for leave in row.owned.leaves]
    events = [event for row in planted.scenarios for event in row.owned.events]
    for spec in specs:
        instants = window_instants(spec.window, spec.reference_timezone)
        assert {p.entity.id for p in leaves_overlapping(leaves, spec.window)} == {
            o.value.id for o in people.leaves_within(spec.window)
        }
        assert {p.entity.id for p in events_overlapping(events, instants)} == {
            o.value.id for o in calendar.events_within(instants)
        }
    # A leave sharing one day with a span is within it; one ending the day before is not.
    probe = planted.scenarios[0].owned.leaves[0]
    touching = DateSpan(probe.entity.end, probe.entity.end + timedelta(days=3))
    before = DateSpan(
        probe.entity.start - timedelta(days=3), probe.entity.start - timedelta(days=1)
    )
    assert probe in leaves_overlapping([probe], touching)
    assert probe not in leaves_overlapping([probe], before)


# --- View agreement -----------------------------------------------------------------------


def test_the_live_view_equals_the_planted_view_at_both_ends_and_the_ends_agree(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    people, work, calendar = projected(planted)
    stamps = dates(planted)
    for row, spec in zip(planted.scenarios, specs, strict=True):
        live = live_view(spec, people, work, calendar, stamps)
        expected = expected_view(planted, spec, stamps)
        views: list[frozenset[Derived]] = []
        for instant in boundary_instants(row, spec):
            planted_view = view_at(expected, instant, spec.reference_timezone)
            live_at = view_at(live, instant, spec.reference_timezone)
            assert compare_views(spec.id, instant, planted_view, live_at) is None
            views.append(live_at)
        assert views[0] == views[1], f"{spec.id}: the observable facts moved inside the interval"
        assert views[0], f"{spec.id}: a run at the boundary observes something"


def test_a_leave_read_back_with_other_dates_is_a_disagreement_naming_both_sides(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    people, work, calendar = projected(planted)
    stamps = dates(planted)
    row, spec = planted.scenarios[0], specs[0]
    investigated: Leave = next(p.entity for p in row.owned.leaves if p.entity.id == spec.leave_id)
    people.leaves[investigated.id] = replace(investigated, end=investigated.end + timedelta(days=2))
    instant = boundary_instants(row, spec)[0]
    zone = spec.reference_timezone
    live = view_at(live_view(spec, people, work, calendar, stamps), instant, zone)
    expected = view_at(expected_view(planted, spec, stamps), instant, zone)
    finding = compare_views(spec.id, instant, expected, live)
    assert finding is not None and finding.scenario_id == spec.id
    assert finding.missing and finding.surplus
    assert all(item.subject.id == investigated.employee_id for item in finding.missing)
    assert all(item.subject.id == investigated.employee_id for item in finding.surplus)


def test_a_record_with_no_planting_cannot_be_dated_and_is_refused(
    planted: PlantedWorldSpec,
) -> None:
    stray = replace(planted.scenarios[0].owned.leaves[0].entity, id=leave_id(999))
    with pytest.raises(LookupError, match="leave_999 has no planting"):
        derive_stamped([observed(stray)], dates(planted))


def test_the_view_at_an_instant_hides_what_the_world_had_not_yet_shown(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]
) -> None:
    row: ScenarioPlanting = planted.scenarios[0]
    derived = expected_view(planted, specs[0], dates(planted))
    earliest = min(p.observable_from for p in row.owned.leaves)
    before = ZoneInfo(specs[0].reference_timezone)
    day_before = view_at(
        derived,
        boundary_instants(row, specs[0])[0].replace(
            year=earliest.year, month=earliest.month, day=earliest.day, tzinfo=before
        )
        - timedelta(days=1),
        specs[0].reference_timezone,
    )
    on_the_day = view_at(derived, boundary_instants(row, specs[0])[0], specs[0].reference_timezone)
    assert day_before < on_the_day
