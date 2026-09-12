"""Projection: the frozen world written into the four systems, restart-safe, through the ports.

One projector per system, each a function over plain entities and the system's reader and
writer, so a projector is tested against the in-memory ports and never against a sandbox.
The invariant is not one algorithm but one property: every projector is restart-safe on
the strongest identity guarantee its target provides (the find-or-create ruling at the
projector step). Frappe, Jira and the corpus find, verify, add: read by domain id, accept
an existing record only when it equals the planted entity as the adapter reads it back —
the integration tests prove the round trip exact for every generator-controlled field, so
equality is the rule and no looser equivalence is named — and add what is missing. The
calendar inserts directly, because its vendor event id is derived from the domain id and
the insert is the ensure: a missing copy is created, an existing copy is verified by
read-back, a half-written event completes; finding one event by id would cost one read per
calendar and turn a recoverable partial write into an error.

An existing identity holding other state is ``IdentityConflict``, the third port fault:
the adapter translated the record fine, the identity points at conflicting state, and
projection stops rather than adopt or overwrite it. The projector's comparison protects
the projection's identity integrity; the validator, separately, proves the assembled world
still yields the expected truth. Order follows what each system needs to exist first:
teams before employees, managers before their reports, employees before leaves;
components before work items; calendars are prepared before events; the corpus schema
before documents.

A receipt is the writer's return, one locator per domain id, and a reader returns an
entity and no locator by design, so a locator that is not persisted before the next
failure is gone — Jira's issue key exists nowhere else. The projectors therefore hand each
receipt to a sink the composition root supplies, right after the write returns and before
the next external write, and the root checkpoints it into the manifest before returning:
a later projection failure cannot lose the receipt of an earlier completed write (the
manifest-lifecycle ruling at the projector step). On a rerun a found entity produces no
receipt, and needs none, since the checkpoint holds it. The calendar re-reports its
derived id every run, which the fold absorbs.

What the sink does not cover is the window between an external write returning and its
durable checkpoint: a process death there, or a checkpoint that itself fails to persist,
loses the locator, because the recovery contract is restartability after the faults the
transport reports, not after a kill at any instruction, and no callback placement spans a
vendor and a local file. That window is loud, never silent — the restart finds the record
and receipts nothing, the post-projection coverage check refuses to accept the manifest,
and the operator deletes the marked record and reruns. Read-side locator recovery is the
revisit if the window is ever hit in practice; the locators the readers cannot reconstruct
today are the vendor-minted ones — Jira issue keys and component ids, Frappe's generated
leave names — while employees, teams, events and documents carry derived ones. A source
that cannot answer raises ``SourceUnreachable`` through, unhandled: a projection with a
dead system has nothing to record.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from leaveimpact.core.entities import (
    CalendarEvent,
    Component,
    Document,
    Employee,
    Leave,
    Team,
    WorkItem,
)
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.ports.errors import IdentityConflict
from leaveimpact.core.ports.observed import KIND_BY_ENTITY_TYPE, Entity, Observed
from leaveimpact.core.ports.read import (
    CalendarReader,
    DocumentReader,
    PeopleReader,
    WorkReader,
)
from leaveimpact.core.ports.write import (
    CalendarWriter,
    DocumentWriter,
    PeopleWriter,
    WorkWriter,
)
from leaveimpact.core.refs import EntityRef
from leaveimpact.world.assembly import WorldSpec

ReceiptSink = Callable[[EntityRef, str], None]
"""Where a projector reports each locator the moment a write returns; the root's checkpoint."""


class PeopleSystem(PeopleReader, PeopleWriter, Protocol):
    """The HR system, both sides: what a projector holds."""


class WorkSystem(WorkReader, WorkWriter, Protocol):
    """The issue tracker, both sides."""


class CalendarSystem(CalendarReader, CalendarWriter, Protocol):
    """The calendar, both sides."""


class DocumentSystem(DocumentReader, DocumentWriter, Protocol):
    """The corpus, both sides."""


@dataclass(frozen=True, slots=True)
class Systems:
    """The four systems a world is projected into, prepared and configured by the root."""

    people: PeopleSystem
    work: WorkSystem
    calendar: CalendarSystem
    documents: DocumentSystem


@dataclass(frozen=True, slots=True)
class WorldEntities:
    """Every entity a world plants, by kind, in projection order.

    Employees come managers first, so a report's manager exists when the report is written;
    the scenario-owned kinds are gathered across scenarios in scenario order.
    """

    teams: tuple[Team, ...]
    employees: tuple[Employee, ...]
    leaves: tuple[Leave, ...]
    components: tuple[Component, ...]
    work_items: tuple[WorkItem, ...]
    events: tuple[CalendarEvent, ...]
    documents: tuple[Document, ...]


