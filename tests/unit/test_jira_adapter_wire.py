"""The Jira adapter's wire behaviour over a scripted transport: write order, what it refuses.

The claims the cassette cannot make cheaply: a work item's id lands in the last
request, after the create, the comments and the transition, so a fault anywhere before
leaves an issue no read by id will see; the marker itself is retried on a lost
response, and when every attempt is lost the issue is asked directly whether the id
landed; an owner option or a component held twice is malformed before anything is
written; a successful response that is not JSON is malformed with the request as
locator.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx
import pytest

from leaveimpact.adapters.jira import (
    JiraAdapter,
    JiraConfig,
    JiraCredential,
    JiraFields,
    JiraSite,
)
from leaveimpact.adapters.jira.adapter import INDEX_POLLS
from leaveimpact.core.comments import comment_text
from leaveimpact.core.entities import Comment, WorkItem
from leaveimpact.core.enums import WorkItemStatus
from leaveimpact.core.ids import comment_id, component_id, employee_id, work_item_id
from leaveimpact.core.ports.errors import IdentityConflict, MalformedRecord, SourceUnreachable

Outcome = httpx.Response | Exception


class Scripted:
    def __init__(self, *outcomes: Outcome) -> None:
        self.seen: list[httpx.Request] = []
        self._outcomes: Iterator[Outcome] = iter(outcomes)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        outcome = next(self._outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


FIELDS = JiraFields(
    ticket_id="customfield_10078",
    owner="customfield_10042",
    opened_on="customfield_10076",
    resolved_on="customfield_10077",
)


def adapter(script: Scripted, pauses: list[float] | None = None) -> JiraAdapter:
    return JiraAdapter(
        base_url="https://jira.invalid",
        credential=JiraCredential("e", "t"),
        config=JiraConfig("CAS", FIELDS),
        sleep=pauses.append if pauses is not None else (lambda _: None),
        httpx_transport=httpx.MockTransport(script.handler),
    )


def ok(payload: Any, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def site(script: Scripted) -> JiraSite:
    return JiraSite(
        base_url="https://jira.invalid",
        credential=JiraCredential("e", "t"),
        sleep=lambda _: None,
        httpx_transport=httpx.MockTransport(script.handler),
    )


def custom_field(id: str, name: str, kind: str) -> dict[str, Any]:
    return {
        "id": id,
        "name": name,
        "custom": True,
        "schema": {"custom": f"com.atlassian.jira.plugin.system.customfieldtypes:{kind}"},
    }


COMPONENTS = ok([{"id": "10001", "name": "Payments", "description": "comp_003 · members: emp_001"}])
CONTEXT = ok({"values": [{"id": "10200", "name": "CAS owners"}], "isLast": True})
OPTIONS = ok({"values": [{"value": "emp_004 — Deniz Yılmaz"}], "isLast": True})
REMARK = comment_text(comment_id(5), date(2026, 9, 12), employee_id(4), "Deniz Yılmaz", "blocked")
TICKET = WorkItem(
    work_item_id(7),
    "Payment retry loop",
    employee_id(4),
    WorkItemStatus.IN_PROGRESS,
    component_id(3),
    date(2026, 8, 12),
    None,
    None,
    (Comment(comment_id(5), date(2026, 9, 12), employee_id(4), REMARK),),
)


def paths(script: Scripted) -> list[str]:
    return [f"{request.method} {request.url.path}" for request in script.seen]


def test_a_work_item_is_written_in_order_and_its_id_lands_last() -> None:
    script = Scripted(
        COMPONENTS,
        CONTEXT,
        OPTIONS,
        ok({"id": "10001", "key": "CAS-1"}, 201),
        ok({"id": "10100"}, 201),
        ok(
            {
                "transitions": [
                    {"id": "21", "to": {"name": "In Progress"}},
                    {"id": "31", "to": {"name": "Done"}},
                ]
            }
        ),
        httpx.Response(204),
        httpx.Response(204),
        ok({"issues": [], "isLast": True}),  # the index trails for one poll
        ok({"issues": [{"key": "CAS-1", "fields": {}}], "isLast": True}),
    )
    pauses: list[float] = []
    assert adapter(script, pauses).add_work_item(TICKET) == "CAS-1"
    assert paths(script) == [
        "GET /rest/api/3/project/CAS/components",
        "GET /rest/api/3/field/customfield_10042/context",
        "GET /rest/api/3/field/customfield_10042/context/10200/option",
        "POST /rest/api/3/issue",
        "POST /rest/api/3/issue/CAS-1/comment",
        "GET /rest/api/3/issue/CAS-1/transitions",
        "POST /rest/api/3/issue/CAS-1/transitions",
        "PUT /rest/api/3/issue/CAS-1",
        "POST /rest/api/3/search/jql",
        "POST /rest/api/3/search/jql",
    ]
    assert pauses == [0.5], "one pause while the index caught up"
    poll = json.loads(script.seen[-1].content)
    assert poll["jql"] == 'project = "CAS" AND cf[10078] ~ "ticket_007"'
    assert poll["reconcileIssues"] == [10001]
    create = json.loads(script.seen[3].content)["fields"]
    assert "customfield_10078" not in create
    assert create["customfield_10042"] == {"value": "emp_004 — Deniz Yılmaz"}
    assert json.loads(script.seen[6].content) == {"transition": {"id": "21"}}
    assert json.loads(script.seen[7].content) == {"fields": {"customfield_10078": "ticket_007"}}


def test_a_lost_marker_response_is_retried_because_setting_the_id_twice_is_one_world() -> None:
    script = Scripted(
        COMPONENTS,
        CONTEXT,
        OPTIONS,
        ok({"id": "10002", "key": "CAS-2"}, 201),
        httpx.ReadTimeout("marker response lost"),
        httpx.Response(204),
        ok({"issues": [{"key": "CAS-2", "fields": {}}], "isLast": True}),
    )
    backlog = WorkItem(
        work_item_id(8),
        "Small",
        employee_id(4),
        WorkItemStatus.TO_DO,
        component_id(3),
        date(2026, 8, 12),
        None,
        None,
        (),
    )
    pauses: list[float] = []
    assert adapter(script, pauses).add_work_item(backlog) == "CAS-2"
    assert paths(script)[-3:] == [
        "PUT /rest/api/3/issue/CAS-2",
        "PUT /rest/api/3/issue/CAS-2",
        "POST /rest/api/3/search/jql",
    ]
    assert pauses == [2.0], "the transport's backoff before the second marker attempt"


def test_a_marker_lost_on_every_attempt_is_reconciled_by_asking_the_issue() -> None:
    script = Scripted(
        COMPONENTS,
        CONTEXT,
        OPTIONS,
        ok({"id": "10002", "key": "CAS-2"}, 201),
        httpx.ReadTimeout("lost"),
        httpx.ReadTimeout("lost"),
        httpx.ReadTimeout("lost"),
        ok({"key": "CAS-2", "fields": {"customfield_10078": "ticket_008"}}),
        ok({"issues": [{"key": "CAS-2", "fields": {}}], "isLast": True}),
    )
    backlog = WorkItem(
        work_item_id(8),
        "Small",
        employee_id(4),
        WorkItemStatus.TO_DO,
        component_id(3),
        date(2026, 8, 12),
        None,
        None,
        (),
    )
    assert adapter(script, []).add_work_item(backlog) == "CAS-2"
    assert paths(script)[-2:] == ["GET /rest/api/3/issue/CAS-2", "POST /rest/api/3/search/jql"]


def test_a_marker_that_never_landed_keeps_the_fault() -> None:
    script = Scripted(
        COMPONENTS,
        CONTEXT,
        OPTIONS,
        ok({"id": "10002", "key": "CAS-2"}, 201),
        httpx.ReadTimeout("lost"),
        httpx.ReadTimeout("lost"),
        httpx.ReadTimeout("lost"),
        ok({"key": "CAS-2", "fields": {"customfield_10078": None}}),
    )
    backlog = WorkItem(
        work_item_id(8),
        "Small",
        employee_id(4),
        WorkItemStatus.TO_DO,
        component_id(3),
        date(2026, 8, 12),
        None,
        None,
        (),
    )
    with pytest.raises(SourceUnreachable, match="ReadTimeout on all 3 attempts"):
        adapter(script, []).add_work_item(backlog)


def test_a_field_name_held_twice_is_malformed_before_any_write() -> None:
    listing = ok([custom_field("customfield_1", "Ticket Id", "textfield"),
                  custom_field("customfield_2", "Ticket Id", "textfield")])
    script = Scripted(listing)
    with pytest.raises(MalformedRecord) as caught:
        site(script).ensure_fields("CAS")
    assert caught.value.locator == "GET /field"
    assert "'Ticket Id' is held by 2 custom fields (customfield_1, customfield_2)" in (
        caught.value.reason
    )
    assert len(script.seen) == 1


def test_an_existing_field_of_another_type_is_malformed_not_adopted() -> None:
    script = Scripted(ok([custom_field("customfield_9", "Ticket Id", "datepicker")]))
    with pytest.raises(MalformedRecord) as caught:
        site(script).ensure_fields("CAS")
    assert caught.value.locator == "field/customfield_9"
    assert "not a 'com.atlassian.jira.plugin.system.customfieldtypes:textfield'" in (
        caught.value.reason
    )


def test_a_missing_owner_context_is_the_callers_ordering_bug() -> None:
    no_context = ok(
        {"values": [{"id": "10001", "name": "Default Configuration Scheme"}], "isLast": True}
    )
    with pytest.raises(LookupError, match="no owner context"):
        adapter(Scripted(COMPONENTS, no_context)).add_work_item(TICKET)


def test_an_insert_answering_without_its_key_is_malformed() -> None:
    script = Scripted(COMPONENTS, CONTEXT, OPTIONS, ok({"self": "x"}, 201))
    with pytest.raises(MalformedRecord) as caught:
        adapter(script).add_work_item(TICKET)
    assert (caught.value.locator, caught.value.reason) == ("POST /issue", "no key")


def test_a_fault_before_the_marker_leaves_no_readable_item_and_no_retry() -> None:
    script = Scripted(
        COMPONENTS, CONTEXT, OPTIONS, ok({"key": "CAS-1"}, 201), httpx.ReadTimeout("lost")
    )
    with pytest.raises(SourceUnreachable) as caught:
        adapter(script).add_work_item(TICKET)
    assert "outcome unknown" in caught.value.reason
    assert paths(script)[-1] == "POST /rest/api/3/issue/CAS-1/comment"
    assert not any(path.startswith("PUT") for path in paths(script)), "the id never landed"


def test_a_backlog_item_needs_no_transition() -> None:
    backlog = WorkItem(
        work_item_id(8),
        "Small",
        employee_id(4),
        WorkItemStatus.TO_DO,
        component_id(3),
        date(2026, 8, 12),
        None,
        None,
        (),
    )
    script = Scripted(
        COMPONENTS,
        CONTEXT,
        OPTIONS,
        ok({"id": "10002", "key": "CAS-2"}, 201),
        httpx.Response(204),
        ok({"issues": [{"key": "CAS-2", "fields": {}}], "isLast": True}),
    )
    adapter(script).add_work_item(backlog)
    assert paths(script)[-3:] == [
        "POST /rest/api/3/issue",
        "PUT /rest/api/3/issue/CAS-2",
        "POST /rest/api/3/search/jql",
    ]


def test_an_index_that_never_catches_up_is_unreachable_after_the_polls() -> None:
    script = Scripted(
        COMPONENTS,
        CONTEXT,
        OPTIONS,
        ok({"id": "10002", "key": "CAS-2"}, 201),
        httpx.Response(204),
        *(ok({"issues": [], "isLast": True}) for _ in range(INDEX_POLLS)),
    )
    backlog = WorkItem(
        work_item_id(8),
        "Small",
        employee_id(4),
        WorkItemStatus.TO_DO,
        component_id(3),
        date(2026, 8, 12),
        None,
        None,
        (),
    )
    pauses: list[float] = []
    with pytest.raises(
        SourceUnreachable, match=f"not in the search index after {INDEX_POLLS} polls"
    ):
        adapter(script, pauses).add_work_item(backlog)
    assert len(pauses) == INDEX_POLLS


def test_a_workflow_without_the_target_status_is_malformed() -> None:
    script = Scripted(
        COMPONENTS,
        CONTEXT,
        OPTIONS,
        ok({"key": "CAS-1"}, 201),
        ok({"id": "10100"}, 201),
        ok({"transitions": [{"id": "31", "to": {"name": "Done"}}]}),
    )
    with pytest.raises(MalformedRecord, match="no single transition to 'In Progress'"):
        adapter(script).add_work_item(TICKET)


def test_an_owner_held_by_two_options_is_malformed_before_any_write() -> None:
    doubled = ok(
        {
            "values": [{"value": "emp_004 — Deniz"}, {"value": "emp_004 — Deniz Yılmaz"}],
            "isLast": True,
        }
    )
    script = Scripted(COMPONENTS, CONTEXT, doubled)
    with pytest.raises(MalformedRecord, match="held by more than one owner option"):
        adapter(script).add_work_item(TICKET)
    assert not any(path.startswith("POST") for path in paths(script))


def test_a_component_held_twice_is_malformed_on_select() -> None:
    twice = ok(
        [
            {"id": "1", "name": "Payments", "description": "comp_003 · members: emp_001"},
            {"id": "2", "name": "Billing", "description": "comp_003 · members:"},
        ]
    )
    with pytest.raises(MalformedRecord, match="held by more than one component"):
        adapter(Scripted(twice)).component(component_id(3))


def test_missing_links_are_the_callers_ordering_bug() -> None:
    with pytest.raises(LookupError, match="add components first"):
        adapter(Scripted(ok([]))).add_work_item(TICKET)
    no_option = ok({"values": [], "isLast": True})
    with pytest.raises(LookupError, match="no owner option"):
        adapter(Scripted(COMPONENTS, CONTEXT, no_option)).add_work_item(TICKET)


def test_a_successful_response_that_is_not_json_is_malformed() -> None:
    with pytest.raises(MalformedRecord) as caught:
        adapter(Scripted(httpx.Response(200, text="<html>"))).components()
    assert caught.value.locator == "GET /project/CAS/components"
    assert caught.value.reason == "response is not JSON"


def test_work_items_reads_the_project_by_id_field_and_pages_comments_to_completion() -> None:
    embedded: dict[str, Any] = {
        "comments": [{"id": "1", "body": {"type": "doc", "content": []}}],
        "total": 2,
    }
    page = ok(
        {
            "issues": [
                {
                    "key": "CAS-1",
                    "fields": {
                        "summary": "Payment retry loop",
                        "status": {"name": "Backlog"},
                        "duedate": None,
                        "components": [{"name": "Payments"}],
                        "comment": embedded,
                        "customfield_10078": "ticket_007",
                        "customfield_10042": {"value": "emp_004 — Deniz Yılmaz"},
                        "customfield_10076": "2026-08-12",
                        "customfield_10077": None,
                    },
                }
            ],
            "isLast": True,
        }
    )
    full = ok(
        {
            "comments": [
                {"id": "1", "body": {"type": "doc", "content": [{"type": "text", "text": REMARK}]}},
                {
                    "id": "2",
                    "body": {
                        "type": "doc",
                        "content": [
                            {"type": "text", "text": REMARK.replace("comment_005", "comment_006")}
                        ],
                    },
                },
            ],
            "total": 2,
        }
    )
    script = Scripted(COMPONENTS, page, full)
    (item,) = adapter(script).work_items()
    assert [comment.id for comment in item.value.comments] == ["comment_005", "comment_006"]
    search = json.loads(script.seen[1].content)
    assert search["jql"] == 'project = "CAS" AND cf[10078] is not EMPTY'
    assert paths(script)[-1] == "GET /rest/api/3/issue/CAS-1/comment"


# --- The project mark and the debris query --------------------------------------------------

VERSION = "a" * 64


def project(description: str | None) -> httpx.Response:
    return ok({"id": "10000", "key": "CAS", "description": description})


def test_a_project_created_carries_the_world_s_mark() -> None:
    script = Scripted(
        ok({"errorMessages": ["No project"]}, 404), ok({"accountId": "me"}), ok({"key": "CAS"}, 201)
    )
    site(script).ensure_project("CAS", "Leave Impact world aaaaaaaa", world_version=VERSION)
    created = script.seen[2]
    assert json.loads(created.content)["description"] == f"world {VERSION}"


def test_a_project_marked_for_this_world_needs_no_write() -> None:
    script = Scripted(project(f"world {VERSION}"))
    site(script).mark_project("CAS", VERSION)
    assert paths(script) == ["GET /rest/api/3/project/CAS"]


def test_an_unmarked_project_is_marked_now() -> None:
    script = Scripted(project(""), ok({"key": "CAS"}, 200))
    site(script).mark_project("CAS", VERSION)
    assert paths(script) == ["GET /rest/api/3/project/CAS", "PUT /rest/api/3/project/CAS"]
    assert json.loads(script.seen[1].content) == {"description": f"world {VERSION}"}
    script = Scripted(project(None), ok(None, 204))
    site(script).mark_project("CAS", VERSION)
    assert len(script.seen) == 2


def test_a_project_marked_for_another_world_is_an_identity_conflict() -> None:
    script = Scripted(project("world " + "b" * 64))
    with pytest.raises(IdentityConflict, match="this world is 'world aaaa") as caught:
        site(script).mark_project("CAS", VERSION)
    assert caught.value.locator == "project/CAS"
    assert len(script.seen) == 1, "nothing written over another world's mark"


def issue(key: str, marker: object) -> dict[str, Any]:
    return {"key": key, "fields": {FIELDS.ticket_id: marker}}


def test_held_markers_reads_every_issue_in_the_project_and_returns_the_markers() -> None:
    page = ok(
        {"issues": [issue("CAS-1", "ticket_007"), issue("CAS-2", "ticket_008")], "isLast": True}
    )
    script = Scripted(page)
    held = site(script).held_markers("CAS", FIELDS)
    assert held == {work_item_id(7), work_item_id(8)}
    body = json.loads(script.seen[0].content)
    assert body["jql"] == 'project = "CAS"' and body["fields"] == [FIELDS.ticket_id]
    assert "reconcileIssues" not in body, "the site inspects, it reconciles nothing of its own"


def test_an_unmarked_issue_or_a_marker_held_twice_is_projection_debris() -> None:
    debris = ok(
        {
            "issues": [
                issue("CAS-1", "ticket_007"),
                issue("CAS-2", None),
                issue("CAS-3", "ticket_007"),
                issue("CAS-4", "LIA-42"),
            ],
            "isLast": True,
        }
    )
    with pytest.raises(MalformedRecord) as caught:
        site(Scripted(debris)).held_markers("CAS", FIELDS)
    assert caught.value.locator == "project/CAS"
    assert "unmarked issues ['CAS-2', 'CAS-4']" in caught.value.reason
    assert "markers held twice {'ticket_007': ['CAS-1', 'CAS-3']}" in caught.value.reason
    assert caught.value.reason.endswith("projection debris, delete before rerunning")
