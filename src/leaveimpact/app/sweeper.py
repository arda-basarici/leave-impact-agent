"""The sweeper: one pass over the demo's public attempts that reconciles what no process
owns, from a snapshot of the log and the live rows to a list of actions, each performed
through the agent's own commands (the live-path commands step, fork 6; ruling 4's four
reconciliations and the fifteen-minute close).

**One function decides, one driver acts.** ``actions_of`` is pure: from a snapshot (the
public admissions of the demo's ledger with their folded state, their live row and, for a
closed one, their publication record; the execution slot's holder; the log's clock) and
the configuration, the actions in a closed union. The driver takes the snapshot, performs
each action through a command and reports what each did; an operator command runs one
pass, and the worker service of the next step calls the same function between claims.
The function reads one snapshot, so an attempt it finalizes is published on the next
pass, not this one.

**The reconciliations, scoped to public attempts.** The sweeper acts on attempts the
demo's start admitted (the admitter ``demo-start`` at position 1 on the demo's ledger)
and leaves the operator's attempts to the lifecycle that admitted them, the wall bound
included (fork 5 as amended). For each open public attempt, in this order: a recorded
stop is finished by the terminal worker (it claims, so the slot is taken, and closes by
the stop); an attempt never claimed is closed as cancelled once its admission is older
than the approval wait (the orphan of a start that lost its rows, and an attempt the
slot never came free for); an approval requested and not given is closed as cancelled at
or past the deadline, the request's recorded instant plus the wait, under the decision's
own serialization with the state reloaded and the condition re-read there, so a decision
that holds the lock first is admitted and one that waited past the deadline is refused
(histories 1, 2, 5, 6 and 15 of the step); and the slot's holder with a live row and an
open segment is fenced and closed as interrupted, its liabilities kept by the settlement,
once the claim's instant is older than the wall bound, measured per occupied segment
from its claim and never across the approval pause, since a request outstanding is the
wait's case above. A public attempt with its segment cleanly ended and nothing requested
gets nothing: the worker's recovery is the next step's. The sweeper applies no liveness
rule to a holder inside the wall (history 10). For each closed public attempt, a
publication that is not published is published, and one inventory per distinct scope
(the world and the registration commit the attempts' frozen inputs name, since the image
carries no registration commit) is written after the publications of the pass. A live
row whose log holds a decision it does not is repaired (history 3), the decision's
instant the event's.

**What the sweeper reads of a refusal: nothing.** An abandonment may be retried after a
crash; the driver reloads the attempt's state and reads closure from it, never from the
refusal's wording (fork 10). A state that changed under the action (a decision landed, a
takeover moved the generation) is reported as such and nothing is done; the next pass
reads the new state.

**The lookback.** The snapshot lists public admissions since a lookback before the clock,
seven days by default, and every open one whatever its age; a closed public attempt left
unpublished longer than the lookback is the operator's ``publish`` command. The
alternative, every public admission ever on every pass, grows with the ledger for
nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from leaveimpact.agent.appender import LogCommands
from leaveimpact.agent.commands import (
    AbandonRequest,
    AttemptAbandoned,
    CommandRefused,
    InventoryRequest,
    InventoryWritten,
    PublishRequest,
    TerminalComposition,
    WorkRequest,
    abandon,
    finalize,
)
from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.log_events import Approved, Declined, Producer
from leaveimpact.agent.log_store import AdmittedAttempt, SlotHolder
from leaveimpact.agent.log_transition import AttemptState, Rules
from leaveimpact.agent.worker import WorkerConfiguration, WorkerEndingKind
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.decide import deadline_of, decision_name
from leaveimpact.app.live import Decision, LiveRow
from leaveimpact.app.public import PublicId
from leaveimpact.app.start import DEMO_START
from leaveimpact.core import AbandonmentReason
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.inventory import InventoryScope, PublicationStatus
from leaveimpact.core.run_timing import HarnessRevision

DEMO_SWEEPER = Producer("demo-sweeper")
"""The authority of every closure the sweeper makes, and the launch identity of the
claims its finalizations take."""

DEFAULT_LOOKBACK = timedelta(days=7)
"""How far back the snapshot lists closed public admissions (see the module)."""


class SweepLog(LogCommands, Protocol):
    """The log's commands and reads a pass uses, as the log store provides them."""

    def serialized(self, name: str) -> AbstractContextManager[None]: ...

    def now(self) -> datetime: ...

    def admitted_by(
        self, admitter: Producer, ledger_id: str, *, since: datetime
    ) -> tuple[AdmittedAttempt, ...]: ...

    def execution_slot(self) -> SlotHolder | None: ...

    def publication_of(self, run_id: str, attempt: int) -> PublicationRecord | None: ...


