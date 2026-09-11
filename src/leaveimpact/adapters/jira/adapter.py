"""The Jira adapter: the work reader and writer over REST v3, and the site preparation beside them.

Two classes over one wire. ``JiraAdapter`` implements both work ports for one project,
configured with the custom field ids it reads and writes — configured, never
discovered at construction, per the step 9 ruling — and ``JiraSite`` is the preparation
the composition root runs first: the project, the custom fields resolved by name and
placed on the project's screens (their ids are what the manifest records and the
adapter is then handed), the owner options for the world's people. The split is the
chicken and the egg: the adapter's configuration is the preparation's result.

**Scope.** Every read is a JQL search inside the configured project and every write
lands in it, so one site holds a project per world version and the cassette project
beside them. The owner select's options live in a field context scoped to the project
(``JiraSite.ensure_owner_options`` creates it), because employee ids restart at one in
every generated world and a site-wide option list would hold ``emp_001`` twice with two
names (a review finding). The identity map is not configured: a work item carries its
id in a custom field, a component in its description, an owner in an option value of
the project's context, so a link resolves by listing the project's components or
options when a call needs them. A domain id matches exactly one record or the record
is malformed.

**Identity lands last.** Jira cannot create an issue in a status, and each comment is
its own request, so a work item is several writes and a fault between them would leave
a half-written issue. The ticket id field is set in the final request: until then the
issue has no id, no read by id sees it, ``work_items`` excludes it, and the projector's
restart — find by id, not found, add — creates the item whole a second time. The
orphan stays in Jira without an id, invisible to the domain, and the cassette reset
deletes it. Reads and the transition lookup are replayable; every write is not, except
the marker itself: setting a field to a value is the same world whether it lands once
or twice, so the marker is declared replayable and a lost response retries it rather
than raising with the id possibly committed and the index still blind to it (a review
finding). When the whole budget is lost, the adapter still knows the key and asks the
issue itself, a database read, whether the id landed, and returns the key if so; only
a source down through both budgets is left ambiguous, by which time the index has had
as long to catch up, and the projector's duplicate check names the rest.

**Reading your own writes.** JQL search runs on an index that trails the database by
moments, so a read straight after a write can miss the item or show its old status
(the first recording did; a freshly created project's issues were absent for seconds).
So ``add_work_item`` returns only once its item is readable: after the marker lands it
polls the search for its id — never for its key, which an index can still map to a
deleted issue when a project's key was reused — bounded, pausing through the injected
``sleep``, and
raises ``SourceUnreachable`` if the index never catches up — the write happened, the
locator cannot honestly be returned, and the projector's restart finds the item. The
search API's reconciliation of named issues is passed for the ids this instance wrote
(the API's limit is fifty, the most recent kept), which keeps an indexed item's fields
exact; it does not surface an unindexed one, which is why the poll exists.

**Faults.** Exhausted retries and undeclared statuses are ``SourceUnreachable`` from
the transport; a record the translation cannot read is ``MalformedRecord``
(``records``), and so is a successful response that is not JSON or lacks the key the
call reads, with the request as locator.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, cast

import httpx

from leaveimpact.adapters.jira import records
from leaveimpact.adapters.transport import DEFAULT_POLICY, Transport, TransportPolicy
from leaveimpact.core.entities import Component, WorkItem
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import ComponentId, EmployeeId, WorkItemId
from leaveimpact.core.ports.errors import MalformedRecord, SourceUnreachable
from leaveimpact.core.ports.observed import Observed

_PAGE = 100
_RECONCILE_LIMIT = 50  # the search API reconciles at most this many issue ids
# How long a write waits for the search index: a freshly created project's issues took
# over ten seconds to appear at one recording, so the budget is a minute, in half seconds.
INDEX_POLLS = 120
INDEX_PAUSE_S = 0.5
Record = dict[str, Any]


@dataclass(frozen=True, slots=True)
class JiraCredential:
    """An Atlassian account email and API token; the repr never shows either."""

    email: str
    api_token: str

    def __repr__(self) -> str:
        return "JiraCredential(email=…, api_token=…)"

    @property
    def auth(self) -> httpx.Auth:
        return httpx.BasicAuth(self.email, self.api_token)


@dataclass(frozen=True, slots=True)
class JiraFields:
    """The ids of the four custom fields, as ``JiraSite.ensure_fields`` resolved them."""

    ticket_id: str
    owner: str
    opened_on: str
    resolved_on: str


@dataclass(frozen=True, slots=True)
class JiraConfig:
    """The project the adapter reads and writes, and the field ids it does so through."""

    project_key: str
    fields: JiraFields


# The custom fields by name, with the type and searcher a create needs.
_FIELD_SPECS: tuple[tuple[str, str, str], ...] = (
    (records.TICKET_ID_FIELD, "textfield", "textsearcher"),
    (records.OWNER_FIELD, "select", "multiselectsearcher"),
    (records.OPENED_ON_FIELD, "datepicker", "daterange"),
    (records.RESOLVED_ON_FIELD, "datepicker", "daterange"),
)
_KANBAN_TEMPLATE = "com.pyxis.greenhopper.jira:gh-kanban-template"
_CUSTOM_FIELD_TYPES = "com.atlassian.jira.plugin.system.customfieldtypes"


class _Wire:
    """One Jira session: the transport with basic auth, and the JSON envelope rule."""

    def __init__(
        self,
        base_url: str,
        credential: JiraCredential,
        policy: TransportPolicy,
        sleep: Callable[[float], None] | None,
        httpx_transport: httpx.BaseTransport | None,
    ) -> None:
        extra: dict[str, Any] = {}
        if sleep is not None:
            extra["sleep"] = sleep
        self.transport = Transport(
            base_url=base_url.rstrip("/") + "/rest/api/3",
            source=Source.JIRA,
            headers={"Accept": "application/json"},
            auth=credential.auth,
            policy=policy,
            httpx_transport=httpx_transport,
            **extra,
        )

    def get(self, path: str, *, ok: tuple[int, ...] = (200,), **kwargs: Any) -> Any:
        response = self.transport.request("GET", path, replayable=True, ok=ok, **kwargs)
        return self._json(response, f"GET {path}")

    def post(
        self, path: str, *, replayable: bool = False, ok: tuple[int, ...] = (201,), **kwargs: Any
    ) -> Any:
        response = self.transport.request("POST", path, replayable=replayable, ok=ok, **kwargs)
        return self._json(response, f"POST {path}")

    def put(self, path: str, *, replayable: bool = False, **kwargs: Any) -> None:
        self.transport.request("PUT", path, replayable=replayable, ok=(204,), **kwargs)

    def delete(self, path: str, *, ok: tuple[int, ...] = (204,)) -> None:
        self.transport.request("DELETE", path, replayable=False, ok=ok)

    @staticmethod
    def _json(response: httpx.Response, locator: str) -> Any:
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as exc:
            raise MalformedRecord(Source.JIRA, locator, "response is not JSON") from exc


def _dict(value: Any, locator: str, what: str) -> Record:
    if not isinstance(value, dict):
        raise MalformedRecord(Source.JIRA, locator, f"{what} is not an object")
    return cast(Record, value)


def _required(record: Record, key: str, locator: str) -> str:
    """The id under ``key`` as text, or malformed: a locator is never the text 'None'.

    Jira writes some ids as strings and some (screens, tabs) as integers; both are ids.
    """
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, str | int) or value == "":
        raise MalformedRecord(Source.JIRA, locator, f"no {key}")
    return str(value)


def _list(value: Any, locator: str, what: str) -> list[Any]:
    if not isinstance(value, list):
        raise MalformedRecord(Source.JIRA, locator, f"{what} is not a list")
    return cast(list[Any], value)


class JiraSite:
    """Preparation of a Jira site for a world: the project, the fields, the owner options.

    Find-or-create throughout, because a field or a project that exists is not an
    error; called by the composition root before the adapter is built, never by the
    adapter. ``ensure_fields`` returns the ids the adapter's configuration needs.
    """

    def __init__(
        self,
        *,
        base_url: str,
        credential: JiraCredential,
        policy: TransportPolicy = DEFAULT_POLICY,
        sleep: Callable[[float], None] | None = None,
        httpx_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._wire = _Wire(base_url, credential, policy, sleep, httpx_transport)

    def close(self) -> None:
        self._wire.transport.close()

    def ensure_project(self, key: str, name: str) -> None:
        """The world's own project on the kanban template; never assumes an empty site."""
        existing = self._wire.get(f"/project/{key}", ok=(200, 404))
        if isinstance(existing, dict) and cast(Record, existing).get("key") == key:
            return
        me = _dict(self._wire.get("/myself"), "GET /myself", "account")
        lead = _required(me, "accountId", "GET /myself")
        self._wire.post(
            "/project",
            json={
                "key": key,
                "name": name,
                "projectTypeKey": "software",
                "projectTemplateKey": _KANBAN_TEMPLATE,
                "leadAccountId": lead,
                "assigneeType": "UNASSIGNED",
            },
        )

    def ensure_fields(self, project_key: str) -> JiraFields:
        """The four custom fields, created where missing and on every screen of the project."""
        listed = _list(self._wire.get("/field"), "GET /field", "fields")
        by_name: dict[str, str] = {}
        for entry in listed:
            field = _dict(entry, "GET /field", "field")
            if field.get("custom"):
                by_name[str(field.get("name"))] = _required(field, "id", "GET /field")
        ids: dict[str, str] = {}
        for name, field_type, searcher in _FIELD_SPECS:
            if name in by_name:
                ids[name] = by_name[name]
                continue
            made = _dict(
                self._wire.post(
                    "/field",
                    json={
                        "name": name,
                        "description": "A world fact of the synthetic organization.",
                        "type": f"{_CUSTOM_FIELD_TYPES}:{field_type}",
                        "searcherKey": f"{_CUSTOM_FIELD_TYPES}:{searcher}",
                    },
                ),
                "POST /field",
                "field",
            )
            ids[name] = _required(made, "id", "POST /field")
        self._place_on_screens(project_key, tuple(ids.values()))
        return JiraFields(
            ticket_id=ids[records.TICKET_ID_FIELD],
            owner=ids[records.OWNER_FIELD],
            opened_on=ids[records.OPENED_ON_FIELD],
            resolved_on=ids[records.RESOLVED_ON_FIELD],
        )

    def ensure_owner_options(
        self, fields: JiraFields, project_key: str, people: Iterable[tuple[EmployeeId, str]]
    ) -> None:
        """An option per person on the owner select, in the project's own field context.

        The context is created where missing, scoped to the project alone, so another
        world's ``emp_001`` never shares a list with this one's; options are appended
        where missing and never removed.
        """
        context_id = _find_owner_context(self._wire, fields.owner, project_key)
        if context_id is None:
            project = _dict(self._wire.get(f"/project/{project_key}"), "GET /project", "project")
            made = _dict(
                self._wire.post(
                    f"/field/{fields.owner}/context",
                    json={
                        "name": _owner_context_name(project_key),
                        "description": "The synthetic owners of one world, per project.",
                        "projectIds": [_required(project, "id", "GET /project")],
                        "issueTypeIds": [],
                    },
                ),
                "POST context",
                "context",
            )
            context_id = _required(made, "id", "POST context")
        existing = {
            _required(option, "value", "GET option")
            for option in _owner_options(self._wire, fields.owner, context_id)
        }
        missing = [
            records.owner_option(employee_id, name)
            for employee_id, name in people
            if records.owner_option(employee_id, name) not in existing
        ]
        if missing:
            self._wire.post(
                f"/field/{fields.owner}/context/{context_id}/option",
                ok=(200, 201),
                json={"options": [{"value": value, "disabled": False} for value in missing]},
            )

    def _place_on_screens(self, project_key: str, field_ids: tuple[str, ...]) -> None:
        # A field can be set on create only from a screen the project's issue type uses;
        # the template names every screen it made after the project key.
        page = _dict(
            self._wire.get("/screens", params={"queryString": project_key}), "GET /screens", "page"
        )
        screens = [
            screen
            for screen in (
                _dict(value, "GET /screens", "screen")
                for value in _list(page.get("values"), "GET /screens", "values")
            )
            if str(screen.get("name", "")).startswith(f"{project_key}:")
        ]
        if not screens:
            raise MalformedRecord(
                Source.JIRA, "GET /screens", f"no screen named '{project_key}: …'"
            )
        for screen in screens:
            screen_id = _required(screen, "id", "GET /screens")
            tabs = _list(self._wire.get(f"/screens/{screen_id}/tabs"), "GET tabs", "tabs")
            tab_id = _required(_dict(tabs[0], "GET tabs", "tab"), "id", "GET tabs")
            on_tab = {
                str(cast(Record, field).get("id"))
                for field in _list(
                    self._wire.get(f"/screens/{screen_id}/tabs/{tab_id}/fields"),
                    "GET fields",
                    "fields",
                )
                if isinstance(field, dict)
            }
            for field_id in field_ids:
                if field_id not in on_tab:
                    self._wire.post(
                        f"/screens/{screen_id}/tabs/{tab_id}/fields",
                        ok=(200, 201),
                        json={"fieldId": field_id},
                    )


