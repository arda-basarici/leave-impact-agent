"""The runtime view: the record set the read ports return for a scenario's window, stated once
in ``world`` and equal to what the in-memory ports return; its facts all dated to the run day;
and the realizability proof it gives the whole-world verification — a key that holds under the
dated truth only because a later planting stays hidden is refused, named under the runtime view."""

from dataclasses import replace
from datetime import date, timedelta

from leaveimpact.core.claims import Verdict
from leaveimpact.core.entities import Leave
from leaveimpact.core.enums import LeaveKind, LeaveStatus
from leaveimpact.core.ids import leave_id
from leaveimpact.world import (
    DEFAULT_PARAMS,
    Planted,
    WorldSpec,
    assemble_world,
    events_within,
    leaves_within,
    runtime_facts,
    runtime_records,
    verify_world,
    window_instants,
    world_fact_base,
)
from tests.unit.in_memory_ports import InMemoryCalendar, InMemoryPeople

WORLD_START = date(2026, 1, 1)


def world() -> WorldSpec:
    return assemble_world(7, DEFAULT_PARAMS, WORLD_START)


def test_the_window_rules_are_the_ports_own() -> None:
    spec = world()
    people, calendar = InMemoryPeople(), InMemoryCalendar()
    leaves = [p for s in spec.scenarios for p in s.owned.leaves]
    events = [p for s in spec.scenarios for p in s.owned.events]
    for planted in leaves:
        people.add_leave(planted.entity)
    for planted in events:
        calendar.add_event(planted.entity)
    for scenario in spec.scenarios:
        window = scenario.spec.window
        instants = window_instants(window, scenario.spec.reference_timezone)
        assert {leave.id for leave in leaves_within(leaves, window)} == {
            o.value.id for o in people.leaves_within(window)
        }
        assert {event.id for event in events_within(events, instants)} == {
            o.value.id for o in calendar.events_within(instants)
        }
    # A leave sharing one day with a span is within it; one ending the day before is not.
    probe = leaves[0]
    touching = replace(probe.entity.span, start=probe.entity.end)
    before = replace(
        probe.entity.span,
        start=probe.entity.start - timedelta(days=3),
        end=probe.entity.start - timedelta(days=1),
    )
    assert leaves_within([probe], touching) == (probe.entity,)
    assert leaves_within([probe], before) == ()


def test_a_run_obtains_every_work_item_and_only_its_windows_leaves_and_events() -> None:
    spec = world()
    owned = [s.owned for s in spec.scenarios]
    first = spec.scenarios[0]
    records = runtime_records(spec.org, owned, first.spec)
    assert records.employees == spec.org.employees and records.components == spec.org.components
    assert len(records.work_items) == sum(len(s.owned.work_items) for s in spec.scenarios)
    assert len(records.work_items) > len(first.owned.work_items), "other slices' tickets too"
    assert {leave.id for leave in records.leaves} == {
        p.entity.id for p in first.owned.leaves if p.entity.span.overlaps(first.spec.window)
    }
    assert all(
        event.span.overlaps(window_instants(first.spec.window, "Europe/Istanbul"))
        for event in records.events
    )


def test_every_fact_a_run_obtains_is_dated_to_the_run_day_and_no_planting_date_survives() -> None:
    spec = world()
    first = spec.scenarios[0]
    run_day = first.spec.today
    base = runtime_facts(
        runtime_records(spec.org, [s.owned for s in spec.scenarios], first.spec), run_day
    )
    assert base.facts and {fact.observable_from for fact in base.facts} == {run_day}
    assert {gap.observable_from for gap in base.gaps} <= {run_day}
    # The dated truth shows earlier dates for the same records: the two views really differ.
    dated = {fact.observable_from for fact in spec.facts.facts}
    assert dated != {run_day}


def test_a_key_that_holds_only_because_a_later_planting_stays_hidden_is_refused() -> None:
    # Scenario 2 plants a leave for scenario 1's viable cover over scenario 1's leave, dated
    # after scenario 1's window: the dated truth never shows it on scenario 1's stable days,
    # so that view stays clean, but a run's leaves_within(window) returns it, the cover is
    # away, and the key is wrong for the world the investigator actually sees.
    spec = world()
    first, second = spec.scenarios[0], spec.scenarios[1]
    (expected, *_) = first.key.impacts
    cover = next(a.employee_id for a in expected.must_assess if a.verdict is Verdict.VIABLE)
    span = first.investigated_leave.span
    late = Leave(leave_id(999), cover, span.start, span.end, LeaveKind.SICK, LeaveStatus.APPROVED)
    planted = Planted(late, first.spec.window.end + timedelta(days=1))
    tampered = replace(second, owned=replace(second.owned, leaves=(*second.owned.leaves, planted)))
    scenarios = (first, tampered, *spec.scenarios[2:])
    findings = verify_world(world_fact_base(spec.org, WORLD_START, scenarios), scenarios, spec.org)
    assert findings
    assert {f.view for f in findings} == {"runtime"}, "the dated view cannot see it"
    assert {f.scenario_id for f in findings} == {first.key.scenario_id}
    assert any(f.subject == cover and f.expected == "viable" for f in findings)
    assert "under the runtime view" in str(findings[0])