class SweepRows(Protocol):
    """The live rows as the app store reads and records them."""

    def live_row_of_attempt(self, run_id: str, attempt: int) -> LiveRow | None: ...

    def record_decision(
        self, public_id: PublicId, decision: Decision, decided_at: datetime
    ) -> LiveRow: ...


# --- the snapshot ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SweptAttempt:
    """One public attempt as the snapshot read it: its admission's instant, its folded
    state, its live row (``None`` for the orphan of a start that lost its rows) and, for a
    closed one, its publication record."""

    run_id: str
    attempt: int
    admitted_at: datetime
    state: AttemptState
    row: LiveRow | None
    publication: PublicationRecord | None


@dataclass(frozen=True, slots=True)
class SweepSnapshot:
    """What one pass decides over: the clock's instant, the public attempts in admission
    order, and the slot's holder."""

    taken_at: datetime
    attempts: tuple[SweptAttempt, ...]
    slot: SlotHolder | None


# --- the actions -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Finalize:
    """Close an open attempt by the stop its log records, through the terminal worker."""

    run_id: str
    attempt: int


@dataclass(frozen=True, slots=True)
class Publish:
    """Publish a closed attempt's export."""

    run_id: str
    attempt: int


@dataclass(frozen=True, slots=True)
class WriteInventory:
    """Write the inventory of one scope, after the pass's publications."""

    world_version: WorldVersion
    registration_commit: str


@dataclass(frozen=True, slots=True)
class CloseWait:
    """Close an attempt whose wait for a decision ended with none given: cancelled."""

    run_id: str
    attempt: int


@dataclass(frozen=True, slots=True)
class CloseUnclaimed:
    """Close an attempt never claimed within the wait: cancelled."""

    run_id: str
    attempt: int


@dataclass(frozen=True, slots=True)
class FenceAndClose:
    """Fence the generation that holds the slot past the wall and close the attempt as
    interrupted, its liabilities kept."""

    run_id: str
    attempt: int
    generation: int


@dataclass(frozen=True, slots=True)
class RepairRow:
    """Write onto the live row the decision its log holds."""

    public_id: PublicId
    decision: Decision
    decided_at: datetime


SweepAction = (
    Finalize | Publish | WriteInventory | CloseWait | CloseUnclaimed | FenceAndClose | RepairRow
)


def actions_of(
    snapshot: SweepSnapshot, configuration: DemoConfiguration
) -> tuple[SweepAction, ...]:
    """The actions one pass takes over ``snapshot`` under ``configuration``, in the order
    the module docstring states: the row repairs and the closures per attempt in admission
    order, the publications, then one inventory per scope among them."""
    actions: list[SweepAction] = []
    scopes: dict[tuple[WorldVersion, str], None] = {}
    wait = timedelta(seconds=configuration.approval_wait_seconds)
    wall = timedelta(seconds=configuration.attempt_wall_seconds)
    for each in snapshot.attempts:
        repair = _row_repair(each)
        if repair is not None:
            actions.append(repair)
        if each.state.closed is not None:
            publication = each.publication
            if publication is None or publication.state is not PublicationStatus.PUBLISHED:
                actions.append(Publish(each.run_id, each.attempt))
                inputs = each.state.inputs
                assert inputs is not None, "a closed attempt was admitted"
                scopes[(inputs.context.world_version, inputs.preregistration_commit)] = None
            continue
        closure = _closure_of(each, snapshot, wait=wait, wall=wall)
        if closure is not None:
            actions.append(closure)
    actions.extend(WriteInventory(world, commit) for world, commit in scopes)
    return tuple(actions)


def _row_repair(each: SweptAttempt) -> RepairRow | None:
    """The decision the log holds that the row does not, as the row should record it."""
    row = each.row
    if row is None:
        return None
    state = each.state
    given = state.approved
    if given is not None and row.decision is not Decision.APPROVED:
        assert isinstance(given.event, Approved)
        return RepairRow(row.public_id, Decision.APPROVED, given.timestamp)
    closed = state.closed
    declined = closed is not None and isinstance(closed.event, Declined)
    if declined and row.decision is not Decision.DECLINED:
        assert closed is not None
        return RepairRow(row.public_id, Decision.DECLINED, closed.timestamp)
    return None


