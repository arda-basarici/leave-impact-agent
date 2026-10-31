"""The ledger page over hand-built ledgers: every entry kind accounted for and the identity
held; a settled attempt whose derived figures do not total its entry refused, and a page
whose figures do not add refused at construction; the memo filling from the settlements read
once, folding only a kept settlement, caching nothing on a failure; the reservation and the
forecast from their sources; and the route over the in-memory rig, rendering the page under
the flag on and off, the no-ledger state, the unavailable page on a store that does not
answer and on a log that disagrees with the ledger, the session closed on every path."""

from __future__ import annotations

import html
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta

import pytest

from leaveimpact.agent import ledger
from leaveimpact.agent.inventory import SnapshotEntry
from leaveimpact.agent.ledger import LedgerEntry, LedgerHead
from leaveimpact.agent.log_events import Admitted, LoggedSettlement
from leaveimpact.agent.log_store import AttemptSettlement, LogStoreUnavailable, TimedLedgerView
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.ledger_page import (
    REPLAY_SET_MEAN_CHARGE_PICO_USD,
    REPLAY_SET_RUNS,
    ForecastSource,
    LedgerComposition,
    LedgerInconsistent,
    LiabilityMemo,
    ReservationSource,
    ThresholdInForce,
    ledger_figures,
    ledger_page,
)
from leaveimpact.app.start import DayTally
from leaveimpact.core.run_account import AccountFigures
from leaveimpact.core.run_ending import KeptReason, ReservationState
from tests.unit import log_histories as histories
from tests.unit.log_store_memory import LEDGER, MemoryLog
from tests.unit.test_app_live_routes import LIVE, OFF, Rig

RULES = histories.RULES
NOON = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
THRESHOLD = 8_000_000_000_000
RESERVATION = 2_167_352_000_000
TALLY = DayTally(today=1, cap=5, open_runs=())
AUTHORITY = "operator:t"


def timed(*entries: LedgerEntry) -> TimedLedgerView:
    """A view over ``entries`` with instants a minute apart, folded to its head."""
    return TimedLedgerView(
        ledger.fold(entries),
        tuple(
            SnapshotEntry(entry, NOON + timedelta(minutes=index))
            for index, entry in enumerate(entries)
        ),
    )


def built() -> tuple[LedgerEntry, ...]:
    """A threshold, two admissions, one settled, one refused, one import: every kind."""
    head = LedgerHead()
    first, head = ledger.threshold_set(
        head, THRESHOLD, authority=AUTHORITY, registration_commit="c"
    )
    second, head = ledger.admitted(head, "run-a", 1, RESERVATION)
    third, head = ledger.settled(
        head, "run-a", 1, reservation_pico_usd=RESERVATION, charged_pico_usd=70_000_000_000
    )
    fourth, head = ledger.admitted(head, "run-b", 1, RESERVATION)
    fifth, head = ledger.refused(head, "run-c", 1, RESERVATION, reason="no room")
    sixth, head = ledger.imported(head, 5_000_000_000, authority=AUTHORITY, registration_commit="c")
    return (first, second, third, fourth, fifth, sixth)


FIGURES = {("run-a", 1): AccountFigures(60_000_000_000, 10_000_000_000, 70_000_000_000)}


def test_every_entry_kind_is_accounted_for_and_the_identity_holds() -> None:
    page = ledger_figures(LEDGER, timed(*built()), TALLY, FIGURES, RESERVATION)
    assert page.threshold == ThresholdInForce(THRESHOLD, NOON, 5)
    assert page.committed_total_pico_usd == RESERVATION + 70_000_000_000 + 5_000_000_000
    assert page.room_pico_usd == THRESHOLD - page.committed_total_pico_usd
    assert (page.open_reservations_pico_usd, page.open_reservations) == (RESERVATION, 1)
    assert (page.charged_pico_usd, page.charged) == (70_000_000_000, 1)
    assert (page.known_pico_usd, page.retained_pico_usd) == (60_000_000_000, 10_000_000_000)
    assert (page.imported_pico_usd, page.imported, page.refusals) == (5_000_000_000, 1, 1)
    assert (page.today, page.cap, page.remaining_today) == (1, 5, 4)
    assert page.reservation_source is ReservationSource.LATEST_ADMISSION
    assert page.forecast.source is ForecastSource.THIS_LEDGER
    assert (page.forecast.mean_pico_usd, page.forecast.runs) == (70_000_000_000, 1)


