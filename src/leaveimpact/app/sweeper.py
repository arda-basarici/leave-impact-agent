"""The sweeper: one pass over the demo's public attempts that reconciles what no process
owns, from a snapshot of the log and the live rows to a list of actions, each performed
through the agent's own commands (the live-path commands step, fork 6; ruling 4's four
reconciliations and the fifteen-minute close).

**One function decides, one driver acts.** ``actions_of`` is pure: from a snapshot (the
public admissions of the demo's ledger with their folded state, their live row and, for a
closed one, their publication record; the execution slot's holder; the inventories the
driver remembers writing; the log's clock), the configuration and the commit this code
runs as, the actions in a closed union. The driver takes the snapshot, performs each
action through a command and reports what each did; an operator command runs one pass,
and the worker service of the next step calls the same function between claims. The
function reads one snapshot, so an attempt it finalizes is published on the next pass,
not this one.

**The reconciliations, scoped to public attempts.** The sweeper acts on attempts the
demo's start admitted (the admitter ``demo-start`` at position 1 on the demo's ledger)
and leaves the operator's attempts to the lifecycle that admitted them, the wall bound
included (fork 5 as amended). For each open public attempt, in this order: a recorded
stop is finished by the terminal worker when its first segment ran the commit this code
runs as (it claims, so the slot is taken, and closes by the stop), and otherwise closed
by abandonment as interrupted at the generation the snapshot showed, the recorded stop
kept as the ending by the transition's own rule, since a claim across commits is an
operator's audited override and never the sweeper's (group 3's external read: the first
build claimed under the current commit whatever the first segment ran, and a stop from
before a deploy stayed open with the slot held, pass after pass); an attempt never
claimed is closed as cancelled once its admission is older than the approval wait (the
orphan of a start that lost its rows, and an attempt the slot never came free for); an
approval requested and not given is closed as cancelled at or past the deadline, the
request's recorded instant plus the wait, under the decision's own serialization with
the state reloaded and the condition re-read there, so a decision that holds the lock
first is admitted and one that waited past the deadline is refused (histories 1, 2, 5,
6 and 15 of the step); and the slot's holder with an open segment is fenced and closed as
interrupted, its liabilities kept by the settlement, once the claim's instant is older
than the wall bound, its live row or none (the orphan a process claimed is the log's to
close, or the slot stays held for good; the worker service's external read), measured per
occupied segment from its claim and never across the approval pause, since a request
outstanding is the wait's case above.
Two states no process of this code will continue are closed as interrupted
at the generation the snapshot showed, the liabilities kept (the worker service's step):
an attempt whose first segment ran another commit than this code's, whatever its state
and the wait included, since a claim across commits is the operator's audited override
and a preserved window would end in the same closure after the approval; and a segment
cleanly ended with nothing outstanding whose next claim the transition reads as a
recovery (``log_transition.next_claim``, the launcher's own reading of work against
recovery), since ruling 4 allows a public attempt no automatic recovery; an approval
delivered and not yet resumed is a resumption, the worker service's to claim, and is left
alone. The sweeper applies no liveness rule to a holder inside the wall (history 10),
and its reading equals the launcher's next-step rule under a human approval wherever the
segment has ended. For each closed public attempt, a publication
that is not published is published, and one inventory per distinct scope (the world and
the registration commit the attempts' frozen inputs name, since the image carries no
registration commit) is written after the publications of the pass. A live row whose
log holds a decision it does not is repaired (history 3), the decision's instant the
event's.

**A closure lands on the state it was decided on.** Each abandonment hands the command
the state the driver checked, so the generation it fences is the checked one and a
takeover in between is refused by the store as stale; and each states its condition as
a precondition the store reads on the current state under the attempt's lock, so a
segment that ended, a claim that landed or a decision that arrived between the driver's
reload and the closure refuses it (group 3's external read: the first build rechecked
closure and the generation alone, and a worker that requested approval and ended its
segment after the snapshot was fenced as interrupted). A refused closure is read from
the state reloaded and the driver's own predicate over it, never from the refusal's
wording (fork 10): a condition that no longer holds is reported as the state's move and
nothing is done; the next pass reads the new state.

**The inventory is remembered, not inferred from the publications.** The driver keeps,
per scope, the identities of the publications (the run, the attempt and the object's
digest) the inventory it last wrote covered; the snapshot carries that memory, and a
published attempt whose identity is not in it, or a publication this pass makes,
schedules the scope's inventory, which then covers every published identity the
snapshot showed and the pass's own. A crash after a publication and before its
inventory, or an inventory write that raised, leaves the identity out of the memory, so
the next pass writes it (group 3's external read: the first build scheduled the
inventory beside an unpublished attempt only, and a death between the two left it
unwritten for good). Identities and never instants: a publication made by another
process, the operator's command among them, is as new to the memory as the pass's own
whatever its record's instant says, where the first memory kept the latest instant and
missed a record at or before it (the read's second round). The memory is the process's:
a restart rewrites
each scope's inventory once, a new object under a new digest, since an inventory carries
the instant of the snapshot it was built from, and the sweep command, one process per
pass, writes it on every pass that lists a published attempt. A durable marker on the
live row is the step's candidate if the live pages come to read the inventory or the
command's passes come to run often.

**The lookback.** The snapshot lists public admissions since a lookback before the clock,
seven days by default, and every open one whatever its age; a closed public attempt left
unpublished longer than the lookback is the operator's ``publish`` command. The
alternative, every public admission ever on every pass, grows with the ledger for
nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Protocol, cast

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
from leaveimpact.agent.log_transition import AttemptState, ClaimKind, Rules, next_claim
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

Scope = tuple[WorldVersion, str]
"""An inventory's scope on the demo's ledger: the world and the registration commit."""

PublicationKey = tuple[str, int, str]
"""A publication's identity: the run, the attempt and the digest of the object sealed."""


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
    order, the slot's holder, and per scope the publications the driver's last inventory
    of it covered."""

    taken_at: datetime
    attempts: tuple[SweptAttempt, ...]
    slot: SlotHolder | None
    inventoried: Mapping[Scope, frozenset[PublicationKey]] = field(
        default_factory=dict[Scope, frozenset[PublicationKey]]
    )


# --- the actions -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Finalize:
    """Close an open attempt by the stop its log records, through the terminal worker."""

    run_id: str
    attempt: int


@dataclass(frozen=True, slots=True)
class CloseStopped:
    """Close an attempt whose recorded stop this code cannot finalize, its first segment
    having run another commit: abandoned as interrupted at the generation the snapshot
    showed, the recorded stop kept as the ending."""

    run_id: str
    attempt: int
    generation: int


@dataclass(frozen=True, slots=True)
class Publish:
    """Publish a closed attempt's export; the scope is its inventory's."""

    run_id: str
    attempt: int
    world_version: WorldVersion
    registration_commit: str

    @property
    def scope(self) -> Scope:
        return (self.world_version, self.registration_commit)


@dataclass(frozen=True, slots=True)
class WriteInventory:
    """Write the inventory of one scope, after the pass's publications; ``covering`` is
    every published identity the snapshot showed in the scope, empty when the pass
    publishes the scope's first."""

    world_version: WorldVersion
    registration_commit: str
    covering: frozenset[PublicationKey]

    @property
    def scope(self) -> Scope:
        return (self.world_version, self.registration_commit)


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
class CloseUnrecovered:
    """Close an attempt no process of this code will continue, as interrupted at the
    generation the snapshot showed, its liabilities kept: its first segment ran another
    commit (whatever its state, the wait included), or its segment ended cleanly with
    nothing outstanding and the next claim would be a recovery, which ruling 4 forbids a
    public attempt (the worker service's step)."""

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
    Finalize
    | CloseStopped
    | Publish
    | WriteInventory
    | CloseWait
    | CloseUnclaimed
    | FenceAndClose
    | CloseUnrecovered
    | RepairRow
)