def _closure_of(
    each: SweptAttempt, snapshot: SweepSnapshot, *, wait: timedelta, wall: timedelta
) -> Finalize | CloseUnclaimed | CloseWait | FenceAndClose | None:
    """The one closure an open public attempt is due, or none."""
    state = each.state
    now = snapshot.taken_at
    if state.stopped is not None:
        return Finalize(each.run_id, each.attempt)
    segment = state.current_segment
    if segment is None:
        if now >= each.admitted_at + wait:
            return CloseUnclaimed(each.run_id, each.attempt)
        return None
    if state.approval_requested is not None and state.approved is None:
        deadline = state.approval_requested.timestamp + wait
        if now >= deadline:
            return CloseWait(each.run_id, each.attempt)
        return None
    slot = snapshot.slot
    if (
        not segment.ended
        and each.row is not None
        and slot is not None
        and (slot.run_id, slot.attempt) == (each.run_id, each.attempt)
        and now >= slot.claimed_at + wall
    ):
        return FenceAndClose(each.run_id, each.attempt, slot.generation)
    return None


# --- the driver --------------------------------------------------------------------------


PublishExport = Callable[[PublishRequest], PublicationRecord | CommandRefused]
"""The agent's publish command bound to its publisher and rules."""

WriteInventoryCommand = Callable[[InventoryRequest], InventoryWritten]
"""The agent's inventory command bound to its publisher and rules."""


@dataclass(frozen=True, slots=True)
class SweepComposition:
    """What the composition root fixes for every pass: the configuration, the rules, the
    harness revision the finalizations claim under, the commit the exports and inventories
    are built as, the two publication commands bound to their publishers, the nonce source
    of the claims, the launch identity, and the lookback."""

    configuration: DemoConfiguration
    rules: Rules
    harness: HarnessRevision
    reader_commit: str
    publish_export: PublishExport
    write_inventory: WriteInventoryCommand
    nonces: Callable[[], str]
    launch: str = DEMO_SWEEPER.identity
    lookback: timedelta = DEFAULT_LOOKBACK


@dataclass(frozen=True, slots=True)
class SweepOutcome:
    """What one action did: carried when the command did what the action asked or found it
    already done, otherwise the detail says what stood in the way."""

    action: SweepAction
    carried: bool
    detail: str


SweepReport = tuple[SweepOutcome, ...]


def snapshot_of(log: SweepLog, rows: SweepRows, composition: SweepComposition) -> SweepSnapshot:
    """The snapshot of one pass: the public admissions since the lookback with every open
    one, each with its state, its row and, for a closed one, its publication; the slot;
    the clock, read first."""
    taken_at = log.now()
    configuration = composition.configuration
    listed = log.admitted_by(
        DEMO_START, configuration.ledger_id, since=taken_at - composition.lookback
    )
    attempts: list[SweptAttempt] = []
    for each in listed:
        state = log.load(each.run_id, each.attempt, rules=composition.rules)
        publication = (
            log.publication_of(each.run_id, each.attempt) if state.closed is not None else None
        )
        attempts.append(
            SweptAttempt(
                each.run_id,
                each.attempt,
                each.admitted_at,
                state,
                rows.live_row_of_attempt(each.run_id, each.attempt),
                publication,
            )
        )
    return SweepSnapshot(taken_at, tuple(attempts), log.execution_slot())


def sweep(log: SweepLog, rows: SweepRows, composition: SweepComposition) -> SweepReport:
    """One pass: the snapshot, the actions, each performed in order, the report."""
    snapshot = snapshot_of(log, rows, composition)
    return tuple(
        perform(action, log, rows, composition)
        for action in actions_of(snapshot, composition.configuration)
    )