def test_before_any_admission_the_planner_and_the_replay_set_supply_the_figures() -> None:
    head = LedgerHead()
    only, _ = ledger.threshold_set(head, THRESHOLD, authority=AUTHORITY, registration_commit="c")
    page = ledger_figures(LEDGER, timed(only), TALLY, {}, RESERVATION)
    assert (page.reservation_pico_usd, page.reservation_source) == (
        RESERVATION,
        ReservationSource.PLANNER,
    )
    assert page.forecast.source is ForecastSource.REPLAY_SET
    assert (page.forecast.mean_pico_usd, page.forecast.runs) == (
        REPLAY_SET_MEAN_CHARGE_PICO_USD,
        REPLAY_SET_RUNS,
    )
    assert page.room_pico_usd == THRESHOLD and page.threshold is not None
    none = ledger_figures(LEDGER, timed(only), TALLY, {}, None)
    assert none.reservation_source is ReservationSource.NONE and none.reservation_pico_usd is None


def test_a_settled_attempt_whose_figures_do_not_total_its_entry_is_refused() -> None:
    wrong = {("run-a", 1): AccountFigures(60_000_000_000, 0, 60_000_000_000)}
    with pytest.raises(LedgerInconsistent, match="totals 60000000000 and the settled entry"):
        ledger_figures(LEDGER, timed(*built()), TALLY, wrong, RESERVATION)
    with pytest.raises(LedgerInconsistent, match="derived for 0 attempts"):
        ledger_figures(LEDGER, timed(*built()), TALLY, {}, RESERVATION)


def test_a_page_whose_figures_do_not_add_is_refused_at_construction() -> None:
    page = ledger_figures(LEDGER, timed(*built()), TALLY, FIGURES, RESERVATION)
    with pytest.raises(LedgerInconsistent, match="committed total"):
        replace(page, imported_pico_usd=1)
    with pytest.raises(LedgerInconsistent, match="charged spend"):
        replace(page, charged_pico_usd=page.charged_pico_usd + 1)


# --- the memo ---------------------------------------------------------------------------------


@dataclass
class CountingLog:
    """A log whose settlements read and loads are counted; ``loads`` is what a fold costs."""

    settlements: tuple[AttemptSettlement, ...]
    state: AttemptState | None = None
    reads: int = 0
    loads: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])

    def settlements_of(self, ledger_id: str) -> tuple[AttemptSettlement, ...]:
        self.reads += 1
        return self.settlements

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        self.loads.append((run_id, attempt))
        assert self.state is not None
        return self.state


def reconciled(run_id: str, charged: int) -> AttemptSettlement:
    return AttemptSettlement(
        run_id, 1, LoggedSettlement(charged, ReservationState.RECONCILED, None, 3)
    )


def test_the_memo_fills_once_from_the_read_and_never_folds_a_reconciled_attempt() -> None:
    log = CountingLog((reconciled("run-a", 70), reconciled("run-b", 30)))
    memo = LiabilityMemo()
    keys = (("run-a", 1), ("run-b", 1))
    first = memo.figures_for(log, LEDGER, keys, RULES)  # type: ignore[arg-type]
    assert first == {
        ("run-a", 1): AccountFigures(70, 0, 70),
        ("run-b", 1): AccountFigures(30, 0, 30),
    }
    second = memo.figures_for(log, LEDGER, keys, RULES)  # type: ignore[arg-type]
    assert second == first and (log.reads, log.loads) == (1, [])
    third = memo.figures_for(log, LEDGER, keys[:1], RULES)  # type: ignore[arg-type]
    assert third == {("run-a", 1): AccountFigures(70, 0, 70)} and log.reads == 1


def test_the_memo_folds_a_kept_settlement_once_and_holds_its_total_to_the_charge() -> None:
    kept = AttemptSettlement(
        "run-k", 1, LoggedSettlement(70, ReservationState.KEPT, KeptReason.USAGE_INCOMPLETE, 3)
    )
    events = histories.HISTORIES["a cut call"]()
    memory = MemoryLog()
    memory.seed(events)
    admitted = events[0].event
    assert isinstance(admitted, Admitted)
    folded = memory.load(admitted.inputs.run_id, 1, rules=RULES)
    log = CountingLog((kept,), state=folded)
    memo = LiabilityMemo()
    with pytest.raises(LedgerInconsistent, match="the account rule totals"):
        memo.figures_for(log, LEDGER, (("run-k", 1),), RULES)  # type: ignore[arg-type]
    assert log.loads == [("run-k", 1)]
    charged = folded.account.pico_usd
    agreeing = CountingLog(
        (
            AttemptSettlement(
                "run-k",
                1,
                LoggedSettlement(charged, ReservationState.KEPT, KeptReason.USAGE_INCOMPLETE, 3),
            ),
        ),
        state=folded,
    )
    figures = memo.figures_for(agreeing, LEDGER, (("run-k", 1),), RULES)  # type: ignore[arg-type]
    assert figures[("run-k", 1)].total_pico_usd == charged
    memo.figures_for(agreeing, LEDGER, (("run-k", 1),), RULES)  # type: ignore[arg-type]
    assert agreeing.loads == [("run-k", 1)], "the kept attempt was folded once"


