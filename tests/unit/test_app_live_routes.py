"""The two live routes over the in-memory stores: the index's start form under the flag on
with the minted key and the scenario ids, and its absence under the flag off; a start
answering the redirect to the replay page with the key as the attempt-scoped cookie, both
rows written, and a repeat the same redirect with the cookie again; each refusal by its
kind with its status, the busy and the per-address refusals one sentence, the world not
served the unavailable page, a form that is not the index's 400 before any rule; the open
replay page showing the review with its digest and the decision form once the approval is
requested; a decision through the route with the cookie landing on the log and the row,
without the cookie or with another key refused as the capability, late or on the log's
refusal 409, an attempt nobody started the not-found page, a form without a decision or a
digest 400."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import datetime, timedelta
from http.cookies import SimpleCookie

import pytest
from fastapi.testclient import TestClient

from leaveimpact.agent.log_events import Admitted, Approved, Declined
from leaveimpact.agent.log_store import LogStoreUnavailable
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.live import Decision, key_digest_of, public_id_for, run_id_for
from leaveimpact.app.main import (
    COOKIE,
    FORM_BYTES_BOUND,
    FORM_FIELDS_BOUND,
    LiveLog,
    Services,
    create_app,
)
from leaveimpact.app.public import PublishableRow
from leaveimpact.app.window import MemoryWindow
from leaveimpact.core.ids import ScenarioId
from tests.unit import log_histories as histories
from tests.unit import test_app_decide as deciding
from tests.unit import test_results_codec as codec
from tests.unit.app_store_memory import MemoryAppStore
from tests.unit.live_routes_fixture import Minter, live_services
from tests.unit.log_store_memory import LEDGER, MemoryLog
from tests.unit.publishable_fixture import CONFIGURATION, SCENARIO, SERVED, history_in_world
from tests.unit.test_app_start import UNLIMITED, closed, key
from tests.unit.test_app_surface import Sessions, Store

CODE = "b" * 40
LIVE = replace(CONFIGURATION, ledger_id=LEDGER, live_runs=True)
OFF = replace(CONFIGURATION, ledger_id=LEDGER)
BUSY_SENTENCE = "A run is in progress; follow it from the replays, and start one when it ends."


class Rig:
    """The whole application over the in-memory stores with the live path composed."""

    def __init__(
        self,
        *,
        configuration: DemoConfiguration = LIVE,
        log: MemoryLog | None = None,
        rows: MemoryAppStore | None = None,
        window: MemoryWindow | None = None,
    ) -> None:
        self.log = MemoryLog() if log is None else log
        self.rows = MemoryAppStore() if rows is None else rows
        self.sessions = Sessions(self.log)
        self.store = Store()
        self.minter = Minter()
        self.services = Services(
            CODE,
            configuration,
            self.store.ready_versions,
            self.store.app_schema,
            self.rows,
            self.sessions,
            histories.RULES,
            codec.results,
            lambda: (),
            **live_services(self.log, self.rows, window=window, mint=self.minter),
        )

    def client(self, cookies: dict[str, str] | None = None) -> TestClient:
        """The test client, holding ``cookies`` as a browser would."""
        return TestClient(create_app(self.services), cookies=cookies or {})


def form(number: int, scenario: str = SCENARIO) -> dict[str, str]:
    return {"key": key(number), "scenario_id": scenario}


def cookie_of(set_cookie: str) -> SimpleCookie:
    jar = SimpleCookie()
    jar.load(set_cookie)
    return jar


# --- the index --------------------------------------------------------------------------------


def test_the_index_carries_the_start_form_with_a_minted_key_under_the_flag_on() -> None:
    rig = Rig()
    with rig.client() as web:
        page = web.get("/").text
    assert 'action="/start"' in page and f'value="{rig.minter.minted[0]}"' in page
    assert f'<option value="{SCENARIO}">' in page and "Live runs are off" not in page


def test_the_index_carries_no_form_under_the_flag_off() -> None:
    rig = Rig(configuration=OFF)
    with rig.client() as web:
        page = web.get("/").text
    assert 'action="/start"' not in page and "Live runs are off" in page
    assert rig.minter.minted == []


# --- the start -------------------------------------------------------------------------------


def test_a_start_redirects_to_the_replay_page_with_the_key_as_the_attempts_cookie() -> None:
    rig = Rig()
    public_id = public_id_for(key_digest_of(key(1)))
    with rig.client() as web:
        answer = web.post("/start", data=form(1), follow_redirects=False)
        assert answer.status_code == 303
        assert answer.headers["location"] == f"/replays/{public_id}"
        jar = cookie_of(answer.headers["set-cookie"])
        assert jar[COOKIE].value == key(1)
        assert jar[COOKIE]["path"] == f"/replays/{public_id}"
        assert jar[COOKIE]["httponly"] and jar[COOKIE]["secure"]
        assert jar[COOKIE]["samesite"].lower() == "strict" and jar[COOKIE]["max-age"]
        assert rig.rows.live_row_of(public_id) is not None
        assert rig.rows.row_of(public_id) is not None
        replay = web.get(f"/replays/{public_id}")
        assert replay.status_code == 200 and "in progress" in replay.text
        again = web.post("/start", data=form(1, "scenario_004"), follow_redirects=False)
        assert again.status_code == 303 and again.headers["location"] == answer.headers["location"]
        assert cookie_of(again.headers["set-cookie"])[COOKIE].value == key(1)
    assert len(rig.log.logs) == 1 and rig.sessions.closed == rig.sessions.opened


@pytest.mark.parametrize(
    ("data", "status", "sentence"),
    [
        ({"key": "not-a-key", "scenario_id": SCENARIO}, 400, "its key is not one"),
        ({"key": key(1)}, 400, "names no scenario"),
        (form(1, "scenario_099"), 400, "no scenario by that name"),
    ],
)
def test_a_form_that_is_not_the_indexs_is_refused_before_any_rule(
    data: dict[str, str], status: int, sentence: str
) -> None:
    rig = Rig()
    with rig.client() as web:
        answer = web.post("/start", data=data)
    assert answer.status_code == status and sentence in answer.text
    assert rig.log.logs == {} and rig.rows.live == []


def test_the_flag_off_the_busy_run_and_the_spent_address_refuse_by_kind() -> None:
    off = Rig(configuration=OFF)
    with off.client() as web:
        answer = web.post("/start", data=form(1))
    assert answer.status_code == 403 and "Live runs are off" in answer.text

    rig = Rig(window=MemoryWindow(limit=UNLIMITED))
    open_run = public_id_for(key_digest_of(key(1)))
    with rig.client() as web:
        assert web.post("/start", data=form(1), follow_redirects=False).status_code == 303
        busy = web.post("/start", data=form(2))
    assert busy.status_code == 409 and BUSY_SENTENCE in busy.text
    assert f'<a href="/replays/{open_run}">Follow the run in progress</a>' in busy.text
    assert f'href="/replays/{open_run}/timeline"' in busy.text

    windowed = Rig(window=MemoryWindow(limit=1))
    with windowed.client() as web:
        assert web.post("/start", data=form(1), follow_redirects=False).status_code == 303
        spent = web.post("/start", data=form(2))
    assert spent.status_code == 409 and BUSY_SENTENCE in spent.text
    assert "Follow the run in progress" not in spent.text, (
        "the address's refusal is made before the read that names the open run"
    )


def test_a_body_past_the_bound_or_with_too_many_fields_is_refused_before_any_rule() -> None:
    """The group's external read: an unbounded read let one post make the process hold the
    whole body. A declared length past the bound, a chunked body without a length past it,
    and a body within it carrying more fields than the parser's bound are refused on both
    routes before any rule runs: no log session opened, nothing admitted, no row."""
    rig = Rig()
    urlencoded = {"content-type": "application/x-www-form-urlencoded"}
    oversized = b"x=&" * FORM_BYTES_BOUND

    def chunks() -> Iterator[bytes]:
        yield oversized[: FORM_BYTES_BOUND // 2]
        yield oversized[FORM_BYTES_BOUND // 2 :]

    crowded = {f"f{number}": "" for number in range(FORM_FIELDS_BOUND + 1)}
    decision = f"/replays/{public_id_for(key_digest_of(key(1)))}/decision"
    with rig.client() as web:
        sized = web.post("/start", content=oversized, headers=urlencoded)
        chunked = web.post("/start", content=chunks(), headers=urlencoded)
        fields = web.post("/start", data=crowded)
        decided_sized = web.post(decision, content=oversized, headers=urlencoded)
        decided_fields = web.post(decision, data=crowded)
    assert sized.status_code == chunked.status_code == decided_sized.status_code == 413
    assert "larger than any this page posts" in sized.text
    assert fields.status_code == decided_fields.status_code == 400
    assert "more fields than any this page posts" in fields.text
    assert rig.log.logs == {} and rig.rows.live == [] and rig.sessions.opened == 0


def test_the_world_not_served_and_a_store_not_answering_are_the_unavailable_page() -> None:
    rig = Rig()
    rig.store.versions = frozenset()
    with rig.client() as web:
        assert web.post("/start", data=form(1)).status_code == 503
    rig.store.versions = frozenset({SERVED})
    rig.store.reachable = False
    with rig.client() as web:
        assert web.post("/start", data=form(1)).status_code == 503
    assert rig.log.logs == {}


# --- the decision --------------------------------------------------------------------------------


def awaiting_rig(*, clock: datetime | None = None) -> tuple[Rig, str]:
    """The fixture attempt awaiting its decision, restated under the served world and the
    public run id, its live row and its publishable row as the start writes them; the
    clock a second before the deadline unless given."""
    events = history_in_world("an approval wait across a restart", SERVED, run_id=deciding.RUN)
    events = events[:9]
    at = deciding.deadline(events) - timedelta(seconds=1) if clock is None else clock
    log, rows, _ = deciding.stores(events, clock=at)
    admitted = events[0].event
    assert isinstance(admitted, Admitted)
    rows.rows.append(
        PublishableRow(
            deciding.PUBLIC_ID,
            deciding.RUN,
            1,
            SERVED,
            admitted.inputs.context.scenario_id,
            None,
            events[0].timestamp,
            "demo-start",
        )
    )
    rig = Rig(log=log, rows=rows)
    return rig, f"/replays/{deciding.PUBLIC_ID}"


def test_the_open_replay_page_shows_the_review_and_the_decision_form_to_the_holder() -> None:
    """Fork 5 of the live pages step: the form renders to the browser holding the key; any
    other viewer reads that the run awaits the browser that started it, with the deadline;
    an attempt no visitor started reads that it awaits its operator. Every viewer reads the
    review's sentences and its digest."""
    rig, path = awaiting_rig()
    deadline = deciding.deadline(deciding.awaiting()).isoformat()
    with rig.client({COOKIE: deciding.KEY}) as web:
        holder = web.get(path)
    with rig.client() as web:
        other = web.get(path)
    with rig.client({COOKIE: str(key(9))}) as web:
        wrong = web.get(path)
    rig.rows.live.clear()
    with rig.client({COOKIE: deciding.KEY}) as web:
        no_visitor = web.get(path)
    assert holder.status_code == 200
    assert f'action="{path}/decision"' in holder.text
    assert f'value="{deciding.DIGEST}"' in holder.text
    assert 'value="approve"' in holder.text and 'value="decline"' in holder.text
    assert f"The wait ends at {deadline}" in holder.text
    for page in (other, wrong):
        assert page.status_code == 200 and 'value="approve"' not in page.text
        assert f"awaits a decision from the browser that started it, until {deadline}" in page.text
    assert no_visitor.status_code == 200 and 'value="approve"' not in no_visitor.text
    assert f"awaits its operator's decision, until {deadline}" in no_visitor.text
    for page in (holder, other, wrong, no_visitor):
        assert "&#34;claims&#34;" in page.text, "the payload's JSON, escaped as text"
        assert f'<span class="cited">{deciding.DIGEST}</span>' in page.text
        assert "The run reported no impact." in page.text, "the fixture's review holds no claim"
        assert "Composed by rules under the policy stated-fact-composer" in page.text
        assert "This run is investigating" not in page.text, "the awaiting page, not the first"


