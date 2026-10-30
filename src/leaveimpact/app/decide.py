"""The public decision: a visitor's approve or decline of the attempt they started, bound
to the review payload they read, admitted while the wait for a decision is open and
refused by name otherwise, the log deciding and the live row recording what it decided.

**Where the decision serializes** (the live-path commands step, fork 4 as amended at
group 3's design pass). The decision runs under the log store's session-level lock with a
per-attempt name, on the connection that commits the decision, and the sweeper's close of
a wait takes the same lock: the deadline check and the log's commit live and die on one
connection, so a decision whose connection dies inside the block loses the lock and its
open transaction together, and the sweeper that takes the lock next reads the log as it
is. The design's first shape locked the live row on the app store's connection and
committed the decision on the log's, the shape of the start's first hole: a decision
reads the clock before the deadline, its app connection dies while its approval is in
flight, the sweeper takes the freed row lock, reads no decision and a passed deadline and
abandons, the approval commits first on the log's attempt row, and an attempt approved
in time is closed as cancelled. The live row is never locked here: its decision columns
are a cache written after the log's commit, by every writer from what the log holds, and
repaired from the log by a retry or the sweeper when a process died between the two.

**The order of the checks.** The live row by its public id (a replay the operator
published has none); the capability, a hash comparison of the key the browser holds with
the digest the row stores, a browser holding none refused the same way and after the row,
so a name nobody started answers alike with and without a key; then, under the lock, the
state loaded: the same decision
already held under the digest (an approval under it, or a close by a decline under it)
answers with its receipt whatever the clock says, and the row is repaired on the way
out; otherwise no request yet is refused by name; otherwise the deadline is the approval
request's recorded instant plus the configured wait, the log's clock compared with it
under the lock, admitted while strictly before it and refused as late at or past it, the
refusal naming the wait and never the clock; then the agent's own approval or decline
command on the log, its refusal passed through with its reason (the attempt closed by
something else, a digest that is not the request's, the other decision already given):
the log's rules are stated once, in the commands, and this module adds the capability,
the deadline and the serialization around them. The deciding identity is one producer,
``demo-visitor``; who clicked is the capability's holder and nothing more is recorded.
"""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from leaveimpact.agent.appender import LogCommands
from leaveimpact.agent.commands import (
    ApprovalDelivery,
    CommandRefused,
    DeclineDelivery,
    decline,
    deliver_approval,
)
from leaveimpact.agent.log_events import (
    ApprovalRequested,
    Approved,
    Declined,
    LoggedEvent,
    Producer,
)
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.live import Decision, LiveRow, StartKey
from leaveimpact.app.public import PublicId
from leaveimpact.core.claims import Claim
from leaveimpact.core.run_ending import Composition
from leaveimpact.core.run_parts_json import review_payload, review_payload_digest
from leaveimpact.core.run_trace import require_digest

DEMO_VISITOR = Producer("demo-visitor")
"""The producer of every public decision: the capability's holder decided, and the log
records no more about them."""


class DecideLog(LogCommands, Protocol):
    """The log's commands and reads a decision uses, as the log store provides them: the
    commands the agent's approval and decline run over, the serialization, the clock and
    the events of one attempt."""

    def serialized(self, name: str) -> AbstractContextManager[None]: ...

    def now(self) -> datetime: ...

    def events(self, run_id: str, attempt: int) -> tuple[LoggedEvent, ...]: ...


class DecisionRows(Protocol):
    """The live rows as the app store reads and records them."""

    def live_row_of(self, public_id: PublicId) -> LiveRow | None: ...

    def record_decision(
        self, public_id: PublicId, decision: Decision, decided_at: datetime
    ) -> LiveRow: ...


@dataclass(frozen=True, slots=True)
class DecideComposition:
    """What the composition root fixes for every decision: the configuration (the wait)
    and the rules the log is folded under."""

    configuration: DemoConfiguration
    rules: Rules