def test_the_memo_caches_nothing_when_a_fill_fails() -> None:
    log = CountingLog((reconciled("run-a", 70),))
    memo = LiabilityMemo()
    keys = (("run-a", 1), ("run-missing", 1))
    with pytest.raises(LedgerInconsistent, match="run-missing attempt 1 and the log no closed"):
        memo.figures_for(log, LEDGER, keys, RULES)  # type: ignore[arg-type]
    memo.figures_for(log, LEDGER, keys[:1], RULES)  # type: ignore[arg-type]
    assert log.reads == 2, "the first fill cached nothing, so the second read the store again"
    logged_none = CountingLog((AttemptSettlement("run-a", 1, None),))
    with pytest.raises(LedgerInconsistent, match="logged no settlement"):
        LiabilityMemo().figures_for(logged_none, LEDGER, keys[:1], RULES)  # type: ignore[arg-type]


# --- the route --------------------------------------------------------------------------------


@dataclass
class LedgerMemoryLog(MemoryLog):
    """The memory log with the page's two reads over hand data; ``timed`` ``None`` is a
    ledger with no head, and ``failing`` makes the view read raise unavailable."""

    timed: TimedLedgerView | None = None
    settlements: tuple[AttemptSettlement, ...] = ()
    failing: bool = False
    closes: int = 0

    def close(self) -> None:
        self.closes += 1

    def ledger_view_timed(self, ledger_id: str) -> TimedLedgerView | None:
        if self.failing:
            raise LogStoreUnavailable("the log does not answer")
        assert ledger_id == LEDGER
        return self.timed

    def settlements_of(self, ledger_id: str) -> tuple[AttemptSettlement, ...]:
        return self.settlements


def rig_with(log: LedgerMemoryLog, configuration: DemoConfiguration = LIVE) -> Rig:
    return Rig(configuration=configuration, log=log)


def test_the_route_renders_every_figure_and_no_run_id_under_the_flag_on_and_off() -> None:
    log = LedgerMemoryLog(timed=timed(*built()), settlements=(reconciled("run-a", 70_000_000_000),))
    for configuration, flag in ((LIVE, "Live runs are on"), (OFF, "Live runs are off")):
        rig = rig_with(log, configuration)
        with rig.client() as web:
            page = web.get("/ledger")
        assert page.status_code == 200, page.text
        text = html.unescape(page.text)  # the templates escape an apostrophe to an entity
        assert "$8.0000, set 2026-10-31 12:00 UTC, 5 entries since" in text
        assert "$0.0700 over 1 settled run: $0.0700 known consumption plus $0.0000 retained" in text
        assert "$2.1674 over 1 open run" in text and "<dt>Refusals</dt><dd>1</dd>" in text
        assert "$0.0050 over 1 import" in text and "(the latest admission)" in text
        assert "the mean over 1 settled run (this ledger's settled runs)" in text
        assert flag in text and "run-a" not in text and "run-b" not in text
    assert log.closes == 2, "one live session per request, closed before the page"


def test_a_ledger_with_no_head_is_the_pages_own_state() -> None:
    rig = rig_with(LedgerMemoryLog(timed=None))
    with rig.client() as web:
        page = web.get("/ledger")
    assert page.status_code == 200
    assert f"The ledger <strong>{LEDGER}</strong> has no entries yet" in page.text


def test_a_store_that_does_not_answer_and_a_log_that_disagrees_are_the_unavailable_page() -> None:
    failing = rig_with(LedgerMemoryLog(failing=True))
    with failing.client() as web:
        assert web.get("/ledger").status_code == 503
    assert failing.log.closes == 1  # type: ignore[attr-defined]
    log = LedgerMemoryLog(timed=timed(*built()), settlements=(reconciled("run-a", 1),))
    disagreeing = rig_with(log)
    with disagreeing.client() as web:
        page = web.get("/ledger")
    assert page.status_code == 503 and "unavailable" in page.text.lower()
    assert log.closes == 1


def test_the_composition_hands_the_page_the_configured_ledger_and_the_planners_figure() -> None:
    log = LedgerMemoryLog(timed=timed(*built()), settlements=(reconciled("run-a", 70_000_000_000),))
    composition = LedgerComposition(LIVE, RULES, RESERVATION)
    page = ledger_page(log, composition, LiabilityMemo())
    assert page is not None and page.ledger_id == LEDGER and page.today == 0
    assert ledger_page(LedgerMemoryLog(timed=None), composition, LiabilityMemo()) is None
