"""An entity as a source returned it: the value and where it was read.

Every read crosses the port wrapped, because the source is provenance the domain
needs and the entity does not carry: the derivation that turns an employee into
facts stamps each one with an evidence reference, and the authority table keys a
conflict by source. The wrapper holds only what the entity cannot say about itself —
the record's reference is computed from the entity's own id, so a second field for it
would be a second place for the same truth to drift.

The source is explicit rather than inferred from the entity's type, because the
registry keys conflicts by source and a second system claiming the same kind of
record is a designed-for case, not an error. What is checked at construction is the
opposite direction: the source must be one that holds this kind of record, the same
table an evidence reference is checked against, so an observed employee from the
tracker fails here rather than becoming a fact with impossible provenance.
"""

# No deferred annotations here: pdoc resolves a PEP 695 type parameter only when the
# class body evaluates it, and nothing in this module needs a forward reference.
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from leaveimpact.core.entities import (
    CalendarEvent,
    Component,
    Document,
    Employee,
    Leave,
    Team,
    WorkItem,
)
from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.refs import TARGET_KINDS_BY_SOURCE, EntityRef

type Entity = Employee | Team | Component | WorkItem | CalendarEvent | Document | Leave
"""The records a port returns — every entity that is read as a record of its own.

A comment is read inside its work item and a clause inside its document, so neither
is observed alone.
"""

KIND_BY_ENTITY_TYPE: Mapping[type[Entity], EntityKind] = MappingProxyType(
    {
        Employee: EntityKind.EMPLOYEE,
        Team: EntityKind.TEAM,
        Component: EntityKind.COMPONENT,
        WorkItem: EntityKind.WORK_ITEM,
        CalendarEvent: EntityKind.EVENT,
        Document: EntityKind.DOCUMENT,
        Leave: EntityKind.LEAVE,
    }
)
"""The reference kind of each observable entity type."""


@dataclass(frozen=True, slots=True)
class Observed[T: Entity]:
    """``value`` as read from ``source``.

    >>> from datetime import date
    >>> from leaveimpact.core.enums import LeaveKind, LeaveStatus
    >>> from leaveimpact.core.ids import employee_id, leave_id
    >>> leave = Leave(leave_id(5), employee_id(17), date(2026, 9, 15), date(2026, 9, 19),
    ...               LeaveKind.ANNUAL, LeaveStatus.APPROVED)
    >>> Observed(leave, Source.FRAPPE).ref
    EntityRef(kind=<EntityKind.LEAVE: 'leave'>, id='leave_005')
    >>> Observed(leave, Source.JIRA)
    Traceback (most recent call last):
    ...
    ValueError: jira holds no leave record; it holds comment, component, work_item
    """

    value: T
    source: Source

    def __post_init__(self) -> None:
        held = TARGET_KINDS_BY_SOURCE[self.source]
        if self.kind not in held:
            raise ValueError(
                f"{self.source.value} holds no {self.kind.value} record; it holds "
                f"{', '.join(sorted(kind.value for kind in held))}"
            )

    @property
    def kind(self) -> EntityKind:
        """The reference kind of the observed record."""
        return KIND_BY_ENTITY_TYPE[type(self.value)]

    @property
    def ref(self) -> EntityRef:
        """The reference to the observed record — the evidence target its facts cite."""
        return EntityRef(self.kind, self.value.id)
