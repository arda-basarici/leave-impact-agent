"""The Jira translation, both directions, without a site.

The claims: a create payload carries every fact where the read expects it and never the
id, which lands last; an issue as the search returns it, with its comments, translates
back to the same work item; a component round-trips through its description; and every
way a record can fail translation — no id, an owner option without the id, a status or
date outside the tables, not exactly one component, a comment without its prefix —
raises ``MalformedRecord`` naming the record.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from leaveimpact.adapters.jira import records
from leaveimpact.core.comments import comment_text
from leaveimpact.core.entities import Comment, Component, WorkItem
from leaveimpact.core.enums import WorkItemStatus
from leaveimpact.core.ids import comment_id, component_id, employee_id, work_item_id
from leaveimpact.core.ports.errors import MalformedRecord

PAYMENTS = Component(component_id(3), "Payments", (employee_id(1), employee_id(4)))
REMARK = comment_text(comment_id(5), date(2026, 9, 12), employee_id(4), "Deniz Yılmaz", "blocked")
TICKET = WorkItem(
    id=work_item_id(7),
    title="Payment retry loop",
    owner_id=employee_id(4),
    status=WorkItemStatus.IN_PROGRESS,
    component_id=PAYMENTS.id,
    opened_on=date(2026, 8, 12),
    resolved_on=None,
    due_on=date(2026, 9, 20),
    comments=(Comment(comment_id(5), date(2026, 9, 12), employee_id(4), REMARK),),
)
FIELDS = dict(
    ticket_id_field="customfield_10078",
    owner_field="customfield_10042",
    opened_on_field="customfield_10076",
    resolved_on_field="customfield_10077",
)


def issue(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "summary": "Payment retry loop",
        "status": {"name": "In Progress"},
        "duedate": "2026-09-20",
        "components": [{"name": "Payments"}],
        "customfield_10078": "ticket_007",
        "customfield_10042": {"value": "emp_004 — Deniz Yılmaz"},
        "customfield_10076": "2026-08-12",
        "customfield_10077": None,
    }
    fields.update(overrides)
    return {"key": "CAS-1", "fields": fields}


COMMENTS = [{"id": "10100", "body": records.comment_body(REMARK)}]
COMPONENTS = {"Payments": PAYMENTS.id}


def test_create_fields_carry_every_fact_but_the_id() -> None:
    fields = records.issue_fields(
        TICKET,
        project_key="CAS",
        component_name="Payments",
        owner_option_value="emp_004 — Deniz Yılmaz",
        owner_field="customfield_10042",
        opened_on_field="customfield_10076",
        resolved_on_field="customfield_10077",
    )
    assert fields["project"] == {"key": "CAS"} and fields["summary"] == "Payment retry loop"
    assert fields["components"] == [{"name": "Payments"}]
    assert fields["customfield_10042"] == {"value": "emp_004 — Deniz Yılmaz"}
    assert fields["customfield_10076"] == "2026-08-12" and fields["duedate"] == "2026-09-20"
    assert "customfield_10077" not in fields, "an open item has no resolved date"
    assert "customfield_10078" not in fields, "the id lands last, never on create"


def test_an_issue_translates_back_with_its_comments() -> None:
    got = records.work_item_from_record(
        issue(), component_by_name=COMPONENTS, comments=COMMENTS, **FIELDS
    )
    assert got == TICKET


def test_a_resolved_issue_reads_its_resolved_date() -> None:
    got = records.work_item_from_record(
        issue(**{"customfield_10077": "2026-09-01", "status": {"name": "Done"}, "duedate": None}),
        component_by_name=COMPONENTS,
        comments=[],
        **FIELDS,
    )
    assert (got.status, got.resolved_on, got.due_on, got.comments) == (
        WorkItemStatus.DONE,
        date(2026, 9, 1),
        None,
        (),
    )


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"customfield_10078": None}, "no Ticket Id"),
        (
            {"customfield_10042": {"value": "Deniz Yılmaz"}},
            "owner option 'Deniz Yılmaz' carries no employee id",
        ),
        (
            {"status": {"name": "Selected for Development"}},
            "status 'Selected for Development' is not one the domain knows",
        ),
        ({"components": []}, "0 components, not one"),
        ({"components": [{"name": "Payments"}, {"name": "Billing"}]}, "2 components, not one"),
        ({"components": [{"name": "Billing"}]}, "component 'Billing' is not one the project holds"),
        ({"customfield_10076": "12/08/2026"}, "Opened On '12/08/2026' is not a date"),
        ({"customfield_10076": None}, "no Opened On"),
    ],
)
def test_an_untranslatable_issue_is_malformed_by_key(
    overrides: dict[str, Any], reason: str
) -> None:
    with pytest.raises(MalformedRecord) as caught:
        records.work_item_from_record(
            issue(**overrides), component_by_name=COMPONENTS, comments=COMMENTS, **FIELDS
        )
    assert caught.value.locator == "issue/CAS-1"
    assert caught.value.reason == reason


def test_a_comment_without_its_prefix_is_malformed_by_comment() -> None:
    bare = [{"id": "10101", "body": records.comment_body("blocked on the vendor")}]
    with pytest.raises(MalformedRecord) as caught:
        records.work_item_from_record(
            issue(), component_by_name=COMPONENTS, comments=bare, **FIELDS
        )
    assert caught.value.locator == "issue/CAS-1/comment/10101"
    assert caught.value.reason.startswith("no comment prefix")


def test_a_component_round_trips_through_its_description() -> None:
    description = records.component_description(PAYMENTS)
    assert description == "comp_003 · members: emp_001, emp_004"
    got = records.component_from_record(
        {"id": "10001", "name": "Payments", "description": description}
    )
    assert got == PAYMENTS


@pytest.mark.parametrize(
    ("record", "reason"),
    [
        (
            {"id": "1", "name": "Payments", "description": "the payments area"},
            "description carries no component id",
        ),
        (
            {"id": "1", "name": "Payments", "description": "comp_003 · members: alice"},
            "member 'alice' is not an employee id",
        ),
        ({"id": "1", "name": "", "description": "comp_003 · members: emp_001"}, "no name"),
    ],
)
def test_an_untranslatable_component_is_malformed(record: dict[str, Any], reason: str) -> None:
    with pytest.raises(MalformedRecord) as caught:
        records.component_from_record(record)
    assert caught.value.locator == "component/1" and caught.value.reason == reason


def test_document_text_walks_nested_content() -> None:
    body = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "a "}, {"type": "text", "text": "b"}],
            },
            {"type": "paragraph", "content": [{"type": "text", "text": "c"}]},
        ],
    }
    assert records.document_text(body) == "a bc"
