"""The two live routes over the real stores: a start through the route admitting on the
log under the demo's admitter with both rows in the app's tables and the cookie set to
the attempt's path, a repeat the same redirect; a decision through the route with the
cookie landing on the log and the row, and the decline after it the log's refusal. The
routes' rules are the commands' and are tested there; this holds the wiring from the form
to the real stores and back to the page."""

from __future__ import annotations

from http.cookies import SimpleCookie

import pytest
from fastapi.testclient import TestClient

from leaveimpact.agent.log_events import Admitted, Approved
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.live import Decision, LiveDraft, key_digest_of, public_id_for
from leaveimpact.app.main import COOKIE, Services, create_app
from leaveimpact.app.public import PublicationDraft
from leaveimpact.app.start import DEMO_START
from leaveimpact.app.store import AppStore
from leaveimpact.results.committed import committed_results
from tests.integration.log_store_support import Rig, rig
from tests.integration.test_app_start import LIVE, app_store, prepared
from tests.integration.test_log_store import opened, replay
from tests.unit import log_histories as histories
from tests.unit.live_routes_fixture import live_services
from tests.unit.publishable_fixture import SCENARIO, SERVED, history_in_world
from tests.unit.test_app_decide import DIGEST, KEY, KEY_DIGEST, PUBLIC_ID, RUN
from tests.unit.test_app_start import key

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

CODE = "b" * 40
RULES = histories.RULES


def client(
    rig: Rig,
    store: AppStore,
    configuration: DemoConfiguration,
    cookies: dict[str, str] | None = None,
) -> TestClient:
    services = Services(
        code_version=CODE,
        configuration=configuration,
        ready_versions=lambda: frozenset({configuration.served_world_version}),
        app_schema=store.schema_supported,
        rows=store,
        log_sessions=rig.store,
        rules=RULES,
        results=committed_results,
        walkthroughs=lambda: (),
        **live_services(rig.store, store),
    )
    return TestClient(create_app(services), cookies=cookies or {})


def test_a_start_through_the_route_admits_on_the_log_and_writes_the_rows(rig: Rig) -> None:
    log, store = prepared(rig)
    log.close()
    public_id = public_id_for(key_digest_of(key(1)))
    with client(rig, store, LIVE) as web:
        answer = web.post(
            "/start", data={"key": key(1), "scenario_id": SCENARIO}, follow_redirects=False
        )
        assert answer.status_code == 303, answer.text
        assert answer.headers["location"] == f"/replays/{public_id}"
        jar = SimpleCookie()
        jar.load(answer.headers["set-cookie"])
        assert jar[COOKIE].value == key(1) and jar[COOKIE]["path"] == f"/replays/{public_id}"
        again = web.post(
            "/start", data={"key": key(1), "scenario_id": SCENARIO}, follow_redirects=False
        )
        assert again.status_code == 303 and again.headers["location"] == answer.headers["location"]
        page = web.get(f"/replays/{public_id}")
    assert page.status_code == 200 and "in progress" in page.text
    row = store.live_row_of(public_id)
    assert row is not None and row.holds(key(1)) and row.decision is None
    publishable = store.row_of(public_id)
    assert publishable is not None and publishable.world_version == SERVED
    log = rig.store()
    try:
        events = log.events(row.run_id, row.attempt)
        assert len(events) == 1 and events[0].envelope == DEMO_START
        recorded = log.recorded_admission(key_digest_of(key(1)))
        assert recorded is not None and recorded.admitted
    finally:
        log.close()


def test_a_decision_through_the_route_lands_on_the_log_and_the_row(rig: Rig) -> None:
    """The fixture history replayed through its approval request under the served world
    and the public run id, the attempt's two rows written as the start writes them, then
    the decision through the route."""
    log = opened(rig)
    store = app_store(rig)
    store.ensure_schema()
    events = history_in_world("an approval wait across a restart", SERVED, run_id=RUN)
    state = replay(log, events, upto=9)
    assert state.approval_requested is not None and state.approved is None
    log.close()
    admitted = events[0].event
    assert isinstance(admitted, Admitted)
    with store.start_section() as writer:
        row = writer.write(
            PublicationDraft(
                PUBLIC_ID,
                RUN,
                1,
                SERVED,
                admitted.inputs.context.scenario_id,
                None,
                "demo-start",
            ),
            LiveDraft(PUBLIC_ID, RUN, 1, KEY_DIGEST, events[0].timestamp),
        )
    configuration = LIVE
    path = f"/replays/{PUBLIC_ID}"
    with client(rig, store, configuration) as bare:
        page = bare.get(path)
        assert page.status_code == 200 and f'value="{DIGEST}"' in page.text
        without = bare.post(
            f"{path}/decision", data={"decision": "approve", "payload_digest": DIGEST}
        )
        assert without.status_code == 403
    with client(rig, store, configuration, {COOKIE: KEY}) as web:
        answer = web.post(
            f"{path}/decision",
            data={"decision": "approve", "payload_digest": DIGEST},
            follow_redirects=False,
        )
        assert answer.status_code == 303 and answer.headers["location"] == path
        declined = web.post(
            f"{path}/decision", data={"decision": "decline", "payload_digest": DIGEST}
        )
        assert declined.status_code == 409
    recorded = store.live_row_of(PUBLIC_ID)
    assert recorded is not None and recorded.decision is Decision.APPROVED
    reader = rig.store()
    try:
        after = reader.load(RUN, 1, rules=RULES)
    finally:
        reader.close()
    assert after.approved is not None and isinstance(after.approved.event, Approved)
    assert recorded.decided_at == after.approved.timestamp
    assert row.decision is None, "the row read at the start was undecided"