def perform(
    action: SweepAction, log: SweepLog, rows: SweepRows, composition: SweepComposition
) -> SweepOutcome:
    """One action through the command it takes; the match is closed, and a kind it does
    not know raises."""
    match action:
        case Finalize():
            return _finalize(action, log, composition)
        case Publish():
            record = composition.publish_export(
                PublishRequest(action.run_id, action.attempt, composition.reader_commit)
            )
            if isinstance(record, CommandRefused):
                return SweepOutcome(action, False, record.reason)
            return SweepOutcome(
                action,
                record.state is PublicationStatus.PUBLISHED,
                f"publication {record.state.value}",
            )
        case WriteInventory():
            written = composition.write_inventory(
                InventoryRequest(
                    InventoryScope(
                        action.world_version,
                        action.registration_commit,
                        composition.configuration.ledger_id,
                    ),
                    composition.reader_commit,
                )
            )
            return SweepOutcome(action, True, f"inventory {written.digest} {written.outcome.value}")
        case CloseWait():
            with log.serialized(decision_name(action.run_id, action.attempt)):
                state = log.load(action.run_id, action.attempt, rules=composition.rules)
                if not _wait_ended(state, log.now(), composition.configuration):
                    return SweepOutcome(action, True, _wait_state(state))
                return _abandon(action, state, AbandonmentReason.CANCELLED, log, composition)
        case CloseUnclaimed():
            state = log.load(action.run_id, action.attempt, rules=composition.rules)
            if state.closed is not None:
                return SweepOutcome(action, True, f"closed at position {state.closed.position}")
            if state.current_segment is not None:
                return SweepOutcome(action, True, "claimed meanwhile")
            return _abandon(action, state, AbandonmentReason.CANCELLED, log, composition)
        case FenceAndClose():
            state = log.load(action.run_id, action.attempt, rules=composition.rules)
            if state.closed is not None:
                return SweepOutcome(action, True, f"closed at position {state.closed.position}")
            if state.generation != action.generation:
                return SweepOutcome(action, True, f"taken over by generation {state.generation}")
            return _abandon(action, state, AbandonmentReason.INTERRUPTED, log, composition)
        case RepairRow():
            rows.record_decision(action.public_id, action.decision, action.decided_at)
            return SweepOutcome(action, True, f"row records {action.decision.value}")
        case _:
            raise TypeError(f"no command for a {type(action).__name__}")


def _finalize(action: Finalize, log: SweepLog, composition: SweepComposition) -> SweepOutcome:
    state = log.load(action.run_id, action.attempt, rules=composition.rules)
    inputs = state.inputs
    assert inputs is not None, "a listed attempt was admitted"
    ending = finalize(
        WorkRequest(action.run_id, action.attempt, composition.nonces(), composition.launch),
        log,
        TerminalComposition(WorkerConfiguration.of(inputs), composition.harness, composition.rules),
    )
    return SweepOutcome(
        action, ending.kind is WorkerEndingKind.CLOSED, f"{ending.kind.value}: {ending.detail}"
    )


def _abandon(
    action: CloseWait | CloseUnclaimed | FenceAndClose,
    state: AttemptState,
    reason: AbandonmentReason,
    log: SweepLog,
    composition: SweepComposition,
) -> SweepOutcome:
    """The abandonment under the sweeper's identity; a refusal is read for closure from
    the state reloaded, never from its wording."""
    closed = abandon(
        AbandonRequest(action.run_id, action.attempt, DEMO_SWEEPER.identity, reason),
        log,
        rules=composition.rules,
    )
    if isinstance(closed, AttemptAbandoned):
        return SweepOutcome(action, True, f"{reason.value} at position {closed.position}")
    latest = log.load(action.run_id, action.attempt, rules=composition.rules)
    if latest.closed is not None:
        return SweepOutcome(action, True, f"closed at position {latest.closed.position}")
    return SweepOutcome(action, False, closed.reason)


def _wait_ended(state: AttemptState, now: datetime, configuration: DemoConfiguration) -> bool:
    """Whether the wait for a decision is over with none given: open, requested, no
    approval, no decline, the deadline at or past ``now``."""
    if state.closed is not None or state.approved is not None:
        return False
    deadline = deadline_of(state, configuration)
    return deadline is not None and now >= deadline


def _wait_state(state: AttemptState) -> str:
    if state.closed is not None:
        return f"closed at position {state.closed.position}"
    given = state.approved
    if given is not None:
        return f"approved at position {given.position}"
    return "the wait is open"


__all__ = [
    "DEFAULT_LOOKBACK",
    "DEMO_SWEEPER",
    "CloseUnclaimed",
    "CloseWait",
    "FenceAndClose",
    "Finalize",
    "Publish",
    "PublishExport",
    "RepairRow",
    "SweepAction",
    "SweepComposition",
    "SweepLog",
    "SweepOutcome",
    "SweepReport",
    "SweepRows",
    "SweepSnapshot",
    "SweptAttempt",
    "WriteInventory",
    "WriteInventoryCommand",
    "actions_of",
    "perform",
    "snapshot_of",
    "sweep",
]
