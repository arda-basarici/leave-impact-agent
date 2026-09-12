"""The records the runtime ports return for a scenario, and their facts under the runtime rule.

Two views of one world exist and only one of them is real at run time. The truth base
dates every fact by when the world planted its record, and the evaluator grades against
keys proven under that dated view. The investigator's harness has no such dates: the
external systems hold every projected record at once, a read returns what the system
holds, and ``core``'s derivation stamps every returned record with the run's day (the
derivation module's rule for a live harness). So what a run can observe is decided by the
read requests alone — leaves and events narrowed to the scenario's window, employees,
components and work items enumerated whole, every scenario's tickets included — and never
by a planting date, which is benchmark-private and lives in the sealed world spec.

This module states that record set once, from the plantings, so that two consumers agree
on it by construction: the whole-world re-verification proves every key under it before
sealing, so a world whose key held only because a later or foreign planting stayed hidden
is refused at generation rather than discovered live; and the validator builds its
expected side from it, so what it compares the live reads against is what the runtime
should see and not what truth dated (the runtime-view ruling at the validator step, made
when the validator was found lending the live side the sealed dates). The window rules
are the read ports' own: a leave sharing a day with the window, an event overlapping the
window's instants in the reference zone; the in-memory ports and the adapters implement
the same rule, and the validator's tests hold the two equal.

Documents are not here because they derive no fact; what a clause requires enters the
runtime through prose, and the authored facts that stand for it are re-dated to the run
day by the caller that includes them.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta

from leaveimpact.core.derivation import Derived, derive
from leaveimpact.core.entities import CalendarEvent, Component, Employee, Leave, Team, WorkItem
from leaveimpact.core.facts import Fact, FactBase, Gap
from leaveimpact.core.worldtime import DateSpan, InstantSpan, zone
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import OwnedEntities, Planted, ScenarioSpec
from leaveimpact.world.truth_facts import observed


def window_instants(window: DateSpan, reference_timezone: str) -> InstantSpan:
    """``window`` as the half-open run of instants it covers in ``reference_timezone``.

    The events a run reads for a window are those overlapping its days as a human in the
    reference zone reads them: from the first day's midnight to the midnight after the
    last day.
    """
    tz = zone(reference_timezone)
    return InstantSpan(
        datetime.combine(window.start, datetime.min.time(), tzinfo=tz),
        datetime.combine(window.end + timedelta(days=1), datetime.min.time(), tzinfo=tz),
    )


def leaves_within(plantings: Iterable[Planted[Leave]], span: DateSpan) -> tuple[Leave, ...]:
    """The planted leaves a ``leaves_within(span)`` read returns: any that shares a day with it."""
    return tuple(p.entity for p in plantings if p.entity.span.overlaps(span))


def events_within(
    plantings: Iterable[Planted[CalendarEvent]], span: InstantSpan
) -> tuple[CalendarEvent, ...]:
    """The planted events an ``events_within(span)`` read returns: any that overlaps it."""
    return tuple(p.entity for p in plantings if p.entity.span.overlaps(span))


@dataclass(frozen=True, slots=True)
class RuntimeRecords:
    """What the read ports return for one scenario's window, before any fact is derived."""

    teams: tuple[Team, ...]
    employees: tuple[Employee, ...]
    components: tuple[Component, ...]
    work_items: tuple[WorkItem, ...]
    leaves: tuple[Leave, ...]
    events: tuple[CalendarEvent, ...]


def runtime_records(
    org: OrgSpec, owned: Iterable[OwnedEntities], spec: ScenarioSpec
) -> RuntimeRecords:
    """The record set a run of ``spec`` obtains from a world holding every planting in ``owned``.

    The organization whole, every scenario's work items, and the leaves and events that
    overlap the scenario's window; the plantings' dates play no part.
    """
    rows = list(owned)
    leaves = [p for entities in rows for p in entities.leaves]
    events = [p for entities in rows for p in entities.events]
    return RuntimeRecords(
        teams=org.teams,
        employees=org.employees,
        components=org.components,
        work_items=tuple(p.entity for entities in rows for p in entities.work_items),
        leaves=leaves_within(leaves, spec.window),
        events=events_within(events, window_instants(spec.window, spec.reference_timezone)),
    )


def runtime_facts(
    records: RuntimeRecords, run_day: date, authored: Iterable[Fact] = ()
) -> FactBase:
    """The base a run on ``run_day`` derives from ``records``: every fact observable that day.

    ``authored`` are the facts prose carries into the run; they are re-dated to the run
    day like everything else the run obtains.
    """
    derived: list[Derived] = []
    for group in (
        records.teams,
        records.employees,
        records.components,
        records.work_items,
        records.leaves,
        records.events,
    ):
        for record in group:
            derived.extend(derive(observed(record), run_day))
    facts = [item for item in derived if isinstance(item, Fact)]
    gaps = [item for item in derived if isinstance(item, Gap)]
    carried = [replace(fact, observable_from=run_day) for fact in authored]
    return FactBase(tuple([*facts, *carried]), tuple(gaps))