Closure = CloseStopped | CloseWait | CloseUnclaimed | FenceAndClose | CloseUnrecovered


def actions_of(
    snapshot: SweepSnapshot,
    configuration: DemoConfiguration,
    *,
    harness_commit: str,
    wall: timedelta | None = None,
) -> tuple[SweepAction, ...]:
    """The actions one pass takes over ``snapshot`` under ``configuration`` as the code at
    ``harness_commit``, in the order the module docstring states: the row repairs and the
    closures per attempt in admission order, the publications, then one inventory per
    scope that a publication of the pass or a published identity outside the remembered
    inventory calls for. ``wall`` replaces the configuration's wall bound for the pass:
    the worker service's start pass reads a dead service's holder as past it with a wall
    of zero, which the configuration itself refuses as a value."""
    actions: list[SweepAction] = []
    seen: dict[Scope, set[PublicationKey]] = {}
    needed: list[Scope] = []
    wait = timedelta(seconds=configuration.approval_wait_seconds)
    if wall is None:
        wall = timedelta(seconds=configuration.attempt_wall_seconds)
    for each in snapshot.attempts:
        repair = _row_repair(each)
        if repair is not None:
            actions.append(repair)
        if each.state.closed is not None:
            inputs = each.state.inputs
            assert inputs is not None, "a closed attempt was admitted"
            scope = (inputs.context.world_version, inputs.preregistration_commit)
            publication = each.publication
            if publication is None or publication.state is not PublicationStatus.PUBLISHED:
                actions.append(Publish(each.run_id, each.attempt, *scope))
                seen.setdefault(scope, set())
                if scope not in needed:
                    needed.append(scope)
                continue
            assert publication.object_digest is not None, "a published record names its object"
            key = (each.run_id, each.attempt, publication.object_digest)
            seen.setdefault(scope, set()).add(key)
            if key not in snapshot.inventoried.get(scope, frozenset()) and scope not in needed:
                needed.append(scope)
            continue
        closure = _closure_of(each, snapshot, wait=wait, wall=wall, harness_commit=harness_commit)
        if closure is not None:
            actions.append(closure)
    actions.extend(WriteInventory(*scope, frozenset(seen[scope])) for scope in needed)
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
    each: SweptAttempt,
    snapshot: SweepSnapshot,
    *,
    wait: timedelta,
    wall: timedelta,
    harness_commit: str,
) -> Finalize | Closure | None:
    """The one closure an open public attempt is due, or none."""
    state = each.state
    now = snapshot.taken_at
    if state.stopped is not None:
        assert state.segments, "a recorded stop follows a claim"
        if state.segments[0].harness.commit == harness_commit:
            return Finalize(each.run_id, each.attempt)
        return CloseStopped(each.run_id, each.attempt, state.generation)
    segment = state.current_segment
    if segment is None:
        if now >= each.admitted_at + wait:
            return CloseUnclaimed(each.run_id, each.attempt)
        return None
    if state.segments[0].harness.commit != harness_commit:
        return CloseUnrecovered(each.run_id, each.attempt, state.generation)
    if state.approval_requested is not None and state.approved is None:
        deadline = state.approval_requested.timestamp + wait
        if now >= deadline:
            return CloseWait(each.run_id, each.attempt)
        return None
    if segment.ended and next_claim(state) is ClaimKind.RECOVERY:
        return CloseUnrecovered(each.run_id, each.attempt, state.generation)
    slot = snapshot.slot
    if (
        not segment.ended
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


@dataclass
class InventoryMemory:
    """The driver's memory of the inventories it wrote (see the module): per scope, the
    publications the last inventory covered, and those the current pass made, folded into
    the former when the scope's inventory is written."""

    covered: dict[Scope, frozenset[PublicationKey]] = field(
        default_factory=dict[Scope, frozenset[PublicationKey]]
    )
    published: dict[Scope, set[PublicationKey]] = field(
        default_factory=dict[Scope, set[PublicationKey]]
    )

    def note_publication(self, scope: Scope, key: PublicationKey) -> None:
        self.published.setdefault(scope, set()).add(key)

    def note_inventory(self, scope: Scope, covering: frozenset[PublicationKey]) -> None:
        self.covered[scope] = covering | self.published.pop(scope, set())


@dataclass(frozen=True, slots=True)
class SweepComposition:
    """What the composition root fixes for every pass: the configuration, the rules, the
    harness revision the finalizations claim under, the commit the exports and inventories
    are built as, the two publication commands bound to their publishers, the nonce source
    of the claims, the launch identity, the lookback, and the inventory memory the passes
    of one process share."""

    configuration: DemoConfiguration
    rules: Rules
    harness: HarnessRevision
    reader_commit: str
    publish_export: PublishExport
    write_inventory: WriteInventoryCommand
    nonces: Callable[[], str]
    launch: str = DEMO_SWEEPER.identity
    lookback: timedelta = DEFAULT_LOOKBACK
    memory: InventoryMemory = field(default_factory=InventoryMemory)


@dataclass(frozen=True, slots=True)
class SweepOutcome:
    """What one action did: carried when the command did what the action asked, found it
    already done, or found the state moved from under it; otherwise the detail says what
    stood in the way."""

    action: SweepAction
    carried: bool
    detail: str


SweepReport = tuple[SweepOutcome, ...]


def snapshot_of(log: SweepLog, rows: SweepRows, composition: SweepComposition) -> SweepSnapshot:
    """The snapshot of one pass: the public admissions since the lookback with every open
    one, each with its state, its row and, for a closed one, its publication; the slot;
    the inventory memory as it stands; the clock, read first."""
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
    return SweepSnapshot(
        taken_at, tuple(attempts), log.execution_slot(), dict(composition.memory.covered)
    )


def action_line(action: SweepAction) -> str:
    """The action's kind and its fields, as a log line names it; a set of publication
    identities is named by its size. The sweep command's and the worker service's one form.

    >>> action_line(CloseWait("demo-0abc", 1))
    'CloseWait run_id=demo-0abc attempt=1'
    """
    fields = " ".join(
        f"{name}={len(cast(frozenset[object], value)) if isinstance(value, frozenset) else value}"
        for name, value in asdict(action).items()
    )
    return f"{type(action).__name__} {fields}"


def sweep(log: SweepLog, rows: SweepRows, composition: SweepComposition) -> SweepReport:
    """One pass: the snapshot, the actions, each performed in order, the report."""
    snapshot = snapshot_of(log, rows, composition)
    actions = actions_of(
        snapshot, composition.configuration, harness_commit=composition.harness.commit
    )
    return tuple(perform(action, log, rows, composition) for action in actions)


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
            published = record.state is PublicationStatus.PUBLISHED
            if published:
                assert record.object_digest is not None, "a published record names its object"
                composition.memory.note_publication(
                    action.scope, (action.run_id, action.attempt, record.object_digest)
                )
            return SweepOutcome(action, published, f"publication {record.state.value}")
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
            composition.memory.note_inventory(action.scope, action.covering)
            return SweepOutcome(action, True, f"inventory {written.digest} {written.outcome.value}")
        case CloseWait():
            with log.serialized(decision_name(action.run_id, action.attempt)):
                state = log.load(action.run_id, action.attempt, rules=composition.rules)
                now = log.now()
                unmet = _wait_unmet(state, now, composition.configuration)
                if unmet is not None:
                    return SweepOutcome(action, True, unmet)
                return _abandon(
                    action,
                    state,
                    AbandonmentReason.CANCELLED,
                    lambda current: _wait_unmet(current, now, composition.configuration),
                    log,
                    composition,
                )
        case CloseUnclaimed():
            return _close_checked(
                action, AbandonmentReason.CANCELLED, _unclaimed_unmet, log, composition
            )
        case FenceAndClose():
            return _close_checked(
                action,
                AbandonmentReason.INTERRUPTED,
                lambda current: _holding_unmet(current, action.generation),
                log,
                composition,
            )
        case CloseStopped():
            return _close_checked(
                action,
                AbandonmentReason.INTERRUPTED,
                lambda current: _stopped_unmet(current, action.generation),
                log,
                composition,
            )
        case CloseUnrecovered():
            return _close_checked(
                action,
                AbandonmentReason.INTERRUPTED,
                lambda current: _unrecovered_unmet(
                    current, action.generation, composition.harness.commit
                ),
                log,
                composition,
            )
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


Unmet = Callable[[AttemptState], str | None]
"""An action's own condition over a state: ``None`` while it holds, otherwise the sentence
that says how the state moved."""


def _close_checked(
    action: Closure,
    reason: AbandonmentReason,
    unmet: Unmet,
    log: SweepLog,
    composition: SweepComposition,
) -> SweepOutcome:
    """The closure after the driver's own reload: the condition read on it, then the
    abandonment on that state with the condition as the store's precondition."""
    state = log.load(action.run_id, action.attempt, rules=composition.rules)
    moved = _closed_or(state, unmet)
    if moved is not None:
        return SweepOutcome(action, True, moved)
    return _abandon(action, state, reason, unmet, log, composition)


def _abandon(
    action: Closure,
    state: AttemptState,
    reason: AbandonmentReason,
    unmet: Unmet,
    log: SweepLog,
    composition: SweepComposition,
) -> SweepOutcome:
    """The abandonment under the sweeper's identity on the state checked, the condition as
    the store's precondition; a refusal is read from the state reloaded and the condition
    over it, never from the refusal's wording."""
    closed = abandon(
        AbandonRequest(action.run_id, action.attempt, DEMO_SWEEPER.identity, reason),
        log,
        rules=composition.rules,
        state=state,
        precondition=unmet,
    )
    if isinstance(closed, AttemptAbandoned):
        return SweepOutcome(action, True, f"{reason.value} at position {closed.position}")
    latest = log.load(action.run_id, action.attempt, rules=composition.rules)
    moved = _closed_or(latest, unmet)
    if moved is not None:
        return SweepOutcome(action, True, moved)
    return SweepOutcome(action, False, closed.reason)


def _closed_or(state: AttemptState, unmet: Unmet) -> str | None:
    if state.closed is not None:
        return f"closed at position {state.closed.position}"
    return unmet(state)


def _wait_unmet(state: AttemptState, now: datetime, configuration: DemoConfiguration) -> str | None:
    """Why the wait for a decision is not over with none given: closed, approved, no
    request, or the deadline not yet reached at ``now``."""
    if state.closed is not None:
        return f"closed at position {state.closed.position}"
    given = state.approved
    if given is not None:
        return f"approved at position {given.position}"
    deadline = deadline_of(state, configuration)
    if deadline is None:
        return "no approval is requested"
    if now < deadline:
        return "the wait is open"
    return None


def _unclaimed_unmet(state: AttemptState) -> str | None:
    if state.closed is not None:
        return f"closed at position {state.closed.position}"
    if state.current_segment is not None:
        return "claimed meanwhile"
    return None


def _holding_unmet(state: AttemptState, generation: int) -> str | None:
    """Why the attempt no longer holds the slot past the wall at ``generation``: closed,
    taken over, its segment ended (the approval pause, or a clean stop), or an approval
    requested and not given, which is the wait's case whether or not the segment has ended
    yet (the read's second round: the request and the segment's end are two events, and a
    worker may die, or the closure land, between them)."""
    if state.closed is not None:
        return f"closed at position {state.closed.position}"
    if state.generation != generation:
        return f"taken over by generation {state.generation}"
    if state.approval_requested is not None and state.approved is None:
        return "an approval is requested"
    segment = state.current_segment
    if segment is None or segment.ended:
        return "the segment ended"
    return None


def _stopped_unmet(state: AttemptState, generation: int) -> str | None:
    if state.closed is not None:
        return f"closed at position {state.closed.position}"
    if state.generation != generation:
        return f"taken over by generation {state.generation}"
    return None


def _unrecovered_unmet(state: AttemptState, generation: int, harness_commit: str) -> str | None:
    """Why the attempt is no longer one nobody will continue at ``generation``: closed,
    taken over, or (on this commit alone, since another commit's attempt stays unrecoverable
    whatever else happened) an approval requested, its segment open again, or a next claim
    the transition reads as a resumption rather than a recovery; the planner's branches
    restated, field by field."""
    if state.closed is not None:
        return f"closed at position {state.closed.position}"
    if state.generation != generation:
        return f"taken over by generation {state.generation}"
    if state.segments and state.segments[0].harness.commit != harness_commit:
        return None
    if state.approval_requested is not None and state.approved is None:
        return "an approval is requested"
    segment = state.current_segment
    if segment is None:
        return "never claimed"
    if not segment.ended:
        return "the segment is open"
    if next_claim(state) is not ClaimKind.RECOVERY:
        return "the next claim is not a recovery"
    return None


__all__ = [
    "DEFAULT_LOOKBACK",
    "DEMO_SWEEPER",
    "CloseStopped",
    "CloseUnclaimed",
    "CloseUnrecovered",
    "CloseWait",
    "FenceAndClose",
    "Finalize",
    "InventoryMemory",
    "Publish",
    "PublishExport",
    "PublicationKey",
    "RepairRow",
    "Scope",
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
    "action_line",
    "actions_of",
    "perform",
    "snapshot_of",
    "sweep",
]
