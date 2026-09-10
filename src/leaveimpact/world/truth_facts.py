"""The truth fact base: core's derivation over every planted record, plus the authored facts.

Truth is built the way the investigator's harness builds its own view, through the one
derivation in ``core`` — an employee record becomes ``has_skill`` and ``member_of_team``
facts, a ticket becomes ``owns_work_item`` and ``due_on``, a meeting ``attends_event``
and ``scheduled_at`` — so the two bases agree on what every field means by construction
(the derivation ruling in DESIGN). What only a world can plant is added as authored
facts: a skill evidenced solely in a ticket comment, an owner a runbook asserts, what a
clause requires. Those are stated twice on purpose, once here as the fact and once in
the prose brief that will carry them; the fact is truth and the brief a rendering
instruction, and the containment gate at materialization keeps the two from drifting.

Every record derives against the date the world made it visible: the org's static
records from the world's start, a scenario's owned records from the day each was
planted. ``SYSTEM_OF`` names the system each record kind is projected to, which is the
source its facts are read from; the projectors will read the same table when they
exist, so it lives in one place.

This module builds the base and nothing else — how the base becomes the sealed truth
manifest is the artifact step's decision.
"""

from collections.abc import Iterable, Mapping
from datetime import date
from types import MappingProxyType

from leaveimpact.core.derivation import Derived, derive
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
from leaveimpact.core.facts import Fact, FactBase, Gap
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import OwnedEntities, Planted

SYSTEM_OF: Mapping[type[Entity], Source] = MappingProxyType(
    {
        Employee: Source.FRAPPE,
        Team: Source.FRAPPE,
        Leave: Source.FRAPPE,
        Component: Source.JIRA,
        WorkItem: Source.JIRA,
        CalendarEvent: Source.CALENDAR,
        Document: Source.CORPUS,
    }
)
"""The system each record kind is projected to — the source its derived facts are read from."""


def observed[T: Entity](entity: T) -> Observed[T]:
    """``entity`` as read from the system the world projects its kind to."""
    return Observed(entity, SYSTEM_OF[type(entity)])


def derive_org(org: OrgSpec, world_start: date) -> tuple[Derived, ...]:
    """Every fact and gap the organization's static records yield, observable from ``world_start``.

    Teams go through derivation like everything else and yield nothing, which keeps the
    rule "every record derives" true without an exception list here.
    """
    records: list[Entity] = [*org.teams, *org.employees, *org.components]
    return tuple(item for record in records for item in derive(observed(record), world_start))


def derive_owned(owned: OwnedEntities) -> tuple[Derived, ...]:
    """Every fact and gap a scenario's owned records yield, each from the day it was planted."""
    return (
        *_derive_each(owned.leaves),
        *_derive_each(owned.work_items),
        *_derive_each(owned.events),
        *_derive_each(owned.documents),
    )


def _derive_each[T: Entity](records: tuple[Planted[T], ...]) -> tuple[Derived, ...]:
    return tuple(
        item
        for record in records
        for item in derive(observed(record.entity), record.observable_from)
    )


def truth_fact_base(
    org: OrgSpec,
    world_start: date,
    owned: Iterable[OwnedEntities],
    authored: Iterable[Fact],
) -> FactBase:
    """The truth base over ``org`` and every scenario's owned records, plus the authored facts.

    The base's own construction refuses an incoherent world — a fact stated twice, a
    source both holding and lacking a value — and that refusal is the right failure: a
    construction bug ends generation instead of grading an agent wrong.
    """
    derived = [*derive_org(org, world_start)]
    for entities in owned:
        derived.extend(derive_owned(entities))
    facts = [item for item in derived if isinstance(item, Fact)]
    gaps = [item for item in derived if isinstance(item, Gap)]
    return FactBase(tuple([*facts, *authored]), tuple(gaps))
