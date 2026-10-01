"""JSON for the observable entities, and for the observed record that wraps one with its source.

The record atom. An entity has one JSON shape in this project, whatever wrote it: the
world's sealed spec embeds a planted leave in it, a tool renders a leave the investigator
read in it, the run export stores that rendering, and the grounding replay decodes it
back to the same ``Observed`` the derivation takes. One codec, here in ``core`` — the only
package both the investigator and the evaluator reach, and the owner of the types —
because two encodings of one type drift on every later field, and the record a model
sees would then differ from the record the world planted for no reason (the investigator
milestone's second build step). The sealed world codecs call the per-entity functions and
keep their own contextual shapes around them, so a sealed byte did not move when the
functions moved.

Two layers, kept apart. The *entity value* is the record by itself, keyed by nothing
but its fields; the sealed world spec embeds it bare. The *observed record* wraps one
value with the ``source`` it was read from and a ``kind`` discriminator, because a
bare value does not say what it is (a work item and a leave are both objects with an
``id``) and the source is provenance the entity cannot carry (the observed-record
module says why). The discriminator never enters a sealed artifact, which names its
records by position. The tool-result envelope — one record, none, a sequence, a failed
read — is a third layer and belongs to the run export, not here.

Strict in the sealed codecs' manner: exactly the declared fields, each of its declared
shape, an id in the namespace the field names (``require_id``, the one rule), an enum
member by its value, dates and instants in the one canonical spelling, and every
semantic check the domain constructors make, since a decoded record is built through
them. A value that decodes is one a rule can run on; anything else refuses naming the
field, never a ``KeyError`` from deep inside.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import assert_never

from leaveimpact.core.entities import (
    CalendarEvent,
    Comment,
    Component,
    Document,
    DocumentSection,
    Employee,
    Leave,
    Team,
    WorkItem,
)
from leaveimpact.core.enums import (
    DocumentKind,
    EmploymentType,
    EntityKind,
    Grade,
    LeaveKind,
    LeaveStatus,
    Source,
    WorkItemStatus,
)
from leaveimpact.core.ids import (
    ClauseId,
    CommentId,
    ComponentId,
    DocumentId,
    EmployeeId,
    EventId,
    LeaveId,
    TeamId,
    WorkItemId,
    skill_id,
)
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    expect_fields,
    field_of,
    object_field,
    optional_string_field,
    string_field,
    string_item,
)
from leaveimpact.core.ports.observed import KIND_BY_ENTITY_TYPE, Entity, Observed
from leaveimpact.core.refs import require_id
from leaveimpact.core.timeshape import (
    decode_date,
    decode_instant,
    decode_optional_date,
    encode_date,
    encode_instant,
    encode_optional_date,
)

# --- Entity values ------------------------------------------------------------------------


def encode_team(team: Team) -> JsonObject:
    """The JSON object of a team: id and name."""
    return {"id": team.id, "name": team.name}


def decode_team(value: object) -> Team:
    """The team ``value`` encodes; ``ValueError`` names what is malformed."""
    data = as_object(value, "a team")
    expect_fields(data, ("id", "name"), "a team")
    return Team(id=_id(data, "id", EntityKind.TEAM, TeamId), name=string_field(data, "name"))


def encode_employee(employee: Employee) -> JsonObject:
    """The JSON object of an employee; ``skills`` is ``null`` when the world holds no record."""
    return {
        "id": employee.id,
        "name": employee.name,
        "team_id": employee.team_id,
        "manager_id": employee.manager_id,
        "skills": None if employee.skills is None else list(employee.skills),
        "location": employee.location,
        "country": employee.country,
        "timezone": employee.timezone,
        "grade": employee.grade.value,
        "employment_type": employee.employment_type.value,
    }


def decode_employee(value: object) -> Employee:
    """The employee ``value`` encodes; a ``null`` skills list stays the absent record."""
    data = as_object(value, "an employee")
    expect_fields(
        data,
        (
            "id",
            "name",
            "team_id",
            "manager_id",
            "skills",
            "location",
            "country",
            "timezone",
            "grade",
            "employment_type",
        ),
        "an employee",
    )
    manager = optional_string_field(data, "manager_id")
    skills = field_of(data, "skills")
    return Employee(
        id=_id(data, "id", EntityKind.EMPLOYEE, EmployeeId),
        name=string_field(data, "name"),
        team_id=_id(data, "team_id", EntityKind.TEAM, TeamId),
        manager_id=None if manager is None else _employee_id(manager),
        skills=None
        if skills is None
        else tuple(skill_id(string_item(item, "skills")) for item in array_field(data, "skills")),
        location=string_field(data, "location"),
        country=string_field(data, "country"),
        timezone=string_field(data, "timezone"),
        grade=Grade(string_field(data, "grade")),
        employment_type=EmploymentType(string_field(data, "employment_type")),
    )


def encode_component(component: Component) -> JsonObject:
    """The JSON object of a component: id, name, member ids in order."""
    return {"id": component.id, "name": component.name, "member_ids": list(component.member_ids)}


def decode_component(value: object) -> Component:
    """The component ``value`` encodes."""
    data = as_object(value, "a component")
    expect_fields(data, ("id", "name", "member_ids"), "a component")
    return Component(
        id=_id(data, "id", EntityKind.COMPONENT, ComponentId),
        name=string_field(data, "name"),
        member_ids=_employee_ids(data, "member_ids"),
    )


def encode_leave(leave: Leave) -> JsonObject:
    """The JSON object of a leave: both absent days inclusive, kind and status by value."""
    return {
        "id": leave.id,
        "employee_id": leave.employee_id,
        "start": encode_date(leave.start),
        "end": encode_date(leave.end),
        "kind": leave.kind.value,
        "status": leave.status.value,
    }


def decode_leave(value: object) -> Leave:
    """The leave ``value`` encodes; a reversed pair fails in the constructor."""
    data = as_object(value, "a leave")
    expect_fields(data, ("id", "employee_id", "start", "end", "kind", "status"), "a leave")
    return Leave(
        id=_id(data, "id", EntityKind.LEAVE, LeaveId),
        employee_id=_id(data, "employee_id", EntityKind.EMPLOYEE, EmployeeId),
        start=decode_date(string_field(data, "start"), "a date"),
        end=decode_date(string_field(data, "end"), "a date"),
        kind=LeaveKind(string_field(data, "kind")),
        status=LeaveStatus(string_field(data, "status")),
    )


def encode_work_item(item: WorkItem) -> JsonObject:
    """The JSON object of a work item with its comments in order; open dates are ``null``."""
    return {
        "id": item.id,
        "title": item.title,
        "owner_id": item.owner_id,
        "status": item.status.value,
        "component_id": item.component_id,
        "opened_on": encode_date(item.opened_on),
        "resolved_on": encode_optional_date(item.resolved_on),
        "due_on": encode_optional_date(item.due_on),
        "comments": [_encode_comment(comment) for comment in item.comments],
    }


def decode_work_item(value: object) -> WorkItem:
    """The work item ``value`` encodes."""
    data = as_object(value, "a work item")
    expect_fields(
        data,
        (
            "id",
            "title",
            "owner_id",
            "status",
            "component_id",
            "opened_on",
            "resolved_on",
            "due_on",
            "comments",
        ),
        "a work item",
    )
    return WorkItem(
        id=_id(data, "id", EntityKind.WORK_ITEM, WorkItemId),
        title=string_field(data, "title"),
        owner_id=_id(data, "owner_id", EntityKind.EMPLOYEE, EmployeeId),
        status=WorkItemStatus(string_field(data, "status")),
        component_id=_id(data, "component_id", EntityKind.COMPONENT, ComponentId),
        opened_on=decode_date(string_field(data, "opened_on"), "a date"),
        resolved_on=decode_optional_date(data, "resolved_on"),
        due_on=decode_optional_date(data, "due_on"),
        comments=tuple(_decode_comment(item) for item in array_field(data, "comments")),
    )


def _encode_comment(comment: Comment) -> JsonObject:
    return {
        "id": comment.id,
        "world_date": encode_date(comment.world_date),
        "author_id": comment.author_id,
        "text": comment.text,
    }


def _decode_comment(value: object) -> Comment:
    data = as_object(value, "a comment")
    expect_fields(data, ("id", "world_date", "author_id", "text"), "a comment")
    return Comment(
        id=_id(data, "id", EntityKind.COMMENT, CommentId),
        world_date=decode_date(string_field(data, "world_date"), "a date"),
        author_id=_id(data, "author_id", EntityKind.EMPLOYEE, EmployeeId),
        text=string_field(data, "text"),
    )


def encode_event(event: CalendarEvent) -> JsonObject:
    """The JSON object of a calendar event: both instants with their zones, attendees in order."""
    return {
        "id": event.id,
        "title": event.title,
        "start": encode_instant(event.start),
        "end": encode_instant(event.end),
        "attendee_ids": list(event.attendee_ids),
    }


def decode_event(value: object) -> CalendarEvent:
    """The event ``value`` encodes; a naive or reversed pair fails in the constructor."""
    data = as_object(value, "an event")
    expect_fields(data, ("id", "title", "start", "end", "attendee_ids"), "an event")
    return CalendarEvent(
        id=_id(data, "id", EntityKind.EVENT, EventId),
        title=string_field(data, "title"),
        start=decode_instant(field_of(data, "start"), "start"),
        end=decode_instant(field_of(data, "end"), "end"),
        attendee_ids=_employee_ids(data, "attendee_ids"),
    )


def encode_document(document: Document) -> JsonObject:
    """The JSON object of one document: id, title, kind, effective date, sections in order."""
    return {
        "id": document.id,
        "title": document.title,
        "kind": document.kind.value,
        "effective_from": encode_date(document.effective_from),
        "sections": [{"id": section.id, "text": section.text} for section in document.sections],
    }


def decode_document(value: object) -> Document:
    """The document ``value`` encodes."""
    data = as_object(value, "a document")
    expect_fields(data, ("id", "title", "kind", "effective_from", "sections"), "a document")
    return Document(
        id=_id(data, "id", EntityKind.DOCUMENT, DocumentId),
        title=string_field(data, "title"),
        kind=DocumentKind(string_field(data, "kind")),
        effective_from=decode_date(string_field(data, "effective_from"), "a date"),
        sections=tuple(_decode_section(item) for item in array_field(data, "sections")),
    )


def _decode_section(value: object) -> DocumentSection:
    data = as_object(value, "a section")
    expect_fields(data, ("id", "text"), "a section")
    return DocumentSection(
        id=_id(data, "id", EntityKind.CLAUSE, ClauseId), text=string_field(data, "text")
    )


# --- Any entity, by kind -------------------------------------------------------------------


def encode_entity(entity: Entity) -> JsonObject:
    """``entity`` in its own shape, whichever of the seven observable kinds it is."""
    match entity:
        case Employee():
            return encode_employee(entity)
        case Team():
            return encode_team(entity)
        case Component():
            return encode_component(entity)
        case WorkItem():
            return encode_work_item(entity)
        case CalendarEvent():
            return encode_event(entity)
        case Document():
            return encode_document(entity)
        case Leave():
            return encode_leave(entity)
        case _:
            assert_never(entity)


def decode_entity(kind: EntityKind, value: object) -> Entity:
    """The entity of ``kind`` that ``value`` encodes; a kind no record is read as is refused."""
    match kind:
        case EntityKind.EMPLOYEE:
            return decode_employee(value)
        case EntityKind.TEAM:
            return decode_team(value)
        case EntityKind.COMPONENT:
            return decode_component(value)
        case EntityKind.WORK_ITEM:
            return decode_work_item(value)
        case EntityKind.EVENT:
            return decode_event(value)
        case EntityKind.DOCUMENT:
            return decode_document(value)
        case EntityKind.LEAVE:
            return decode_leave(value)
        case EntityKind.COMMENT | EntityKind.CLAUSE:
            raise ValueError(f"{kind.value} is read inside its record, never observed alone")
        case _:
            assert_never(kind)


# --- The observed record -------------------------------------------------------------------


def encode_observed(observed: Observed[Entity]) -> JsonObject:
    """The observed record: its kind, the source it was read from, the entity value.

    >>> from datetime import date
    >>> from leaveimpact.core.ids import employee_id, leave_id
    >>> leave = Leave(leave_id(5), employee_id(17), date(2026, 9, 15), date(2026, 9, 19),
    ...               LeaveKind.ANNUAL, LeaveStatus.APPROVED)
    >>> encode_observed(Observed(leave, Source.FRAPPE))["kind"]
    'leave'
    """
    return {
        "kind": KIND_BY_ENTITY_TYPE[type(observed.value)].value,
        "source": observed.source.value,
        "value": encode_entity(observed.value),
    }


def decode_observed(value: object) -> Observed[Entity]:
    """The observed record ``value`` encodes, through the constructor's source-holds-kind check."""
    data = as_object(value, "an observed record")
    expect_fields(data, ("kind", "source", "value"), "an observed record")
    kind = EntityKind(string_field(data, "kind"))
    source = Source(string_field(data, "source"))
    return Observed(decode_entity(kind, object_field(data, "value")), source)


# --- Ids -----------------------------------------------------------------------------------


def _id[K: str](
    data: Mapping[str, object], key: str, kind: EntityKind, as_kind: Callable[[str], K]
) -> K:
    return as_kind(require_id(kind, string_field(data, key)))


def _employee_id(value: str) -> EmployeeId:
    return EmployeeId(require_id(EntityKind.EMPLOYEE, value))


def _employee_ids(data: Mapping[str, object], key: str) -> tuple[EmployeeId, ...]:
    return tuple(_employee_id(string_item(item, key)) for item in array_field(data, key))