def test_a_decision_with_the_cookie_lands_on_the_log_and_the_row_and_redirects() -> None:
    rig, path = awaiting_rig()
    with rig.client({COOKIE: deciding.KEY}) as web:
        answer = web.post(
            f"{path}/decision",
            data={"decision": "approve", "payload_digest": deciding.DIGEST},
            follow_redirects=False,
        )
        assert answer.status_code == 303 and answer.headers["location"] == path
        state = rig.log.load(deciding.RUN, 1, rules=histories.RULES)
        assert state.approved is not None and isinstance(state.approved.event, Approved)
        row = rig.rows.live_row_of(deciding.PUBLIC_ID)
        assert row is not None and row.decision is Decision.APPROVED
        after = web.get(path)
        assert 'value="approve"' not in after.text, "no form once the approval is given"
        approved_at = rig.log.load(deciding.RUN, 1, rules=histories.RULES).approved
        assert approved_at is not None
        assert f"The plan was approved at {approved_at.timestamp.isoformat()}" in after.text
        declined = web.post(
            f"{path}/decision", data={"decision": "decline", "payload_digest": deciding.DIGEST}
        )
    assert declined.status_code == 409 and "refused the decision" in declined.text


def test_a_decline_closes_the_attempt_and_the_page_renders_its_ending() -> None:
    rig, path = awaiting_rig()
    with rig.client({COOKIE: deciding.KEY}) as web:
        answer = web.post(
            f"{path}/decision",
            data={"decision": "decline", "payload_digest": deciding.DIGEST},
            follow_redirects=False,
        )
    assert answer.status_code == 303
    state = rig.log.load(deciding.RUN, 1, rules=histories.RULES)
    assert state.closed is not None and isinstance(state.closed.event, Declined)
    with rig.client() as web:
        page = web.get(path)
    assert page.status_code == 200 and "<h2>The plan was declined.</h2>" in page.text
    assert "The plan was declined by a person, which closed the run." in page.text
    assert "Abandoned by" not in page.text and "Failed by" not in page.text


