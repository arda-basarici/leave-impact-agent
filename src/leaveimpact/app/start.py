"""The public start: a visitor's request to run one scenario of the served world, admitted
to the log under the demo's rules or refused by name, and the rows the pages read written
beside the admission.

**Where the rules serialize** (the live-path commands step, fork 1 as amended at group 2's
external read). The start runs its checks and the log's admission under the log store's
session-level lock for the demo's ledger, on the connection that commits the admission:
the recorded request by its identity, then the admissions by the demo's admitter against
the demo's ledger since the UTC day's start with their open state, then the admission
itself. The lock lives exactly as long as that connection, so a start whose connection
dies inside the block loses the lock and its open transaction together, and a start whose
admission committed is counted by the next holder from that moment; an admission that got
no live row (a crash between the log's commit and the rows', history 7 of the step's
forks) is counted all the same and no extra admission is possible. The first build held
the lock on the app store's connection, and a start whose app backend died during its
admission released the lock while the admission went on to commit, which admitted a sixth
attempt against a cap of five on the real store. The live rows are a cache of page-facing
facts, written in their own transaction after the admission, and nothing the rules read.

**The order of the checks.** The recorded request first: a repeat of a request, a lost
response resent or a start retried after a deploy that changed what the inputs would be,
is answered as the log recorded it before the flag, the cap or the single-open condition
can refuse it as new, and before any inputs are rebuilt (fork 2 as amended, history 17);
a recorded admission with no live row gets its rows now. Then the flag: live runs off
admits no new attempt and nothing else. Then the served world and the scenario, read off
the composition the deploy fixed. Then the client address's window (``window``, fork 8 as
placed at group 4's design pass): two admissions per address per UTC day, consulted here
and not on the route, so a repeat is answered before it and the window counts admissions
alone; its refusal wears the busy page's wording under its own kind. Then the day's count
against the cap, by the admissions' instants and never the tuple's length (the read lists
older open ones too); then the single-open condition, by the closed flag; then the log's
admission, whose refusal (the ledger's) is the recorded one and leaves nothing on the app
side, and whose receipt is noted on the window; then the publishable row and the live row
in the app store's section.

**One tally, two readers** (the live pages step, group 3's design pass, fork 2). The cap and
the single-open condition are read off ``day_tally``, the admissions listing reduced to
today's count, the cap and the open runs; the index page reads the same tally through
``index_state`` to say, before any click, whether the form is open with how many starts
remain, a run is in progress (named by its derived public id, so the page links it), or
the day's budget is spent. The rule and the page cannot drift, since neither has a predicate
of its own. The busy refusal carries the open run's id for the same reason, so the refusal
page points at the run and not only at the replays. The index's read runs under no lock
and the post keeps every check: the read and the submit can race, and the refusal is the
truth then.

**The names.** The key's digest is the request identity, the run id and the public id are
derived from it, and the admitter is one identity, ``demo-start``, which is what makes an
admission at position 1 a public one (``live.py``). The frozen inputs come from a planner
the composition root hands in as a callable over the scenario's id: the launcher's own
plan over the registration the image ships, the committed price table and the served
world's scenario specifications (``launch.demo``), so a repeat rebuilds byte-identical
inputs and the worker's comparison at the claim passes by construction. This module sees
the scenarios as ids and the plan as a function, since the surface imports neither the
launcher nor the world's codecs (the import law).
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, time
from enum import StrEnum
from typing import ClassVar, Protocol

from leaveimpact.agent.log_events import FrozenInputs, Producer
from leaveimpact.agent.log_store import (
    AdmissionReceipt,
    AdmissionRequest,
    AdmissionResult,
    AdmittedAttempt,
    RecordedAdmission,
)
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.live import (
    LiveDraft,
    LiveRow,
    StartKey,
    key_digest_of,
    public_id_for,
    public_id_of_run,
    run_id_for,
)
from leaveimpact.app.public import PublicationDraft, PublicId
from leaveimpact.app.window import AddressWindow
from leaveimpact.core.ids import ScenarioId

DEMO_START = Producer("demo-start")
"""The admitter of every public attempt: the one identity at position 1 that distinguishes
a visitor's admission from an operator's on the same ledger."""

FIRST_ATTEMPT = 1
"""A public run has one attempt: a repeat answers as recorded, and no path retries a run."""


class StartLog(Protocol):
    """The log's commands and reads a start uses, as the log store provides them."""

    def serialized(self, name: str) -> AbstractContextManager[None]: ...

    def now(self) -> datetime: ...

    def recorded_admission(self, request_id: str) -> RecordedAdmission | None: ...

    def admitted_by(
        self, admitter: Producer, ledger_id: str, *, since: datetime
    ) -> tuple[AdmittedAttempt, ...]: ...

    def admit(self, request: AdmissionRequest) -> AdmissionResult: ...

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState: ...


