"""The ledger page: the demo's money as the configured ledger records it, every entry kind
accounted for, and an identity the page refuses to print unless it adds (the live pages
step, the ledger page's forks).

The page reads the ledger in one log session: the timed view (the head and every entry with
its accept instant) and the day's public admissions, the same read the index and the start
rule make. From the entries it states the threshold in force and when it was set, the
committed total, the open reservations (admitted entries no settled entry closed), the
charged spend over the settled entries, the imported spend, the refusals, the room, and the
reservation a run holds (the latest admitted entry's amount, which every admission under
one registration shares; before any admission, the planner's figure the composition root
hands in). Two figures come from outside the ledger. The retained liability is in no table
by design (the account rule derives it from the decoded events, and a second copy in SQL
would drift), so it is derived here per settled attempt and memoized for the process's
life, a closed log being immutable; the mean charge per settled run is labelled a
conservative charge forecast, since a kept reservation sits inside a charge, and until a
visitor run settles the figure is the replay set's, pinned to the ledger-cost probe's
capture by a unit test. The identity the page states, committed total equals open
reservations plus known consumption plus retained liability plus imported spend, with
"charged" shown as known consumption plus retained liability, is checked in the page's
constructor, and each settled attempt's derived total is checked against its settled
entry's amount before the page is built, so the log's account and the ledger's entry are
compared on every view and a drift is a refusal and not a sum. No entry is listed and no
run id reaches the page.

The memo fills the attempts it lacks from the store's one-statement read of every closed
attempt's logged settlement, so a reconciled attempt (every line priced whole) costs one
decode and never a fold, and only a kept one is folded, once. The ledger-cost probe measured
the fold at 129 ms an attempt on the instance (3.9 s of CPU over the replay set's thirty,
19 s forecast for a month at the daily cap), which is why the reconciled case does not
fold; the settlements read's own cost is the probe's second capture, taken after this page
deployed. A store failure during a fill caches nothing. The memo has no lock: a closed log
is immutable, two viewers computing one attempt at once get the same figure, and a dict
assignment is atomic under the interpreter lock.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from leaveimpact.agent.ledger import EntryKind
from leaveimpact.agent.log_events import Producer
from leaveimpact.agent.log_store import AdmittedAttempt, AttemptSettlement, TimedLedgerView
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.start import DEMO_START, DayTally, day_start_of, day_tally
from leaveimpact.core.run_account import AccountFigures, figures_of
from leaveimpact.core.run_ending import ReservationState

REPLAY_SET_RUNS = 30
REPLAY_SET_TOTAL_PICO_USD = 2_096_667_100_000
REPLAY_SET_MEAN_CHARGE_PICO_USD = 69_888_903_333
"""The replay set's thirty settled charges on the demo ledger as the ledger-cost probe read
them on the instance (FINDINGS ``ledger-cost``: $2.0967 in all, $0.0699 a run): the charge
forecast the page quotes until a visitor run settles. The ledger-cost test holds these to
the committed capture through the probe's own reducer, so the figure cannot outlive the
reading (the pin pattern of the wait sentence)."""

AttemptKey = tuple[str, int]


class LedgerLog(Protocol):
    """The log session's reads the page makes, as the log store provides them."""

    def now(self) -> datetime: ...

    def admitted_by(
        self, admitter: Producer, ledger_id: str, *, since: datetime
    ) -> tuple[AdmittedAttempt, ...]: ...

    def ledger_view_timed(self, ledger_id: str) -> TimedLedgerView | None: ...

    def settlements_of(self, ledger_id: str) -> tuple[AttemptSettlement, ...]: ...

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState: ...


class LedgerInconsistent(Exception):
    """The log and the ledger disagree about a settled attempt, or the page's figures do not
    add: a defect of the deployment the page refuses to print over."""


@dataclass(frozen=True, slots=True)
class LedgerComposition:
    """What the composition root fixes for every view of the page: the configuration, the
    rules a kept attempt is folded under, and the reservation the planner would freeze for
    a run under the registration (``None`` for a system that reserves nothing)."""

    configuration: DemoConfiguration
    rules: Rules
    reservation_pico_usd: int | None