def test_without_the_cookie_or_with_another_key_the_decision_is_the_capabilitys_refusal() -> None:
    rig, path = awaiting_rig()
    data = {"decision": "approve", "payload_digest": deciding.DIGEST}
    cases: tuple[dict[str, str], ...] = ({}, {COOKIE: str(key(9))}, {COOKIE: "nope"})
    for cookies in cases:
        with rig.client(cookies) as web:
            answer = web.post(f"{path}/decision", data=data)
        assert answer.status_code == 403 and "does not hold the key" in answer.text, cookies
    assert rig.log.load(deciding.RUN, 1, rules=histories.RULES).approved is None


def test_a_late_decision_and_a_form_without_a_decision_or_a_digest_refuse_by_kind() -> None:
    events = deciding.awaiting()
    rig, path = awaiting_rig(clock=deciding.deadline(events))
    with rig.client({COOKIE: deciding.KEY}) as web:
        late = web.post(
            f"{path}/decision", data={"decision": "approve", "payload_digest": deciding.DIGEST}
        )
        assert late.status_code == 409 and "wait for a decision has ended" in late.text
        no_decision = web.post(f"{path}/decision", data={"payload_digest": deciding.DIGEST})
        assert no_decision.status_code == 400 and "names no decision" in no_decision.text
        no_digest = web.post(f"{path}/decision", data={"decision": "approve"})
        assert no_digest.status_code == 400 and "no review digest" in no_digest.text
    with rig.client() as web:
        nobody = web.post(
            "/replays/nobody-here/decision",
            data={"decision": "approve", "payload_digest": deciding.DIGEST},
        )
        assert nobody.status_code == 404
        assert nobody.content == web.get("/replays/nobody-here").content


