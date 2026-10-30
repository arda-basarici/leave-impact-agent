"""The read model: the one admission every read of the demo surface passes, and the public
view data it returns.

Publishability is one predicate on every read (the demo milestone's ruling): the surface
serves the one world version its configuration names, an allowlist of one, when the cache
serves it, and an attempt only when the app-owned table of publishable attempts holds it.
The predicate has two functions here because the two kinds of read cost differently. The
listing reads the table's projection alone, one indexed query for the rows of the served
version, and loads no log, so thirty titles never fold thirty histories. A content read,
anything that shows or streams what an attempt did, goes through ``admitted``, which finds
the row, requires its world version to be the served one, then loads the attempt from the
log and compares the admission's world version and scenario with the row before returning
anything. The row's world version is a projection written by the operator; the admission
is what the attempt is, and a row that disagrees with it (an operator's mistake, or a
forged row carrying the allowlisted version for an embargoed attempt) serves nothing. The
export re-check alone would have left the narration, which reads events and builds no
export, over a false row (the step's external read); so the comparison is made here, once,
for every content read.

Every refusal is ``None``: an unknown name, a row the predicate refuses and a row the log
contradicts are indistinguishable from outside, so a forced row reveals neither the
attempt's existence nor its world. The contradiction is a defect of the deployment, not a
visitor's error, and is logged here with the public id and the reason, never shown. The
cache's half of the predicate (the served version marked ready) is the route's question,
answered 503 after admission is resolved, since an unavailable cache is an operational
state and not a secret.

``instants_of`` is the one thing a page reads beyond an attempt's export: the log's accept
instant per position, since an export holds positions and not instants and the report
labels each record with when the log took it (the report step's second fork).

``rules_under`` is the surface's reading of the registration: folding a model run needs
the registered attribution table and re-dispatch policy, so the composition root loads the
registration the image ships and this function refuses one whose digest is not the
configured ``registration_digest``, which makes the configuration's digest a live check of
what the service loads rather than a label.

``open_view`` is the replay page of an attempt that has not closed (the live pages step,
group 3's design pass, fork 3): its phase, the wait explained with the measured figures,
and while a review is outstanding the viewer the page renders for (the decision module's
classification of the live row and the browser's key), the deadline and the review as
sentences (``report.review_view``). The page is not the authority: the decision route
keeps its own capability and deadline checks, and this view decides only what a page shows.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from leaveimpact.agent.log_ending import status_of
from leaveimpact.agent.log_events import LoggedEvent
from leaveimpact.agent.log_transition import AttemptState, Rules, trace_operations
from leaveimpact.agent.registered import effective_rules
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.decide import Review, Viewer, deadline_of
from leaveimpact.app.public import PublicAttempt, PublicId, PublicReplay, PublishableRow
from leaveimpact.app.report import ReviewView, review_view
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.registration_json import decode_registration_bytes

_log = logging.getLogger(__name__)

Report = Callable[[str], None]
"""Where a contradiction between a row and the log is recorded: the process's log by
default, a test's list when it asserts the line."""


class PublishableReads(Protocol):
    """The table's two reads, as the store provides them."""

    def rows_for(self, world_version: WorldVersion) -> tuple[PublishableRow, ...]: ...

    def row_of(self, public_id: PublicId) -> PublishableRow | None: ...


class LogReads(Protocol):
    """The log's one read a content resolution needs."""

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState: ...


class LogSession(LogReads, Protocol):
    """A log opened for one request or one command, closed by its opener: the log store
    keeps its connection, so a session is never shared across requests. Beside the whole
    fold it reads the events past a position, the narration stream's tick after its first
    (the live pages step), as the log store provides it."""

    def events_after(self, run_id: str, attempt: int, *, after: int) -> tuple[LoggedEvent, ...]: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class Admitted:
    """A content read's admission: the row and the attempt's state the log folds to, the
    two agreeing on world version and scenario."""

    row: PublishableRow
    state: AttemptState


def rules_under(configuration: DemoConfiguration, registration: bytes) -> Rules:
    """The rules the surface folds every attempt under, from the registration bytes the
    image ships; ``ValueError`` when their digest is not the configured one."""
    digest = hashlib.sha256(registration).hexdigest()
    if digest != configuration.registration_digest:
        raise ValueError(
            f"the registration file's digest {digest[:12]}… is not the configured "
            f"{configuration.registration_digest[:12]}…: the service would fold runs under "
            "rules the demo configuration does not name"
        )
    return effective_rules(decode_registration_bytes(registration))


def listing(reads: PublishableReads, configuration: DemoConfiguration) -> tuple[PublicAttempt, ...]:
    """The published attempts of the served world, oldest first: the projection, no log."""
    return tuple(
        PublicAttempt(row.public_id, row.scenario_id, row.title, row.published_at)
        for row in reads.rows_for(configuration.served_world_version)
    )