def world_entities(world: WorldSpec) -> WorldEntities:
    """The entities of ``world`` in projection order; the projectors' only read of the spec."""
    org = world.org
    owned = [scenario.owned for scenario in world.scenarios]
    return WorldEntities(
        teams=org.teams,
        employees=managers_first(org.employees),
        leaves=tuple(planted.entity for scenario in owned for planted in scenario.leaves),
        components=org.components,
        work_items=tuple(planted.entity for scenario in owned for planted in scenario.work_items),
        events=tuple(planted.entity for scenario in owned for planted in scenario.events),
        documents=tuple(planted.entity for scenario in owned for planted in scenario.documents),
    )


def managers_first(employees: Iterable[Employee]) -> tuple[Employee, ...]:
    """``employees`` reordered so that every manager precedes their reports, ties by input order.

    A manager outside the sequence, or a cycle, is a construction defect and raises.

    >>> from leaveimpact.core.enums import EmploymentType, Grade
    >>> from leaveimpact.core.ids import employee_id, team_id
    >>> def person(number: int, manager: int | None) -> Employee:
    ...     return Employee(employee_id(number), f"P{number}", team_id(1),
    ...                     None if manager is None else employee_id(manager), (), "Istanbul",
    ...                     "TR", "Europe/Istanbul", Grade.SENIOR, EmploymentType.EMPLOYEE)
    >>> [e.id for e in managers_first([person(3, 2), person(2, 1), person(1, None)])]
    ['emp_001', 'emp_002', 'emp_003']
    """
    pending = list(employees)
    placed: dict[EmployeeId, Employee] = {}
    while pending:
        ready = [
            employee
            for employee in pending
            if employee.manager_id is None or employee.manager_id in placed
        ]
        if not ready:
            waiting = sorted(employee.id for employee in pending)
            raise ValueError(f"no manager order places {waiting}: a manager is missing or cyclic")
        for employee in ready:
            placed[employee.id] = employee
        pending = [employee for employee in pending if employee.id not in placed]
    return tuple(placed.values())


# --- The four projectors ------------------------------------------------------------------


def project_people(entities: WorldEntities, system: PeopleSystem, sink: ReceiptSink) -> None:
    """Teams, then employees managers first, then leaves: find, verify, add."""
    _ensure(entities.teams, system.team, system.add_team, Source.FRAPPE, sink)
    _ensure(entities.employees, system.employee, system.add_employee, Source.FRAPPE, sink)
    _ensure(entities.leaves, system.leave, system.add_leave, Source.FRAPPE, sink)


def project_work(entities: WorldEntities, system: WorkSystem, sink: ReceiptSink) -> None:
    """Components, then work items with their comments: find, verify, add."""
    _ensure(entities.components, system.component, system.add_component, Source.JIRA, sink)
    _ensure(entities.work_items, system.work_item, system.add_work_item, Source.JIRA, sink)


def project_calendar(entities: WorldEntities, system: CalendarSystem, sink: ReceiptSink) -> None:
    """Every event inserted; the derived id makes the insert the ensure, so no find precedes it."""
    for event in entities.events:
        sink(_ref(event), system.add_event(event))


def project_documents(entities: WorldEntities, system: DocumentSystem, sink: ReceiptSink) -> None:
    """Documents with their sections: find, verify, add."""
    _ensure(entities.documents, system.document, system.add_document, Source.CORPUS, sink)


def project_world(entities: WorldEntities, systems: Systems, sink: ReceiptSink) -> None:
    """All four projectors in system order, every receipt reported to ``sink`` as it lands."""
    project_people(entities, systems.people, sink)
    project_work(entities, systems.work, sink)
    project_calendar(entities, systems.calendar, sink)
    project_documents(entities, systems.documents, sink)


def _ensure[T: Entity, K: str](
    entities: Sequence[T],
    find: Callable[[K], Observed[T] | None],
    add: Callable[[T], str],
    source: Source,
    sink: ReceiptSink,
) -> None:
    """Find, verify, add for one kind, each add's locator reported before the next entity."""
    for entity in entities:
        found = find(cast(K, entity.id))
        if found is None:
            sink(_ref(entity), add(entity))
        elif found.value != entity:
            raise IdentityConflict(
                source,
                str(entity.id),
                f"an existing record differs from the planted one: {found.value} is not {entity}",
            )


def _ref(entity: Entity) -> EntityRef:
    return EntityRef(KIND_BY_ENTITY_TYPE[type(entity)], entity.id)