def _owner_context_name(project_key: str) -> str:
    return f"{project_key} owners"


def _find_owner_context(wire: _Wire, owner_field: str, project_key: str) -> str | None:
    """The id of the project's owner context, or ``None`` when preparation has not made it."""
    path = f"/field/{owner_field}/context"
    start = 0
    while True:
        listed = wire.get(path, params={"startAt": start, "maxResults": _PAGE})
        page = _dict(listed, f"GET {path}", "page")
        contexts = [
            _dict(value, f"GET {path}", "context")
            for value in _list(page.get("values"), f"GET {path}", "values")
        ]
        for context in contexts:
            if context.get("name") == _owner_context_name(project_key):
                return _required(context, "id", f"GET {path}")
        if page.get("isLast", True) or not contexts:
            return None
        start += len(contexts)


def _owner_options(wire: _Wire, owner_field: str, context_id: str) -> list[Record]:
    path = f"/field/{owner_field}/context/{context_id}/option"
    options: list[Record] = []
    start = 0
    while True:
        page = _dict(
            wire.get(path, params={"startAt": start, "maxResults": _PAGE}), f"GET {path}", "page"
        )
        values = [
            _dict(value, f"GET {path}", "option")
            for value in _list(page.get("values"), f"GET {path}", "values")
        ]
        options.extend(values)
        if page.get("isLast", True) or not values:
            return options
        start += len(values)