def admitted(
    public_id: PublicId,
    reads: PublishableReads,
    log: LogReads,
    configuration: DemoConfiguration,
    rules: Rules,
    *,
    report: Report = _log.warning,
) -> Admitted | None:
    """The attempt ``public_id`` names, admitted for content, or ``None``: no row, a row
    of another world, a row the log has no attempt for, or a row the admission contradicts.
    The last two are reported through ``report`` as defects; the answer stays ``None``."""
    row = reads.row_of(public_id)
    if row is None or row.world_version != configuration.served_world_version:
        return None
    try:
        state = log.load(row.run_id, row.attempt, rules=rules)
    except ValueError as error:
        report(f"publishable row {public_id!r} names an attempt the log cannot load: {error}")
        return None
    inputs = state.inputs
    if inputs is None:
        report(f"publishable row {public_id!r} names an attempt with no admission")
        return None
    context = inputs.context
    if (context.world_version, context.scenario_id) != (row.world_version, row.scenario_id):
        report(
            f"publishable row {public_id!r} says world {row.world_version} scenario "
            f"{row.scenario_id}; the admission says world {context.world_version} scenario "
            f"{context.scenario_id}; the row serves nothing"
        )
        return None
    return Admitted(row, state)


def instants_of(state: AttemptState) -> dict[int, datetime]:
    """The log's accept instant of every event of ``state``, by position."""
    return {event.position: event.timestamp for event in state.events}


def replay_view(admitted: Admitted) -> PublicReplay:
    """The replay page's header over an admitted attempt: its ending when closed."""
    ending = status_of(admitted.state).ending
    row = admitted.row
    return PublicReplay(
        row.public_id,
        row.scenario_id,
        row.title,
        row.published_at,
        None if ending is None else ending.status,
    )


# --- The open page --------------------------------------------------------------------------

MEASURED_RUNS = 30
MEASURED_MEDIAN_SECONDS = 40
MEASURED_LONGEST_SECONDS = 48
"""What the pages quote for a run's duration: the thirty replays' admission-to-request
durations as the tick-cost probe measured them on the instance (FINDINGS ``tick-cost``:
median 40.07 s, max 48.30 s), rounded to the second. The tick-cost test holds these to the
committed capture through the probe's own reducer, so the sentence cannot outlive the
measurement (the live pages step, fork 10)."""


def _minutes(seconds: int) -> str:
    return f"{seconds // 60} minutes" if seconds % 60 == 0 else f"{seconds} seconds"


def wait_explained(configuration: DemoConfiguration) -> str:
    """What a visitor is in for, with the measured figures and the configured bounds and
    nothing else numeric: the index's form state and the open page before the request say
    it (fork 10 as amended: the bound is per running segment, the approval's resumption a
    new segment with its own bound)."""
    return (
        "A live run investigates one scenario of the served world and asks the browser that "
        f"started it to approve or decline its plan. Over the {MEASURED_RUNS} recorded runs "
        f"the investigation took about {MEASURED_MEDIAN_SECONDS} seconds at the median and "
        f"{MEASURED_LONGEST_SECONDS} at most. The decision waits "
        f"{_minutes(configuration.approval_wait_seconds)}; without one the run closes. Each "
        f"running segment is bounded at {_minutes(configuration.attempt_wall_seconds)}, and "
        "the approval's resumption runs in a new segment with its own bound. The replays are "
        "open meanwhile."
    )


class OpenPhase(StrEnum):
    """Where an open attempt stands, as its replay page says it."""

    INVESTIGATING = "investigating"
    """Claimed or not, before any approval request."""
    AWAITING = "awaiting"
    """The review is requested and no decision is in the log."""
    APPROVED = "approved"
    """Approved, carrying out its plan until it closes."""


@dataclass(frozen=True, slots=True)
class OpenView:
    """An open attempt's replay page: the phase, the wait explained, and in the awaiting
    phase the viewer the page renders for, the deadline in UTC and the review rendered as
    sentences over the run's reads; in the approved phase the approval's instant."""

    phase: OpenPhase
    wait: str
    viewer: Viewer | None = None
    deadline: datetime | None = None
    review: ReviewView | None = None
    approved_at: datetime | None = None


def open_view(
    state: AttemptState,
    review: Review | None,
    viewer: Viewer | None,
    configuration: DemoConfiguration,
) -> OpenView:
    """The open page over an admitted open ``state``: ``review`` is the decision module's
    reading of it (``None`` outside the awaiting phase) and ``viewer`` the classification
    of the browser, given exactly when a review is."""
    wait = wait_explained(configuration)
    if review is not None:
        assert viewer is not None, "the awaiting page renders for a classified viewer"
        return OpenView(
            OpenPhase.AWAITING,
            wait,
            viewer=viewer,
            deadline=deadline_of(state, configuration),
            review=review_view(review, trace_operations(state)),
        )
    approved = state.approved
    if approved is not None:
        return OpenView(OpenPhase.APPROVED, wait, approved_at=approved.timestamp)
    return OpenView(OpenPhase.INVESTIGATING, wait)