def test_a_scenario_id_the_form_names_is_the_planners_scenario() -> None:
    """The scenario reaches the start as the id typed, the planner restates it in the
    frozen inputs, and the replay page names it."""
    rig = Rig()
    with rig.client() as web:
        answer = web.post("/start", data=form(1, "scenario_004"), follow_redirects=False)
        page = web.get(answer.headers["location"])
    assert ScenarioId("scenario_004") in page.text


# --- the index's live state ----------------------------------------------------------------------


def test_the_index_reads_the_live_state_form_busy_spent_and_the_address() -> None:
    """Fork 4 of the live pages step: one admissions read decides the index's state; the key
    is minted for the form alone, and the busy state links the open run by its derived id."""
    rig = Rig(window=MemoryWindow(limit=UNLIMITED))
    open_run = public_id_for(key_digest_of(key(1)))
    with rig.client() as web:
        fresh = web.get("/").text
        assert web.post("/start", data=form(1), follow_redirects=False).status_code == 303
        busy = web.get("/").text
    assert 'action="/start"' in fresh and "5 of today's 5 live runs remain" in fresh
    assert "about 40 seconds at the median and 48 at most" in fresh
    assert "The decision waits 15 minutes" in fresh and "bounded at 10 minutes" in fresh
    assert 'action="/start"' not in busy and "A live run is in progress" in busy
    assert f'<a href="/replays/{open_run}">Follow it</a>' in busy
    assert f'href="/replays/{open_run}/timeline"' in busy
    assert len(rig.minter.minted) == 1, "a key is minted only for a form the page renders"
    assert rig.sessions.opened == rig.sessions.closed, "the index's session is closed"

    capped = Rig(window=MemoryWindow(limit=UNLIMITED))
    with capped.client() as web:
        for number in range(1, 6):
            assert web.post("/start", data=form(number), follow_redirects=False).status_code == 303
            closed(capped.log, run_id_for(key_digest_of(key(number))))
        spent = web.get("/").text
    assert 'action="/start"' not in spent
    assert "Today's budget of live runs is spent: 5 of 5 started" in spent

    windowed = Rig(window=MemoryWindow(limit=1))
    with windowed.client() as web:
        assert web.post("/start", data=form(1), follow_redirects=False).status_code == 303
        closed(windowed.log, run_id_for(key_digest_of(key(1))))
        address = web.get("/").text
    assert 'action="/start"' not in address
    assert "This address has started its live runs for today" in address


