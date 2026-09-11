"""The Jira adapter's wire behaviour over a scripted transport: write order, what it refuses.

The claims the cassette cannot make cheaply: a work item's id lands in the last
request, after the create, the comments and the transition, so a fault anywhere before
leaves an issue no read by id will see; a fault in the marker itself is an unknown
outcome and nothing is retried; an owner option or a component held twice is
malformed before anything is written; a successful response that is not JSON is
malformed with the request as locator.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from typing import Any

import httpx
import pytest

from leaveimpact.adapters.jira import JiraAdapter, JiraConfig, JiraCredential, JiraFields
from leaveimpact.adapters.jira.adapter import INDEX_POLLS
from leaveimpact.core.comments import comment_text
from leaveimpact.core.entities import Comment, WorkItem
from leaveimpact.core.enums import WorkItemStatus
from leaveimpact.core.ids import comment_id, component_id, employee_id, work_item_id
from leaveimpact.core.ports.errors import MalformedRecord, SourceUnreachable

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


COMPONENTS = ok([{"id": "10001", "name": "Payments", "description": "comp_003 · members: emp_001"}])
CONTEXT = ok({"values": [{"id": "10200"}]})
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