@dataclass(frozen=True, slots=True)
class DecideRequest:
    """What a visitor's click carries: the attempt's public id, the key the browser holds
    (``None`` when it holds none), the decision, and the digest of the review payload the
    page showed."""

    public_id: PublicId
    key: StartKey | None
    decision: Decision
    payload_digest: str

    def __post_init__(self) -> None:
        require_digest(self.payload_digest, "the review payload's digest")


class DecideRefusalKind(StrEnum):
    """Why a decision was refused; the page's wording is the renderer's."""

    NOT_LIVE = "not_live"
    """No visitor started the attempt the public id names, or nothing is published under it."""
    CAPABILITY = "capability"
    """The key given is not the one the attempt was started under, or none was given."""
    NO_REQUEST = "no_request"
    """The attempt has asked for no approval yet."""
    LATE = "late"
    """The wait for a decision has ended."""
    LOG_REFUSED = "log_refused"
    """The log's own refusal: closed by something else, another digest, the other
    decision already given; the detail is the command's reason."""


@dataclass(frozen=True, slots=True)
class Decided:
    """The decision is in the log at ``position`` and on the row: made now, or held
    already under the same digest and answered as the receipt."""

    row: LiveRow
    position: int
    repeated: bool


@dataclass(frozen=True, slots=True)
class DecideRefused:
    """The decision was refused: the kind and a sentence."""

    kind: DecideRefusalKind
    detail: str


DecideOutcome = Decided | DecideRefused


def decision_name(run_id: str, attempt: int) -> str:
    """The name a decision on the attempt and the sweeper's close of its wait serialize
    under.

    >>> decision_name("demo-0abc", 1)
    'decision:demo-0abc:1'
    """
    return f"decision:{run_id}:{attempt}"


def decide(
    request: DecideRequest, log: DecideLog, rows: DecisionRows, composition: DecideComposition
) -> DecideOutcome:
    """One public decision in the order the module docstring states; ``Decided`` with the
    row as recorded, or ``DecideRefused`` by name. Raises what the stores raise
    (unavailable, invariant broken), none of them a visitor's outcome."""
    row = rows.live_row_of(request.public_id)
    if row is None:
        return DecideRefused(DecideRefusalKind.NOT_LIVE, "no visitor started this attempt")
    if request.key is None or not row.holds(request.key):
        return DecideRefused(DecideRefusalKind.CAPABILITY, "the key given did not start it")
    with log.serialized(decision_name(row.run_id, row.attempt)):
        state = log.load(row.run_id, row.attempt, rules=composition.rules)
        held = held_position(state, request.decision, request.payload_digest)
        if held is not None:
            position, repeated = held, True
        else:
            refusal = _wait_refusal(state, log, composition.configuration)
            if refusal is not None:
                return refusal
            outcome = _on_the_log(request, row, log, composition.rules)
            if isinstance(outcome, CommandRefused):
                return DecideRefused(DecideRefusalKind.LOG_REFUSED, outcome.reason)
            position, repeated = outcome, False
        decided_at = _instant_at(log, row, position)
    recorded = rows.record_decision(row.public_id, request.decision, decided_at)
    return Decided(recorded, position, repeated)


@dataclass(frozen=True, slots=True)
class Review:
    """The review an open attempt awaits a decision on, as the replay page shows it: the
    request's position, the frozen claims and composition the digest covers (what the page
    renders as sentences), the payload as indented JSON, and its digest, which the decision
    form carries back."""

    position: int
    claims: tuple[Claim, ...]
    composition: Composition
    payload_json: str
    digest: str


def review_of(state: AttemptState) -> Review | None:
    """The review ``state`` awaits a decision on, or ``None``: before any request, once an
    approval is given, or once the attempt is closed."""
    requested = state.approval_requested
    if requested is None or state.approved is not None or state.closed is not None:
        return None
    event = requested.event
    assert isinstance(event, ApprovalRequested), "the request is its own event"
    payload = review_payload(event.claims, event.composition)
    return Review(
        requested.position,
        event.claims,
        event.composition,
        json.dumps(payload, indent=2, sort_keys=True),
        review_payload_digest(event.claims, event.composition),
    )


