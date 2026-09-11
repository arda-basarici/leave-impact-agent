"""The Jira adapter against the site, recorded once and replayed on every push.

One scenario end to end: the cassette project dropped, the site prepared (project, the
four custom fields on its screens, an owner option per person), two components and
three work items written — a backlog item, an in-progress item with two dated
comments and a due date, a done item with its resolved date — then everything read
back through the reader's four questions, the absent identities answering ``None``.
The claims are the port's: what the writer added, the reader returns as the same
entity, comments included and in order; a component's members round-trip; the
project's issues are the world's.

Recording (``just test-record``) needs the site and its credential in the
environment; replay needs neither and the cassette host is a placeholder. The project
key is the cassette scope, so a world's project never reads these.
"""

from __future__ import annotations

import os
import time
from datetime import date

import pytest

from leaveimpact.adapters.jira import JiraAdapter, JiraConfig, JiraCredential, JiraSite
from leaveimpact.adapters.transport import Transport
from leaveimpact.core.comments import comment_text
from leaveimpact.core.entities import Comment, Component, WorkItem
from leaveimpact.core.enums import Source, WorkItemStatus
from leaveimpact.core.ids import comment_id, component_id, employee_id, work_item_id
from tests.integration.jira_support import reset_project
from tests.recording import JIRA

pytestmark = [pytest.mark.integration, pytest.mark.vcr]

PROJECT_KEY = "CAS"
PEOPLE = [
    (employee_id(901), "Seda Aksoy"),
    (employee_id(902), "Baran Demir"),
    (employee_id(903), "Deniz Yılmaz"),
]
PAYMENTS = Component(component_id(901), "Payments", (employee_id(901), employee_id(903)))
BILLING = Component(component_id(902), "Billing", (employee_id(902),))
BLOCKED = comment_text(
    comment_id(901),
    date(2026, 9, 10),
    employee_id(903),
    "Deniz Yılmaz",
    "blocked on the vendor API",
)
UPDATE = comment_text(
    comment_id(902),
    date(2026, 9, 11),
    employee_id(901),
    "Seda Aksoy",
    "vendor promised a fix by Friday",
)
BACKLOG = WorkItem(
    work_item_id(901),
    "Rotate API keys",
    employee_id(902),
    WorkItemStatus.TO_DO,
    BILLING.id,
    date(2026, 9, 1),
    None,
    None,
    (),
)
IN_PROGRESS = WorkItem(
    work_item_id(902),
    "Payment retry loop",
    employee_id(903),
    WorkItemStatus.IN_PROGRESS,
    PAYMENTS.id,
    date(2026, 8, 12),
    None,
    date(2026, 9, 20),
    (
        Comment(comment_id(901), date(2026, 9, 10), employee_id(903), BLOCKED),
        Comment(comment_id(902), date(2026, 9, 11), employee_id(901), UPDATE),
    ),
)
DONE = WorkItem(
    work_item_id(903),
    "Licence audit",
    employee_id(901),
    WorkItemStatus.DONE,
    PAYMENTS.id,
    date(2026, 5, 5),
    date(2026, 9, 4),
    None,
    (),
)


def pause(seconds: float) -> None:
    """Real waits while recording (the index has to catch up); none on replay."""
    if JIRA.recording:
        time.sleep(seconds)


def credential() -> JiraCredential:
    if JIRA.recording:
        return JiraCredential(
            os.environ["LEAVE_IMPACT_JIRA_EMAIL"], os.environ["LEAVE_IMPACT_JIRA_TOKEN"]
        )
    return JiraCredential("replay@example.invalid", "replay")


def test_work_written_is_read_back() -> None:
    cred = credential()
    site = JiraSite(base_url=JIRA.base_url, credential=cred, sleep=pause)
    site.ensure_project(PROJECT_KEY, "Cassette World")
    with Transport(base_url=JIRA.base_url, source=Source.JIRA, auth=cred.auth, sleep=pause) as raw:
        reset_project(raw, PROJECT_KEY)
    fields = site.ensure_fields(PROJECT_KEY)
    site.ensure_owner_options(fields, PEOPLE)
    site.close()

    adapter = JiraAdapter(
        base_url=JIRA.base_url,
        credential=cred,
        config=JiraConfig(PROJECT_KEY, fields),
        sleep=pause,
    )

    locators = [adapter.add_component(PAYMENTS), adapter.add_component(BILLING)]
    locators += [
        adapter.add_work_item(BACKLOG),
        adapter.add_work_item(IN_PROGRESS),
        adapter.add_work_item(DONE),
    ]
    assert all(locators) and len(set(locators)) == len(locators)

    components = adapter.components()
    assert all(item.source is Source.JIRA for item in components)
    assert {item.value for item in components} == {PAYMENTS, BILLING}
    payments = adapter.component(PAYMENTS.id)
    assert payments is not None and payments.value == PAYMENTS
    assert adapter.component(component_id(999)) is None

    items = adapter.work_items()
    assert {item.value for item in items} == {BACKLOG, IN_PROGRESS, DONE}
    in_progress = adapter.work_item(IN_PROGRESS.id)
    assert in_progress is not None and in_progress.value == IN_PROGRESS
    assert [comment.id for comment in in_progress.value.comments] == ["comment_901", "comment_902"]
    assert adapter.work_item(work_item_id(999)) is None
    adapter.close()