class LiabilityMemo:
    """The per-attempt figures of every settled attempt the process has seen, keyed by run
    and attempt for the process's life. One instance per process, carried by the services;
    a test gives it a counting log and shows the second view loads nothing."""

    def __init__(self) -> None:
        self._figures: dict[AttemptKey, AccountFigures] = {}

    def figures_for(
        self, log: LedgerLog, ledger_id: str, attempts: tuple[AttemptKey, ...], rules: Rules
    ) -> dict[AttemptKey, AccountFigures]:
        """The figures of each settled attempt in ``attempts``, the missing ones filled from
        the store's settlements read: a reconciled settlement is known consumption entire
        with nothing retained, a kept one is folded through ``load`` and split by the account
        rule. ``LedgerInconsistent`` for a settled entry whose attempt the read does not
        report, whose closure logged no settlement, or whose folded total is not the charge
        its closure logged."""
        missing = [key for key in attempts if key not in self._figures]
        if not missing:
            return {key: self._figures[key] for key in attempts}
        settled = {
            (each.run_id, each.attempt): each.settlement for each in log.settlements_of(ledger_id)
        }
        filled: dict[AttemptKey, AccountFigures] = {}
        for run_id, attempt in missing:
            where = f"run {run_id} attempt {attempt}"
            if (run_id, attempt) not in settled:
                raise LedgerInconsistent(
                    f"the ledger holds a settled entry for {where} and the log no closed attempt"
                )
            settlement = settled[(run_id, attempt)]
            if settlement is None:
                raise LedgerInconsistent(f"{where} settled on the ledger and logged no settlement")
            if settlement.state is ReservationState.RECONCILED:
                charged = settlement.charged_pico_usd
                figures = AccountFigures(charged, 0, charged)
            else:
                figures = figures_of(log.load(run_id, attempt, rules=rules).account)
                if figures.total_pico_usd != settlement.charged_pico_usd:
                    raise LedgerInconsistent(
                        f"{where}: the account rule totals {figures.total_pico_usd} and the "
                        f"closure logged {settlement.charged_pico_usd}"
                    )
            filled[(run_id, attempt)] = figures
        # Written only once every missing attempt resolved, so a failure caches nothing.
        self._figures.update(filled)
        return {key: self._figures[key] for key in attempts}


# --- The page ---------------------------------------------------------------------------------


class ReservationSource(StrEnum):
    """Where the page's "reservation a run holds" figure comes from."""

    LATEST_ADMISSION = "the latest admission"
    PLANNER = "the planner, before any run"
    NONE = "none: the configured system reserves nothing"


class ForecastSource(StrEnum):
    """Which settled runs the charge forecast averages."""

    THIS_LEDGER = "this ledger's settled runs"
    REPLAY_SET = "the replay set on the demo ledger, until a run settles here"


@dataclass(frozen=True, slots=True)
class ThresholdInForce:
    """The threshold entry in force: its amount, the instant the store took it, and how many
    entries the ledger has written since."""

    amount_pico_usd: int
    set_at: datetime
    entries_since: int


@dataclass(frozen=True, slots=True)
class ChargeForecast:
    """The mean charge per settled run and the count it averages, labelled by its source."""

    mean_pico_usd: int
    runs: int
    source: ForecastSource


@dataclass(frozen=True, slots=True)
class LedgerPage:
    """Every figure the page states, in pico-dollars and counts, with the identity checked
    at construction: the committed total is the open reservations plus the known consumption
    plus the retained liability plus the imported spend, and the charged spend is the known
    consumption plus the retained liability. ``LedgerInconsistent`` otherwise."""

    ledger_id: str
    revision: int
    threshold: ThresholdInForce | None
    committed_total_pico_usd: int
    room_pico_usd: int
    open_reservations_pico_usd: int
    open_reservations: int
    charged_pico_usd: int
    charged: int
    known_pico_usd: int
    retained_pico_usd: int
    imported_pico_usd: int
    imported: int
    refusals: int
    today: int
    cap: int
    reservation_pico_usd: int | None
    reservation_source: ReservationSource
    forecast: ChargeForecast

    def __post_init__(self) -> None:
        accounted = (
            self.open_reservations_pico_usd
            + self.known_pico_usd
            + self.retained_pico_usd
            + self.imported_pico_usd
        )
        if self.committed_total_pico_usd != accounted:
            raise LedgerInconsistent(
                f"the committed total {self.committed_total_pico_usd} is not the open "
                f"reservations {self.open_reservations_pico_usd} plus the known consumption "
                f"{self.known_pico_usd} plus the retained liability {self.retained_pico_usd} "
                f"plus the imported spend {self.imported_pico_usd}"
            )
        if self.charged_pico_usd != self.known_pico_usd + self.retained_pico_usd:
            raise LedgerInconsistent(
                f"the charged spend {self.charged_pico_usd} is not the known consumption "
                f"{self.known_pico_usd} plus the retained liability {self.retained_pico_usd}"
            )

    @property
    def remaining_today(self) -> int:
        """How many starts the day has left, never below zero."""
        return max(self.cap - self.today, 0)


