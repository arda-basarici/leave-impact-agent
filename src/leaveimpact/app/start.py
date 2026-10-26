"""The public start: a visitor's request to run one scenario of the served world, admitted
to the log under the demo's rules or refused by name, and the rows the pages read written
beside the admission.

**Where the rules serialize** (the live-path commands step, fork 1 as amended). The start
holds the app store's advisory lock for the demo's ledger across the whole command, and
every check it makes reads the log, never the live rows: the recorded request by its
identity, then the admissions by the demo's admitter against the demo's ledger since the
UTC day's start with their open state. The log's admission commits on the log's own
connection while the lock is held, so an admission that got no live row (a crash between
the two commits, history 7 of the step's forks) is counted by the next start from the
moment it committed and no extra admission is possible; the live rows are a cache of
page-facing facts and nothing the rules read.

**The order of the checks.** The recorded request first: a repeat of a request, a lost
response resent or a start retried after a deploy that changed what the inputs would be,
is answered as the log recorded it before the flag, the cap or the single-open condition
can refuse it as new, and before any inputs are rebuilt (fork 2 as amended, history 17);
a recorded admission with no live row gets its rows now. Then the flag: live runs off
admits no new attempt and nothing else. Then the served world and the scenario, read off
the composition the deploy fixed. Then the day's count against the cap, by the admissions'
instants and never the tuple's length (the read lists older open ones too); then the
single-open condition, by the closed flag; then the log's admission, whose refusal (the
ledger's) is the recorded one and leaves nothing on the app side; then the publishable row
and the live row in the section's transaction.

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
from typing import Protocol

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
    run_id_for,
)
from leaveimpact.app.public import PublicationDraft
from leaveimpact.core.ids import ScenarioId

DEMO_START = Producer("demo-start")
"""The admitter of every public attempt: the one identity at position 1 that distinguishes
a visitor's admission from an operator's on the same ledger."""

FIRST_ATTEMPT = 1
"""A public run has one attempt: a repeat answers as recorded, and no path retries a run."""


class StartLog(Protocol):
    """The log's commands and reads a start uses, as the log store provides them."""

    def now(self) -> datetime: ...

    def recorded_admission(self, request_id: str) -> RecordedAdmission | None: ...

    def admitted_by(
        self, admitter: Producer, ledger_id: str, *, since: datetime
    ) -> tuple[AdmittedAttempt, ...]: ...

    def admit(self, request: AdmissionRequest) -> AdmissionResult: ...

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState: ...


class LiveWriter(Protocol):
    """The live rows inside one start's critical section."""

    def live_row_of_attempt(self, run_id: str, attempt: int) -> LiveRow | None: ...

    def write(self, publishable: PublicationDraft, live: LiveDraft) -> LiveRow: ...


class StartSections(Protocol):
    """The app store's serialization point: the section every public start against a
    ledger runs inside, one at a time."""

    def start_section(self, ledger_id: str) -> AbstractContextManager[LiveWriter]: ...


Planner = Callable[[ScenarioId, str, int], FrozenInputs]
"""The frozen inputs of a run of the scenario under the run id and attempt given; called
only for a scenario the composition lists."""


@dataclass(frozen=True, slots=True)
class StartComposition:
    """What the composition root fixes for every start: the configuration, the rules the
    log is folded under, the served world's scenario ids, the planner over them, and
    whether the cache serves the configured world."""

    configuration: DemoConfiguration
    rules: Rules
    scenarios: frozenset[ScenarioId]
    plan: Planner
    world_served: Callable[[], bool]


@dataclass(frozen=True, slots=True)
class StartRequest:
    """What a visitor's form carries: the key the index minted into it and the scenario."""

    key: StartKey
    scenario_id: ScenarioId


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
    """The start was refused: the kind, a sentence, and whether the refusal is the log's
    recorded answer to this request (a repeat of a refused one) rather than a rule of this
    command applied now."""

    kind: StartRefusalKind
    detail: str
    recorded: bool = False


StartOutcome = Started | StartRefused


def start(
    request: StartRequest, log: StartLog, sections: StartSections, composition: StartComposition
) -> StartOutcome:
    """One public start under the demo's rules, in the order the module docstring states;
    ``Started`` with the live row, or ``StartRefused`` by name. Raises what the stores raise
    (unavailable, invariant broken, a conflict under the request identity), none of them
    a visitor's outcome."""
    configuration = composition.configuration
    digest = key_digest_of(request.key)
    with sections.start_section(configuration.ledger_id) as writer:
        recorded = log.recorded_admission(digest)
        if recorded is not None:
            return _as_recorded(recorded, writer, log, composition, digest)
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
        admitted = log.admitted_by(DEMO_START, configuration.ledger_id, since=since)
        refusal = _rule_refusal(admitted, configuration, since=since)
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


def _rule_refusal(
    admitted: tuple[AdmittedAttempt, ...], configuration: DemoConfiguration, *, since: datetime
) -> StartRefused | None:
    """The cap, then the single-open condition, over the log's listing: today's count is
    the admissions at or after ``since`` (the listing holds older open ones beside them),
    openness is each entry's closed flag."""
    today = sum(1 for each in admitted if each.admitted_at >= since)
    if today >= configuration.daily_admissions:
        return StartRefused(
            StartRefusalKind.BUDGET_SPENT,
            f"today's budget is spent: {today} of {configuration.daily_admissions} starts",
        )
    if any(not each.closed for each in admitted):
        return StartRefused(StartRefusalKind.BUSY, "an attempt is running; the replays are open")
    return None


def _as_recorded(
    recorded: RecordedAdmission,
    writer: LiveWriter,
    log: StartLog,
    composition: StartComposition,
    digest: str,
) -> StartOutcome:
    """A repeat answered as the log recorded it: the refusal with its reason, or the
    attempt with its live row, written now if the first start lost it."""
    if not recorded.admitted:
        assert recorded.reason is not None, "a recorded refusal carries its reason"
        return StartRefused(StartRefusalKind.RESERVATION_REFUSED, recorded.reason, recorded=True)
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
            LiveDraft(public_id, recorded.run_id, recorded.attempt, digest, recorded.recorded_at),
        )
    return Started(row, repeated=True)


__all__ = [
    "DEMO_START",
    "FIRST_ATTEMPT",
    "LiveWriter",
    "Planner",
    "StartComposition",
    "StartLog",
    "StartOutcome",
    "StartRefusalKind",
    "StartRefused",
    "StartRequest",
    "StartSections",
    "Started",
    "day_start_of",
    "start",
]