class Viewer(StrEnum):
    """Who is reading an open attempt's page, as the live row and the browser's key tell it;
    the page renders the decision form to the holder alone and tells every other viewer
    what is true (the live pages step, group 3's design pass, fork 3). The post keeps its
    own check: this classification decides what a page shows, never what the log admits."""

    HOLDER = "holder"
    """The browser holds the key the attempt was started under."""
    OTHER = "other"
    """A visitor started the attempt, and this browser holds no key or another one."""
    NO_VISITOR = "no_visitor"
    """No visitor started it: an operator's attempt, published while open."""


def viewer_of(row: LiveRow | None, key: StartKey | None) -> Viewer:
    """The viewer the page renders for, from the live row the public id names (``None`` for
    an attempt no visitor started) and the key the browser's cookie carries (``None`` for
    none or not a key); a hash comparison, as the decision's."""
    if row is None:
        return Viewer.NO_VISITOR
    if key is not None and row.holds(key):
        return Viewer.HOLDER
    return Viewer.OTHER


def held_position(state: AttemptState, decision: Decision, payload_digest: str) -> int | None:
    """The position of ``decision`` already in the log under ``payload_digest``, or
    ``None``: an approval under the digest, or a close by a decline under it. What a
    repeat is answered with whatever the clock says (history 16 of the step's forks), and
    what the sweeper reads to repair a row."""
    match decision:
        case Decision.APPROVED:
            given = state.approved
            if given is None:
                return None
            assert isinstance(given.event, Approved)
            return given.position if given.event.payload_digest == payload_digest else None
        case Decision.DECLINED:
            closed = state.closed
            if closed is None or not isinstance(closed.event, Declined):
                return None
            return closed.position if closed.event.payload_digest == payload_digest else None


def deadline_of(state: AttemptState, configuration: DemoConfiguration) -> datetime | None:
    """When the wait for a decision ends: the approval request's recorded instant plus the
    configured wait, ``None`` before any request. A decision is admitted strictly before
    it; the sweeper closes the wait at or past it."""
    requested = state.approval_requested
    if requested is None:
        return None
    return requested.timestamp + timedelta(seconds=configuration.approval_wait_seconds)


def _wait_refusal(
    state: AttemptState, log: DecideLog, configuration: DemoConfiguration
) -> DecideRefused | None:
    deadline = deadline_of(state, configuration)
    if deadline is None:
        return DecideRefused(DecideRefusalKind.NO_REQUEST, "no approval is requested yet")
    if log.now() >= deadline:
        return DecideRefused(DecideRefusalKind.LATE, "the wait for a decision has ended")
    return None


def _on_the_log(
    request: DecideRequest, row: LiveRow, log: DecideLog, rules: Rules
) -> int | CommandRefused:
    """The agent's command for the decision, its position or its refusal."""
    match request.decision:
        case Decision.APPROVED:
            delivered = deliver_approval(
                ApprovalDelivery(
                    row.run_id, row.attempt, DEMO_VISITOR.identity, request.payload_digest
                ),
                log,
                rules=rules,
            )
            return delivered if isinstance(delivered, CommandRefused) else delivered.position
        case Decision.DECLINED:
            declined = decline(
                DeclineDelivery(
                    row.run_id, row.attempt, DEMO_VISITOR.identity, request.payload_digest
                ),
                log,
                rules=rules,
            )
            return declined if isinstance(declined, CommandRefused) else declined.position


def _instant_at(log: DecideLog, row: LiveRow, position: int) -> datetime:
    """The log's instant of the event at ``position``: what the row records as the
    decision's instant, so the row and the log say one moment."""
    events = log.events(row.run_id, row.attempt)
    logged = events[position - 1]
    assert logged.position == position, "positions are dense"
    return logged.timestamp


__all__ = [
    "DEMO_VISITOR",
    "DecideComposition",
    "DecideLog",
    "DecideOutcome",
    "DecideRefusalKind",
    "DecideRefused",
    "DecideRequest",
    "Decided",
    "DecisionRows",
    "Review",
    "Viewer",
    "deadline_of",
    "decide",
    "decision_name",
    "held_position",
    "review_of",
    "viewer_of",
]