class LiveWriter(Protocol):
    """The live rows inside one section of the app store."""

    def live_row_of_attempt(self, run_id: str, attempt: int) -> LiveRow | None: ...

    def write(self, publishable: PublicationDraft, live: LiveDraft) -> LiveRow: ...


class StartSections(Protocol):
    """The app store's section: one transaction over the rows of one started attempt."""

    def start_section(self) -> AbstractContextManager[LiveWriter]: ...


Planner = Callable[[ScenarioId, str, int], FrozenInputs]
"""The frozen inputs of a run of the scenario under the run id and attempt given; called
only for a scenario the composition lists."""


@dataclass(frozen=True, slots=True)
class Planning:
    """What the composition root above the shells hands the surface: the served world's
    scenario ids, the planner over them, and the reservation the planner freezes for a run
    (``None`` for a system that reserves nothing), all built by the launcher from the
    registration, the price table and the world store, which the surface never imports.
    The reservation is one figure and not per scenario because the planner computes it
    from the registration's caps, the role and the pricing basis alone; the ledger page
    quotes it before any admission exists."""

    scenarios: frozenset[ScenarioId]
    plan: Planner
    reservation_pico_usd: int | None


@dataclass(frozen=True, slots=True)
class StartComposition:
    """What the composition root fixes for every start: the configuration, the rules the
    log is folded under, the served world's scenario ids, the planner over them, whether
    the cache serves the configured world, and the per-address window."""

    configuration: DemoConfiguration
    rules: Rules
    scenarios: frozenset[ScenarioId]
    plan: Planner
    world_served: Callable[[], bool]
    window: AddressWindow


@dataclass(frozen=True, slots=True)
class StartRequest:
    """What a visitor's form carries, the key the index minted into it and the scenario,
    and the client address the route read for the window."""

    key: StartKey
    scenario_id: ScenarioId
    address: str


class StartRefusalKind(StrEnum):
    """Why a start was refused; the page's wording is the renderer's."""

    LIVE_RUNS_OFF = "live_runs_off"
    """The configuration's flag: no new public admission."""
    WORLD_NOT_SERVED = "world_not_served"
    """The cache does not serve the configured world, so nothing could be shown."""
    UNKNOWN_SCENARIO = "unknown_scenario"
    """The served world has no scenario of that id."""
    BUDGET_SPENT = "budget_spent"
    """The day's admissions reached the cap."""
    BUSY = "busy"
    """A public attempt is open; the replays are there to read meanwhile."""
    ADDRESS_SPENT = "address_spent"
    """The client address had its admissions for the UTC day; rendered with the busy
    wording, so the sentence a visitor reads is one, and named here so the record is."""
    RESERVATION_REFUSED = "reservation_refused"
    """The log refused the admission (the ledger's room or its head); the reason is the
    log's, recorded under the request identity."""


@dataclass(frozen=True, slots=True)
class Started:
    """The attempt the start names: admitted now, or as recorded for a repeat."""

    row: LiveRow
    repeated: bool


@dataclass(frozen=True, slots=True)
class StartRefused:
    """The start was refused: the kind, a sentence, whether the refusal is the log's
    recorded answer to this request (a repeat of a refused one) rather than a rule of this
    command applied now, and for the busy kind the open run's id, so the page can point at
    the run; ``None`` on every other kind."""

    kind: StartRefusalKind
    detail: str
    recorded: bool = False
    open_run: str | None = None


StartOutcome = Started | StartRefused


@dataclass(frozen=True, slots=True)
class DayTally:
    """The day's public admissions as the rule and the index read them: how many were
    admitted at or after the day's start, the cap, and the run ids of the open ones in the
    listing (older ones included: an open attempt is open whatever day admitted it)."""

    today: int
    cap: int
    open_runs: tuple[str, ...]

    @property
    def remaining(self) -> int:
        """How many starts the day has left, never below zero."""
        return max(self.cap - self.today, 0)