def ledger_figures(
    ledger_id: str,
    view: TimedLedgerView,
    tally: DayTally,
    figures: Mapping[AttemptKey, AccountFigures],
    planner_reservation_pico_usd: int | None,
) -> LedgerPage:
    """The page of ``ledger_id`` over the timed view, the day's tally and the settled
    attempts' figures, pure; ``figures`` holds exactly the settled entries' attempts.
    ``LedgerInconsistent`` when a settled attempt's figures do not total its entry's amount,
    or the page does not add."""
    entries = [each.entry for each in view.entries]
    settled = {
        (entry.run_id, entry.attempt): entry
        for entry in entries
        if entry.kind is EntryKind.SETTLED
        if entry.run_id is not None and entry.attempt is not None
    }
    if set(figures) != set(settled):
        raise LedgerInconsistent(
            f"figures were derived for {len(figures)} attempts and the ledger settles "
            f"{len(settled)}"
        )
    for key, entry in settled.items():
        if figures[key].total_pico_usd != entry.amount_pico_usd:
            raise LedgerInconsistent(
                f"run {key[0]} attempt {key[1]}: the account rule totals "
                f"{figures[key].total_pico_usd} and the settled entry holds {entry.amount_pico_usd}"
            )
    admitted = [entry for entry in entries if entry.kind is EntryKind.ADMITTED]
    open_reservations = [
        entry for entry in admitted if (entry.run_id, entry.attempt) not in settled
    ]
    imported = [entry for entry in entries if entry.kind is EntryKind.IMPORTED]
    thresholds = [
        (entry, each.recorded_at)
        for each, entry in zip(view.entries, entries, strict=True)
        if entry.kind is EntryKind.THRESHOLD_SET
    ]
    threshold = None
    if thresholds:
        entry, set_at = thresholds[-1]
        threshold = ThresholdInForce(
            entry.amount_pico_usd, set_at, view.head.revision - entry.revision
        )
    known = sum(each.known_pico_usd for each in figures.values())
    retained = sum(each.retained_pico_usd for each in figures.values())
    if admitted:
        reservation: int | None = admitted[-1].amount_pico_usd
        source = ReservationSource.LATEST_ADMISSION
    elif planner_reservation_pico_usd is not None:
        reservation = planner_reservation_pico_usd
        source = ReservationSource.PLANNER
    else:
        reservation = None
        source = ReservationSource.NONE
    if settled:
        charged_total = sum(entry.amount_pico_usd for entry in settled.values())
        forecast = ChargeForecast(
            round(charged_total / len(settled)), len(settled), ForecastSource.THIS_LEDGER
        )
    else:
        forecast = ChargeForecast(
            REPLAY_SET_MEAN_CHARGE_PICO_USD, REPLAY_SET_RUNS, ForecastSource.REPLAY_SET
        )
    return LedgerPage(
        ledger_id=ledger_id,
        revision=view.head.revision,
        threshold=threshold,
        committed_total_pico_usd=view.head.total_pico_usd,
        room_pico_usd=view.head.room_pico_usd,
        open_reservations_pico_usd=sum(entry.amount_pico_usd for entry in open_reservations),
        open_reservations=len(open_reservations),
        charged_pico_usd=known + retained,
        charged=len(settled),
        known_pico_usd=known,
        retained_pico_usd=retained,
        imported_pico_usd=sum(entry.amount_pico_usd for entry in imported),
        imported=len(imported),
        refusals=sum(1 for entry in entries if entry.kind is EntryKind.REFUSED),
        today=tally.today,
        cap=tally.cap,
        reservation_pico_usd=reservation,
        reservation_source=source,
        forecast=forecast,
    )


def ledger_page(
    log: LedgerLog, composition: LedgerComposition, memo: LiabilityMemo
) -> LedgerPage | None:
    """The page from one log session: the timed view of the configured ledger, the day's
    admissions since midnight UTC, the settled attempts' figures through the memo; ``None``
    when the ledger has no head yet, which the route renders as its own state. Raises what
    the log raises, and ``LedgerInconsistent`` as the derivation does."""
    configuration = composition.configuration
    view = log.ledger_view_timed(configuration.ledger_id)
    if view is None:
        return None
    since = day_start_of(log.now())
    admitted = log.admitted_by(DEMO_START, configuration.ledger_id, since=since)
    tally = day_tally(admitted, configuration, since=since)
    settled_attempts = tuple(
        (each.entry.run_id, each.entry.attempt)
        for each in view.entries
        if each.entry.kind is EntryKind.SETTLED
        and each.entry.run_id is not None
        and each.entry.attempt is not None
    )
    figures = memo.figures_for(log, configuration.ledger_id, settled_attempts, composition.rules)
    return ledger_figures(
        configuration.ledger_id, view, tally, figures, composition.reservation_pico_usd
    )


__all__ = [
    "REPLAY_SET_MEAN_CHARGE_PICO_USD",
    "REPLAY_SET_RUNS",
    "REPLAY_SET_TOTAL_PICO_USD",
    "AttemptKey",
    "ChargeForecast",
    "ForecastSource",
    "LedgerComposition",
    "LedgerInconsistent",
    "LedgerLog",
    "LedgerPage",
    "LiabilityMemo",
    "ReservationSource",
    "ThresholdInForce",
    "ledger_figures",
    "ledger_page",
]
