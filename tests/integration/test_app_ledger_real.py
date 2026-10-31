"""The ledger page over the real stores: a settled attempt, an open one and a refusal written
through the real log store, then the page read through the route, its figures held equal
to what the store's own reads say, the identity holding, and the memo filled once across two
views. The page's rules are tested over hand-built ledgers in the unit suite; this holds the
wiring from the configured ledger through the store's two new reads to the rendered page."""

from __future__ import annotations

import html

import pytest
from fastapi.testclient import TestClient

from leaveimpact.agent import ledger
from leaveimpact.agent.log_events import LoggedEvent
from leaveimpact.agent.log_store import AdmissionReceipt, AdmissionRefusal, LogStore
from leaveimpact.agent.log_transition import AttemptState
from leaveimpact.app.amounts import dollars
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.ledger_page import LedgerComposition, LiabilityMemo, ledger_page
from leaveimpact.app.main import Services, create_app
from leaveimpact.app.store import AppStore
from leaveimpact.results.committed import committed_results
from tests.integration.log_store_support import Rig, rig
from tests.integration.test_app_start import LEDGER, LIVE, app_store, prepared
from tests.integration.test_log_store import admission_of, request_for, step
from tests.unit import log_histories as histories
from tests.unit.live_routes_fixture import RESERVATION, live_services
from tests.unit.publishable_fixture import SERVED, history_in_world

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

CODE = "b" * 40
RULES = histories.RULES


def client(rig: Rig, store: AppStore, configuration: DemoConfiguration) -> TestClient:
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
    return TestClient(create_app(services))


def replay(
    log: LogStore, events: tuple[LoggedEvent, ...], *, upto: int | None = None
) -> AttemptState:
    """The history admitted against the start rig's ledger and appended through ``upto``."""
    admitted, admitter = admission_of(events)
    receipt = log.admit(request_for(admitted, admitter, ledger_id=LEDGER))
    assert isinstance(receipt, AdmissionReceipt), receipt
    state = log.load(admitted.inputs.run_id, admitted.inputs.attempt, rules=RULES)
    for logged in events[1 : upto if upto is not None else len(events)]:
        state = step(log, logged, state).state
    return state


def histories_written(log: LogStore) -> tuple[int, int]:
    """A settled attempt, an open one and a refused admission on the test ledger; the charge
    the settled one was charged and the open one's reservation."""
    settled = history_in_world("a cut call", SERVED, run_id="run-settled")
    final = replay(log, settled)
    opened = history_in_world("a handled fact-submission tool", SERVED, run_id="run-open")
    replay(log, opened, upto=1)
    admitted, admitter = admission_of(history_in_world("a cut call", SERVED, run_id="run-refused"))
    refusal = log.admit(request_for(admitted, admitter, ledger_id=LEDGER))
    assert isinstance(refusal, AdmissionRefusal), refusal
    charged = final.account.pico_usd
    reservation = admitted.inputs.reservation_pico_usd
    assert reservation is not None
    return charged, reservation


def test_the_page_through_the_route_states_the_stores_figures_and_fills_the_memo_once(
    rig: Rig,
) -> None:
    # A threshold holding exactly two reservations, so the third admission is refused.
    log, store = prepared(rig, threshold=2 * RESERVATION)
    charged, reservation = histories_written(log)
    view = log.ledger_view(LEDGER)
    kinds = [entry.kind for entry in view.entries]
    assert kinds == [
        ledger.EntryKind.THRESHOLD_SET,
        ledger.EntryKind.ADMITTED,
        ledger.EntryKind.SETTLED,
        ledger.EntryKind.ADMITTED,
        ledger.EntryKind.REFUSED,
    ]
    log.close()
    with client(rig, store, LIVE) as web:
        first = web.get("/ledger")
        second = web.get("/ledger")
    assert first.status_code == 200, first.text
    text = html.unescape(first.text)
    assert f"{dollars(2 * RESERVATION)}, set " in text and ", 4 entries since" in text
    assert f"<dt>Committed total</dt><dd>{dollars(view.head.total_pico_usd)}</dd>" in text
    assert f"{dollars(reservation)} over 1 open run" in text
    assert f"{dollars(charged)} over 1 settled run: {dollars(charged)} known consumption" in text
    assert "<dt>Refusals</dt><dd>1</dd>" in text and "run-settled" not in text
    assert "(the latest admission)" in text and "this ledger's settled runs" in text
    assert second.text == first.text
    # The same derivation through the module over the real session: the identity by the
    # store's numbers, and the memo loading nothing the second time.
    session = rig.store()
    try:
        memo = LiabilityMemo()
        composition = LedgerComposition(LIVE, RULES, RESERVATION)
        page = ledger_page(session, composition, memo)
        assert page is not None
        assert page.committed_total_pico_usd == view.head.total_pico_usd == reservation + charged
        assert (page.open_reservations_pico_usd, page.known_pico_usd, page.retained_pico_usd) == (
            reservation,
            charged,
            0,
        )
        assert page.forecast.mean_pico_usd == charged and page.forecast.runs == 1
        again = ledger_page(session, composition, memo)
        assert again == page
    finally:
        session.close()


def test_a_ledger_with_no_head_renders_the_pages_own_state_over_the_real_store(rig: Rig) -> None:
    store = app_store(rig)
    store.ensure_schema()
    with client(rig, store, LIVE) as web:
        page = web.get("/ledger")
    assert page.status_code == 200
    assert f"The ledger <strong>{LEDGER}</strong> has no entries yet" in page.text