def day_tally(
    admitted: tuple[AdmittedAttempt, ...], configuration: DemoConfiguration, *, since: datetime
) -> DayTally:
    """The tally over the admissions-by-admitter listing read since ``since``, the UTC
    day's start: today's count by each admission's instant and never the tuple's length,
    openness by each entry's closed flag."""
    return DayTally(
        today=sum(1 for each in admitted if each.admitted_at >= since),
        cap=configuration.daily_admissions,
        open_runs=tuple(each.run_id for each in admitted if not each.closed),
    )


@dataclass(frozen=True, slots=True)
class FormOpen:
    """The index shows the form: the day's remaining starts against the cap."""

    kind: ClassVar[str] = "form"

    remaining: int
    cap: int


@dataclass(frozen=True, slots=True)
class Busy:
    """A public run is open; the index names it by its derived public id and says what a
    start after it meets: the day's remaining count once it closes (the open run counted
    in today's tally already), and whether the visitor's own address still admits one
    (group 3's external read: the first wording promised a start the cap or the address
    would refuse)."""

    kind: ClassVar[str] = "busy"

    open_run: PublicId
    remaining: int
    address_admits: bool


@dataclass(frozen=True, slots=True)
class Spent:
    """The day's cap is reached; it opens again at midnight UTC."""

    kind: ClassVar[str] = "spent"

    today: int
    cap: int


@dataclass(frozen=True, slots=True)
class AddressSpent:
    """The visitor's own address had its starts for the day; the post would refuse it."""

    kind: ClassVar[str] = "address_spent"


IndexState = FormOpen | Busy | Spent | AddressSpent


def index_state(log: StartLog, composition: StartComposition, address: str) -> IndexState:
    """What the index says under the flag on, from one admissions read in ``log`` and the
    window the composition holds: busy first (a run to follow is the most useful fact),
    then the spent day, then the visitor's own spent address, else the open form with the
    remaining count. Raises what the log raises."""
    configuration = composition.configuration
    since = day_start_of(log.now())
    admitted = log.admitted_by(DEMO_START, configuration.ledger_id, since=since)
    tally = day_tally(admitted, configuration, since=since)
    address_admits = composition.window.admits(address, since=since)
    if tally.open_runs:
        return Busy(public_id_of_run(tally.open_runs[0]), tally.remaining, address_admits)
    if tally.today >= tally.cap:
        return Spent(tally.today, tally.cap)
    if not address_admits:
        return AddressSpent()
    return FormOpen(tally.remaining, tally.cap)


def serialization_name(ledger_id: str) -> str:
    """The name every public start against ``ledger_id`` serializes under.

    >>> serialization_name("ledger-demo")
    'start:ledger-demo'
    """
    return f"start:{ledger_id}"


def start(
    request: StartRequest, log: StartLog, sections: StartSections, composition: StartComposition
) -> StartOutcome:
    """One public start under the demo's rules, in the order the module docstring states;
    ``Started`` with the live row, or ``StartRefused`` by name. Raises what the stores raise
    (unavailable, invariant broken, a conflict under the request identity), none of them
    a visitor's outcome."""
    configuration = composition.configuration
    digest = key_digest_of(request.key)
    with log.serialized(serialization_name(configuration.ledger_id)):
        recorded = log.recorded_admission(digest)
        if recorded is not None:
            return _as_recorded(recorded, sections, log, composition, digest)
        if not configuration.live_runs:
            return StartRefused(StartRefusalKind.LIVE_RUNS_OFF, "live runs are off")
        if not composition.world_served():
            return StartRefused(
                StartRefusalKind.WORLD_NOT_SERVED, "the served world is not available"
            )
        if request.scenario_id not in composition.scenarios:
            return StartRefused(
                StartRefusalKind.UNKNOWN_SCENARIO,
                f"the served world has no scenario {request.scenario_id}",
            )
        since = day_start_of(log.now())
        if not composition.window.admits(request.address, since=since):
            return StartRefused(
                StartRefusalKind.ADDRESS_SPENT, "an attempt is running; the replays are open"
            )
        admitted = log.admitted_by(DEMO_START, configuration.ledger_id, since=since)
        refusal = _rule_refusal(day_tally(admitted, configuration, since=since))
        if refusal is not None:
            return refusal
        run_id = run_id_for(digest)
        inputs = composition.plan(request.scenario_id, run_id, FIRST_ATTEMPT)
        result = log.admit(
            AdmissionRequest(
                digest,
                inputs,
                DEMO_START,
                configuration.ledger_id if inputs.reservation_pico_usd is not None else None,
                composition.rules,
            )
        )
        if not isinstance(result, AdmissionReceipt):
            return StartRefused(StartRefusalKind.RESERVATION_REFUSED, result.reason)
        composition.window.note(request.address, result.recorded_at)
        with sections.start_section() as writer:
            row = writer.write(
                PublicationDraft(
                    public_id_for(digest),
                    run_id,
                    FIRST_ATTEMPT,
                    inputs.context.world_version,
                    inputs.context.scenario_id,
                    None,
                    DEMO_START.identity,
                ),
                LiveDraft(public_id_for(digest), run_id, FIRST_ATTEMPT, digest, result.recorded_at),
            )
        return Started(row, repeated=False)


