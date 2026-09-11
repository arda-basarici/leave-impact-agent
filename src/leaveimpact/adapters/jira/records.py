"""Jira record shapes, both directions: issue and component JSON to domain entities and back.

Pure: dictionaries in, entities or payloads out, so where each fact lives on a Jira
issue is testable without a site. The adapter (``adapter``) owns the wire.

**Where the facts live.** A work item is an issue in the world's project. Its id is a
short-text custom field (``Ticket Id``), its owner the ``Synthetic Owner`` select whose
option value is ``emp_017 — Alice Demir`` (the id before the dash is read, the name is
for a human reading the board — DESIGN's owner shape), its opened and resolved dates
two custom date fields (Jira's ``created`` and ``resolutiondate`` cannot be set over
REST, so they are vendor time and never read), its due date Jira's own due date (a
date a user sets, not a timestamp), its component the issue's single Jira component,
its status the workflow status by name, its comments the issue's comments with the
bracketed prefix ``core.comments`` defines. A component is a Jira component of the
project; Jira components have no member list, so the component's id and its members
live in the description in a fixed shape (``comp_003 · members: emp_001, emp_004``),
read the way a custom field is.

**The status table** is the kanban template's workflow: a new issue is in Backlog, and
the two other domain states are the template's In Progress and Done. Its fourth
status, Selected for Development, is one the world never plants, so reading it is
malformed rather than folded into a neighbour.

**Malformed means untranslatable.** A missing id, an option value without the id
prefix, a status or a date outside the tables, a comment without its prefix, more or
fewer than one component — each raises ``MalformedRecord`` with the issue key or
component id as locator.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, cast

from leaveimpact.core.comments import parse_comment
from leaveimpact.core.entities import Comment, Component, WorkItem
from leaveimpact.core.enums import Source, WorkItemStatus
from leaveimpact.core.ids import NUMBERED_ID, ComponentId, EmployeeId, WorkItemId
from leaveimpact.core.ports.errors import MalformedRecord

# The custom fields the records live in, by their site-wide names.
TICKET_ID_FIELD = "Ticket Id"
OWNER_FIELD = "Synthetic Owner"
OPENED_ON_FIELD = "Opened On"
RESOLVED_ON_FIELD = "Resolved On"

STATUS_NAME_BY_STATUS: dict[WorkItemStatus, str] = {
    WorkItemStatus.TO_DO: "Backlog",
    WorkItemStatus.IN_PROGRESS: "In Progress",
    WorkItemStatus.DONE: "Done",
}
STATUS_BY_STATUS_NAME: dict[str, WorkItemStatus] = {
    name: status for status, name in STATUS_NAME_BY_STATUS.items()
}
INITIAL_STATUS = WorkItemStatus.TO_DO

OWNER_SEPARATOR = " — "
_MEMBERS = re.compile(r"^(?P<id>comp_[0-9]{3,}) · members:(?P<members>.*)$")


def owner_option(employee_id: EmployeeId, name: str) -> str:
    """The select option value for a person: the id, then the name a board reader sees.

    >>> from leaveimpact.core.ids import employee_id
    >>> owner_option(employee_id(17), "Alice Demir")
    'emp_017 — Alice Demir'
    """
    return f"{employee_id}{OWNER_SEPARATOR}{name}"


def owner_from_option(value: str, locator: str) -> EmployeeId:
    head, separator, _ = value.partition(OWNER_SEPARATOR)
    if not separator or not NUMBERED_ID.match(head):
        raise MalformedRecord(
            Source.JIRA, locator, f"owner option {value!r} carries no employee id"
        )
    return EmployeeId(head)


# --- components ------------------------------------------------------------------------


def component_description(component: Component) -> str:
    """The description that carries a component's id and members.

    >>> from leaveimpact.core.ids import component_id, employee_id
    >>> payments = Component(component_id(3), "Payments", (employee_id(1), employee_id(4)))
    >>> component_description(payments)
    'comp_003 · members: emp_001, emp_004'
    """
    return f"{component.id} · members: {', '.join(component.member_ids)}"


def component_from_record(record: dict[str, Any]) -> Component:
    """A project component, as Jira lists it, read through its description.

    >>> component_from_record({"id": "10001", "name": "Payments",
    ...                        "description": "comp_003 · members: emp_001, emp_004"})
    Component(id='comp_003', name='Payments', member_ids=('emp_001', 'emp_004'))
    >>> component_from_record({"id": "2", "name": "Loose", "description": "comp_004 · members:"})
    Component(id='comp_004', name='Loose', member_ids=())
    """
    locator = f"component/{record.get('id', '?')}"
    match = _MEMBERS.match(str(record.get("description") or ""))
    if match is None:
        raise MalformedRecord(Source.JIRA, locator, "description carries no component id")
    members = tuple(part.strip() for part in match["members"].split(",") if part.strip())
    for member in members:
        if not NUMBERED_ID.match(member):
            raise MalformedRecord(Source.JIRA, locator, f"member {member!r} is not an employee id")
    name = record.get("name")
    if not isinstance(name, str) or not name:
        raise MalformedRecord(Source.JIRA, locator, "no name")
    return Component(
        ComponentId(match["id"]), name, tuple(EmployeeId(member) for member in members)
    )


# --- work items ------------------------------------------------------------------------


def issue_fields(
    work_item: WorkItem,
    *,
    project_key: str,
    component_name: str,
    owner_option_value: str,
    owner_field: str,
    opened_on_field: str,
    resolved_on_field: str,
) -> dict[str, Any]:
    """The ``fields`` of the create request — everything but the id, which lands last."""
    fields: dict[str, Any] = {
        "project": {"key": project_key},
        "issuetype": {"name": "Task"},
        "summary": work_item.title,
        "components": [{"name": component_name}],
        owner_field: {"value": owner_option_value},
        opened_on_field: work_item.opened_on.isoformat(),
    }
    if work_item.resolved_on is not None:
        fields[resolved_on_field] = work_item.resolved_on.isoformat()
    if work_item.due_on is not None:
        fields["duedate"] = work_item.due_on.isoformat()
    return fields


def comment_body(text: str) -> dict[str, Any]:
    """A comment's text as the Atlassian document Jira's v3 API wants: one paragraph."""
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def document_text(body: Any) -> str:
    """Every text node of an Atlassian document, in order, joined — the inverse of ``comment_body``.

    >>> document_text(comment_body("a remark"))
    'a remark'
    """
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            node_dict = cast(dict[str, Any], node)
            if node_dict.get("type") == "text":
                parts.append(str(node_dict.get("text", "")))
            for child in cast(list[Any], node_dict.get("content") or []):
                walk(child)
        elif isinstance(node, list):
            for child in cast(list[Any], node):
                walk(child)

    walk(body)
    return "".join(parts)


def _date(value: Any, what: str, locator: str) -> date:
    if not isinstance(value, str):
        raise MalformedRecord(Source.JIRA, locator, f"no {what}")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MalformedRecord(Source.JIRA, locator, f"{what} {value!r} is not a date") from exc


def comment_from_record(record: dict[str, Any], locator: str) -> Comment:
    text = document_text(record.get("body"))
    try:
        return parse_comment(text)
    except ValueError as exc:
        raise MalformedRecord(
            Source.JIRA, f"{locator}/comment/{record.get('id', '?')}", str(exc)
        ) from exc


def work_item_from_record(
    record: dict[str, Any],
    *,
    ticket_id_field: str,
    owner_field: str,
    opened_on_field: str,
    resolved_on_field: str,
    component_by_name: dict[str, ComponentId],
    comments: list[dict[str, Any]],
) -> WorkItem:
    """An issue as the search returns it, with its comments already fetched to completion."""
    key = str(record.get("key", "?"))
    locator = f"issue/{key}"
    fields: Any = record.get("fields")
    if not isinstance(fields, dict):
        raise MalformedRecord(Source.JIRA, locator, "no fields")
    fields_dict = cast(dict[str, Any], fields)
    ticket_id = fields_dict.get(ticket_id_field)
    if not isinstance(ticket_id, str) or not NUMBERED_ID.match(ticket_id):
        raise MalformedRecord(Source.JIRA, locator, f"no {TICKET_ID_FIELD}")
    title = fields_dict.get("summary")
    if not isinstance(title, str) or not title:
        raise MalformedRecord(Source.JIRA, locator, "no summary")
    owner_raw: Any = fields_dict.get(owner_field)
    owner = cast(dict[str, Any], owner_raw) if isinstance(owner_raw, dict) else {}
    if not isinstance(owner.get("value"), str):
        raise MalformedRecord(Source.JIRA, locator, f"no {OWNER_FIELD}")
    status_raw: Any = fields_dict.get("status")
    status = cast(dict[str, Any], status_raw) if isinstance(status_raw, dict) else {}
    status_name = status.get("name")
    if status_name not in STATUS_BY_STATUS_NAME:
        raise MalformedRecord(
            Source.JIRA, locator, f"status {status_name!r} is not one the domain knows"
        )
    components_raw: Any = fields_dict.get("components") or []
    components = cast(list[Any], components_raw) if isinstance(components_raw, list) else []
    if len(components) != 1:
        raise MalformedRecord(
            Source.JIRA,
            locator,
            f"{len(components)} components, not one",
        )
    first: Any = components[0]
    component_name = cast(dict[str, Any], first).get("name") if isinstance(first, dict) else None
    if component_name not in component_by_name:
        raise MalformedRecord(
            Source.JIRA, locator, f"component {component_name!r} is not one the project holds"
        )
    resolved_raw = fields_dict.get(resolved_on_field)
    due_raw = fields_dict.get("duedate")
    return WorkItem(
        id=WorkItemId(ticket_id),
        title=title,
        owner_id=owner_from_option(str(owner["value"]), locator),
        status=STATUS_BY_STATUS_NAME[status_name],
        component_id=component_by_name[component_name],
        opened_on=_date(fields_dict.get(opened_on_field), OPENED_ON_FIELD, locator),
        resolved_on=_date(resolved_raw, RESOLVED_ON_FIELD, locator)
        if resolved_raw is not None
        else None,
        due_on=_date(due_raw, "due date", locator) if due_raw is not None else None,
        comments=tuple(comment_from_record(comment, locator) for comment in comments),
    )