def test_the_index_under_the_flag_on_is_unavailable_when_the_log_does_not_answer() -> None:
    rig = Rig()

    def refusing() -> LiveLog:
        raise LogStoreUnavailable("the log store did not answer")

    with TestClient(create_app(replace(rig.services, live_logs=refusing))) as web:
        answer = web.get("/")
    assert answer.status_code == 503 and rig.minter.minted == []


def test_the_open_page_before_the_request_says_investigating_with_the_wait() -> None:
    events = history_in_world("an approval wait across a restart", SERVED, run_id=deciding.RUN)
    log, rows, _ = deciding.stores(events[:7], clock=events[6].timestamp)
    admitted = events[0].event
    assert isinstance(admitted, Admitted)
    rows.rows.append(
        PublishableRow(
            deciding.PUBLIC_ID,
            deciding.RUN,
            1,
            SERVED,
            admitted.inputs.context.scenario_id,
            None,
            events[0].timestamp,
            "demo-start",
        )
    )
    rig = Rig(log=log, rows=rows)
    with rig.client() as web:
        page = web.get(f"/replays/{deciding.PUBLIC_ID}")
    assert page.status_code == 200
    assert "This run is investigating; its report renders when it closes." in page.text
    assert "about 40 seconds at the median and 48 at most" in page.text
    assert "A decision is asked" not in page.text and 'value="approve"' not in page.text