class JiraAdapter:
    """Work reader and writer over one Jira project, through configured field ids."""

    def __init__(
        self,
        *,
        base_url: str,
        credential: JiraCredential,
        config: JiraConfig,
        policy: TransportPolicy = DEFAULT_POLICY,
        sleep: Callable[[float], None] | None = None,
        httpx_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._wire = _Wire(base_url, credential, policy, sleep, httpx_transport)
        self._sleep = sleep or time.sleep
        self._owner_options_cache: dict[str, str] | None = None
        self._written: list[int] = []

    @property
    def config(self) -> JiraConfig:
        return self._config

    def close(self) -> None:
        self._wire.transport.close()

    # --- the read side --------------------------------------------------------------

    def work_item(self, id: WorkItemId) -> Observed[WorkItem] | None:
        matches = [item for item in self.work_items() if item.value.id == id]
        if not matches:
            return None
        if len(matches) > 1:
            raise MalformedRecord(
                Source.JIRA, f"issue/{id}", f"{id} is held by more than one issue"
            )
        return matches[0]

    def work_items(self) -> tuple[Observed[WorkItem], ...]:
        fields = self._config.fields
        component_by_name = {
            component.value.name: component.value.id for component in self.components()
        }
        issues = self._search(
            f'project = "{self._config.project_key}" AND cf[{_number(fields.ticket_id)}] '
            "is not EMPTY",
            [
                "summary",
                "status",
                "duedate",
                "components",
                "comment",
                fields.ticket_id,
                fields.owner,
                fields.opened_on,
                fields.resolved_on,
            ],
        )
        return tuple(
            Observed(
                records.work_item_from_record(
                    issue,
                    ticket_id_field=fields.ticket_id,
                    owner_field=fields.owner,
                    opened_on_field=fields.opened_on,
                    resolved_on_field=fields.resolved_on,
                    component_by_name=component_by_name,
                    comments=self._all_comments(issue),
                ),
                Source.JIRA,
            )
            for issue in issues
        )

    def component(self, id: ComponentId) -> Observed[Component] | None:
        matches = [component for component in self.components() if component.value.id == id]
        if not matches:
            return None
        if len(matches) > 1:
            raise MalformedRecord(
                Source.JIRA, f"component/{id}", f"{id} is held by more than one component"
            )
        return matches[0]

    def components(self) -> tuple[Observed[Component], ...]:
        path = f"/project/{self._config.project_key}/components"
        listed = _list(self._wire.get(path), f"GET {path}", "components")
        return tuple(
            Observed(
                records.component_from_record(_dict(record, f"GET {path}", "component")),
                Source.JIRA,
            )
            for record in listed
        )

    # --- the write side -------------------------------------------------------------

    def add_component(self, component: Component) -> str:
        made = _dict(
            self._wire.post(
                "/component",
                json={
                    "name": component.name,
                    "project": self._config.project_key,
                    "description": records.component_description(component),
                },
            ),
            "POST /component",
            "component",
        )
        return _required(made, "id", "POST /component")

    def add_work_item(self, work_item: WorkItem) -> str:
        """Create, comment, transition, then set the id: the marker that makes it readable."""
        fields = self._config.fields
        component_name = self._component_name(work_item.component_id)
        owner_value = self._owner_option(work_item.owner_id)
        made = _dict(
            self._wire.post(
                "/issue",
                json={
                    "fields": records.issue_fields(
                        work_item,
                        project_key=self._config.project_key,
                        component_name=component_name,
                        owner_option_value=owner_value,
                        owner_field=fields.owner,
                        opened_on_field=fields.opened_on,
                        resolved_on_field=fields.resolved_on,
                    )
                },
            ),
            "POST /issue",
            "issue",
        )
        key = _required(made, "key", "POST /issue")
        self._remember(made.get("id"))
        for comment in work_item.comments:
            self._wire.post(
                f"/issue/{key}/comment", json={"body": records.comment_body(comment.text)}
            )
        if work_item.status is not records.INITIAL_STATUS:
            self._transition(key, records.STATUS_NAME_BY_STATUS[work_item.status])
        self._mark(key, work_item.id)
        self._await_indexed(key, work_item.id)
        return key

    # --- the wire ---------------------------------------------------------------------

    def _mark(self, key: str, id: WorkItemId) -> None:
        """Set the ticket id on the issue; when every attempt loses its response, ask the issue.

        Replayable on purpose — setting the id to the same value twice is one world — so a
        lost response retries the write. When the whole budget is lost, the key is still
        known here and the issue itself (a database read, not the index) says whether the
        id landed: if it did, the write succeeded and the caller gets its key; otherwise
        the fault stands. Only a source down through both budgets is left ambiguous.
        """
        ticket = self._config.fields.ticket_id
        try:
            self._wire.put(f"/issue/{key}", replayable=True, json={"fields": {ticket: id}})
        except SourceUnreachable as fault:
            issue = _dict(
                self._wire.get(f"/issue/{key}", params={"fields": ticket}),
                f"GET /issue/{key}",
                "issue",
            )
            landed = _dict(issue.get("fields"), f"GET /issue/{key}", "fields").get(ticket) == id
            if not landed:
                raise fault

    def _await_indexed(self, key: str, id: WorkItemId) -> None:
        """Return once the search index answers the item's id with its key; raise if never."""
        ticket = self._config.fields.ticket_id
        jql = f'project = "{self._config.project_key}" AND cf[{_number(ticket)}] ~ "{id}"'
        for _ in range(INDEX_POLLS):
            found = self._search(jql, [ticket])
            if any(issue.get("key") == key for issue in found):
                return
            self._sleep(INDEX_PAUSE_S)
        raise SourceUnreachable(
            Source.JIRA, f"issue {key} not in the search index after {INDEX_POLLS} polls"
        )

    def _remember(self, issue_id: Any) -> None:
        if isinstance(issue_id, str) and issue_id.isdigit():
            self._written = [*self._written, int(issue_id)][-_RECONCILE_LIMIT:]

    def _search(self, jql: str, fields: list[str]) -> list[Record]:
        issues: list[Record] = []
        token: str | None = None
        while True:
            body: Record = {"jql": jql, "fields": fields, "maxResults": _PAGE}
            if self._written:
                body["reconcileIssues"] = list(self._written)
            if token:
                body["nextPageToken"] = token
            page = _dict(
                self._wire.post("/search/jql", replayable=True, ok=(200,), json=body),
                "POST /search/jql",
                "page",
            )
            issues.extend(
                _dict(issue, "POST /search/jql", "issue")
                for issue in _list(page.get("issues"), "POST /search/jql", "issues")
            )
            token = page.get("nextPageToken")
            if page.get("isLast", True) or not token:
                return issues

    def _all_comments(self, issue: Record) -> list[Record]:
        """The issue's comments to completion: the search embeds a page, the rest is fetched."""
        key = str(issue.get("key", "?"))
        fields = _dict(issue.get("fields"), f"issue/{key}", "fields")
        embedded = _dict(
            fields.get("comment") or {"comments": [], "total": 0}, f"issue/{key}", "comment"
        )
        comments: list[Record] = [
            _dict(comment, f"issue/{key}", "comment")
            for comment in _list(embedded.get("comments", []), f"issue/{key}", "comments")
        ]
        total = int(embedded.get("total", len(comments)))
        if len(comments) >= total:
            return comments
        path = f"/issue/{key}/comment"
        comments = []
        start = 0
        while True:
            page = _dict(
                self._wire.get(path, params={"startAt": start, "maxResults": _PAGE}),
                f"GET {path}",
                "page",
            )
            batch = [
                _dict(comment, f"GET {path}", "comment")
                for comment in _list(page.get("comments"), f"GET {path}", "comments")
            ]
            comments.extend(batch)
            if not batch or len(comments) >= int(page.get("total", len(comments))):
                return comments
            start += len(batch)

    def _transition(self, key: str, target_status: str) -> None:
        path = f"/issue/{key}/transitions"
        page = _dict(self._wire.get(path), f"GET {path}", "page")
        candidates = [
            _dict(transition, f"GET {path}", "transition")
            for transition in _list(page.get("transitions"), f"GET {path}", "transitions")
        ]
        matching = [
            transition
            for transition in candidates
            if _dict(transition.get("to"), f"GET {path}", "to").get("name") == target_status
        ]
        if len(matching) != 1:
            names = sorted(str(_dict(t.get("to"), path, "to").get("name")) for t in candidates)
            raise MalformedRecord(
                Source.JIRA,
                f"issue/{key}",
                f"no single transition to {target_status!r}; the workflow offers {names}",
            )
        transition_id = _required(matching[0], "id", f"GET {path}")
        self._wire.post(path, ok=(204,), json={"transition": {"id": transition_id}})

    def _component_name(self, component_id: ComponentId) -> str:
        found = self.component(component_id)
        if found is None:
            raise LookupError(
                f"component {component_id} is not in Jira project {self._config.project_key}; "
                "add components first"
            )
        return found.value.name

    def _owner_option(self, employee_id: EmployeeId) -> str:
        if self._owner_options_cache is None:
            owner = self._config.fields.owner
            context_id = _find_owner_context(self._wire, owner, self._config.project_key)
            if context_id is None:
                raise LookupError(
                    f"project {self._config.project_key} has no owner context in Jira; "
                    "ensure the world's people first"
                )
            options = _owner_options(self._wire, owner, context_id)
            values = [str(option.get("value")) for option in options]
            cache: dict[str, str] = {}
            for value in values:
                head, separator, _ = value.partition(records.OWNER_SEPARATOR)
                if not separator:
                    continue
                if head in cache:
                    raise MalformedRecord(
                        Source.JIRA,
                        f"field/{owner}/option",
                        f"{head} is held by more than one owner option",
                    )
                cache[head] = value
            self._owner_options_cache = cache
        try:
            return self._owner_options_cache[employee_id]
        except KeyError:
            raise LookupError(
                f"employee {employee_id} has no owner option in Jira; "
                "ensure the world's people first"
            ) from None


def _number(field_id: str) -> str:
    """The numeric part of ``customfield_10078``, the way JQL's ``cf[]`` names a field."""
    return field_id.removeprefix("customfield_")