def day_start_of(instant: datetime) -> datetime:
    """The start of ``instant``'s UTC day, the cap's window.

    >>> from datetime import timedelta, timezone
    >>> plus_three = timezone(timedelta(hours=3))
    >>> day_start_of(datetime(2026, 10, 27, 1, 30, tzinfo=plus_three))
    datetime.datetime(2026, 10, 26, 0, 0, tzinfo=datetime.timezone.utc)
    """
    return datetime.combine(instant.astimezone(UTC).date(), time(), tzinfo=UTC)


def _rule_refusal(tally: DayTally) -> StartRefused | None:
    """The cap, then the single-open condition, over the day's tally; the busy refusal
    carries the first open run."""
    if tally.today >= tally.cap:
        return StartRefused(
            StartRefusalKind.BUDGET_SPENT,
            f"today's budget is spent: {tally.today} of {tally.cap} starts",
        )
    if tally.open_runs:
        return StartRefused(
            StartRefusalKind.BUSY,
            "an attempt is running; the replays are open",
            open_run=tally.open_runs[0],
        )
    return None


def _as_recorded(
    recorded: RecordedAdmission,
    sections: StartSections,
    log: StartLog,
    composition: StartComposition,
    digest: str,
) -> StartOutcome:
    """A repeat answered as the log recorded it: the refusal with its reason, or the
    attempt with its live row, written now if the first start lost it. The write is the
    section's get-or-create: a repeat that found no row and then met the first start's
    rows landing (the first start's log connection died after its admission committed, so
    its session lock was gone while its rows were still in flight) takes those rows as its
    receipt."""
    if not recorded.admitted:
        assert recorded.reason is not None, "a recorded refusal carries its reason"
        return StartRefused(StartRefusalKind.RESERVATION_REFUSED, recorded.reason, recorded=True)
    with sections.start_section() as writer:
        row = writer.live_row_of_attempt(recorded.run_id, recorded.attempt)
        if row is None:
            inputs = log.load(recorded.run_id, recorded.attempt, rules=composition.rules).inputs
            assert inputs is not None, "an admitted attempt's state holds its frozen inputs"
            context = inputs.context
            public_id = public_id_for(digest)
            row = writer.write(
                PublicationDraft(
                    public_id,
                    recorded.run_id,
                    recorded.attempt,
                    context.world_version,
                    context.scenario_id,
                    None,
                    DEMO_START.identity,
                ),
                LiveDraft(
                    public_id, recorded.run_id, recorded.attempt, digest, recorded.recorded_at
                ),
            )
    return Started(row, repeated=True)


__all__ = [
    "DEMO_START",
    "FIRST_ATTEMPT",
    "AddressSpent",
    "Busy",
    "DayTally",
    "FormOpen",
    "IndexState",
    "LiveWriter",
    "Planner",
    "Planning",
    "Spent",
    "StartComposition",
    "StartLog",
    "StartOutcome",
    "StartRefusalKind",
    "StartRefused",
    "StartRequest",
    "StartSections",
    "Started",
    "day_start_of",
    "day_tally",
    "index_state",
    "serialization_name",
    "start",
]
