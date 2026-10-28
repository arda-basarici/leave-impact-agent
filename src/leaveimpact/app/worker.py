"""The worker service: the long-running single-flight loop that runs a visitor's attempt
(ruling 4 of the demo milestone's entry; the worker service's step), composed of the
sweeper's pass and one work per tick, the work in a child process the service supervises.

**One tick.** The heartbeat is written idle (a deadline three intervals ahead); the
sweeper's snapshot is taken and its actions performed and reported, one line each, so
every reconciliation of the pass precedes the claim; then the one attempt due for work,
if any, is worked: the heartbeat written working (the claim's instant plus the wall plus
a cleanup allowance), the child spawned for the request under a fresh nonce and the
service's launch identity, waited on under the wall, its ending read and reported.
``work_due`` is the pure part: the oldest open public attempt whose next claim the
transition reads as a first claim or a resumption on this commit
(``log_transition.next_claim``), which is the launcher's WORK; an outstanding request, a
recovery, another commit's attempt or a closed one is never due, the sweeper's rule having
closed or kept each (``sweeper``, the eighth action). The tick blocks on the child:
single flight is the loop's shape, not a lock.

**The child.** The work runs in a process of its own because the blocked-work probe
showed the in-process shape losing the first stop signal: LangGraph submits the
checkpoint writes to an executor whose exit waits for every pending future before an
exception in flight propagates, so a write stuck on a lock parked the signal's exception
behind it and the process neither unwound nor exited on its own (the probe's findings,
``worker-blocked``). A child the service can terminate, wait on, kill and reap is ended
whatever its threads are doing. The composition names the child's command line per
request (``ChildCommand``; the demo's command line supplies its own ``work-one``) and the
spawn (``Spawn``; ``Popen`` with stdout piped, stderr and the environment inherited), and
the child prints its ending as one JSON line on stdout (``ending_line``), which the
supervisor decodes; nothing else crosses the pipe.

**The wall, the kill and the closure.** The supervisor waits on the child for the wall
(``communicate`` with the bound). Past it, the child is terminated, given a grace (ten
seconds by the step's ruling; a field, so a test runs the path in under a second), killed
if still there, and reaped. A killed child leaves its segment open, or ended by its own
stop handler, under the service's identity, and the next pass would close it only at the
wall; so the supervisor closes the attempt itself in the same tick, by the sweeper's rule
with the wall read as elapsed (``close_lost``: a fresh snapshot, the actions under a zero
wall, kept to the lost attempt's own), as the start pass does for a dead service. A child
that exits on its own without an ending line (a crash, a refusal, a stop that reached it
from outside) is closed the same way, its exit code reported: the service read no ending,
and the attempt is not left to the wall either. An attempt the child left waiting on an
approval request shows no action under the rule and the window is kept.

**The start pass.** Before the first tick the slot is read. A holder whose launch
identity carries this service's prefix and is not this process is a dead service, since
one service container runs at a time (the deploy drains the old one before the new one
starts), and one pass runs with the wall read as zero, so the sweeper's own rule decides
what the dead holder left: a recorded stop finalized, an outstanding request kept to its
deadline (the visitor's review window survives the restart), an open segment fenced and
closed, an ended one closed as unrecovered; any other holder, the operator's lifecycle
among them, is left alone and a normal pass runs. The closure is never a bare fence: the
external read of the step's entry found the request-then-death history the first draft
would have cancelled.

**The drain.** The stop signal's handler raises ``Drained``, a ``SystemExit`` subclass,
in the main thread wherever the loop is. Inside the wait on the child, the supervisor
terminates the child the same way (terminate, the grace, kill, reap) and re-raises;
``serve`` catches it and the process exits 0 with nothing closed: the replacement's start
pass or next tick closes what the drain left. The child installs the same handler, so a
terminate that reaches it ends the segment where an append is still possible
(``worker.Worker``, the handler around the invocation) and exits without an ending line,
and one that parks behind a stuck write ends with the kill.

**The heartbeat.** A small JSON file the compose healthcheck reads through
``worker-health``: the state and a deadline, idle three intervals ahead and rewritten
per tick once the pass has read the stores (a store that does not answer lets it go
stale), working the claim's instant plus the wall plus the cleanup allowance and
written at the claim. The check compares the clock with the deadline, one rule for both
states, so a loop that stopped ticking and a worker past its wall and its cleanup both
read unhealthy while an attempt lasting minutes reads healthy (the external read's fourth
point: a between-ticks touch would mark ordinary work unhealthy). The cleanup allowance
covers the grace and the closure after a kill.

This module reads no wall clock: the composition root hands the service the clock its
heartbeat deadlines are written from. Nothing here logs scenario content: the lines carry
action kinds and fields, run and attempt ids, generations, ending kinds and exit codes,
as the sweep command's do.
"""

from __future__ import annotations

import json
import os
import random
import secrets
import signal
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from types import FrameType
from typing import Any, Protocol

from leaveimpact.agent.commands import WorkRequest
from leaveimpact.agent.log_store import LogStoreUnavailable
from leaveimpact.agent.log_transition import ClaimKind, next_claim
from leaveimpact.agent.worker import WorkerEnding, WorkerEndingKind
from leaveimpact.app.store import AppStoreUnavailable
from leaveimpact.app.sweeper import (
    RepairRow,
    SweepAction,
    SweepComposition,
    SweepLog,
    SweepReport,
    SweepRows,
    SweepSnapshot,
    SweptAttempt,
    WriteInventory,
    action_line,
    actions_of,
    perform,
    snapshot_of,
)

SERVICE_PREFIX = "worker-"
"""The launch identities of this service's claims start with it: the kind the start pass
reads a dead holder by."""

DEFAULT_INTERVAL_SECONDS = 2.0
"""Between ticks; a visitor watches the page, and a tick is one snapshot."""

TERMINATE_GRACE_SECONDS = 10.0
"""Between the child's terminate and its kill (the step's ruling): the time a stop handler
that reached the child needs to end its segment where the store answers."""

CLEANUP_ALLOWANCE = timedelta(seconds=30)
"""What the working heartbeat's deadline grants past the wall for the grace, the kill and
the closure."""

HEARTBEAT_FILE = "LEAVEIMPACT_HEARTBEAT_FILE"
"""The environment name of the heartbeat's path."""

DEFAULT_HEARTBEAT_PATH = Path("/tmp/leaveimpact-worker-heartbeat.json")  # noqa: S108 - the container's own tmpfs, read by its healthcheck alone

IDLE_INTERVALS = 3
"""How many intervals an idle heartbeat stays fresh."""


class Drained(SystemExit):
    """The stop signal: raised in the main thread wherever the loop is; ``serve`` catches
    it and exits 0. The child installs the same handler and exits through it."""


def service_identity(now: datetime, token: str) -> str:
    """The launch identity of one service process: the prefix, the UTC start instant and a
    token, opaque as the claim requires.

    >>> service_identity(datetime.fromisoformat("2026-10-28T09:05:00+00:00"), "ab" * 16)
    'worker-20261028T090500Z-abababababababababababababababab'
    """
    return f"{SERVICE_PREFIX}{now:%Y%m%dT%H%M%SZ}-{token}"


# --- the pure part -----------------------------------------------------------------------


def work_due(snapshot: SweepSnapshot, *, harness_commit: str) -> SweptAttempt | None:
    """The one attempt the tick works after the pass, or none: the oldest open public
    attempt whose next claim is a first claim or a resumption on this commit; every other
    state is the sweeper's or nobody's (see the module)."""
    for each in snapshot.attempts:
        state = each.state
        if state.closed is not None or state.stopped is not None:
            continue
        if state.segments and state.segments[0].harness.commit != harness_commit:
            continue
        if state.approval_requested is not None and state.approved is None:
            continue
        if next_claim(state) is ClaimKind.RECOVERY:
            continue
        return each
    return None


def concerns(action: SweepAction, run_id: str, attempt: int) -> bool:
    """Whether ``action`` is about the attempt: a closure or a publication of it; a row
    repair or an inventory is about the surface or a scope, never one attempt.

    >>> from leaveimpact.app.sweeper import CloseUnrecovered, WriteInventory
    >>> concerns(CloseUnrecovered("run-a", 1, 2), "run-a", 1)
    True
    >>> concerns(CloseUnrecovered("run-a", 2, 2), "run-a", 1)
    False
    >>> concerns(WriteInventory("world-v", "c" * 40, frozenset()), "run-a", 1)
    False
    """
    match action:
        case RepairRow() | WriteInventory():
            return False
        case _:
            return (action.run_id, action.attempt) == (run_id, attempt)


# --- the heartbeat ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Heartbeat:
    """What the loop last said of itself: idle or working, and the instant past which the
    claim is stale."""

    state: str
    deadline: datetime

    def write(self, path: Path) -> None:
        """Written whole then moved into place, so a reader never sees a torn file."""
        staged = path.with_name(path.name + ".tmp")
        staged.write_text(
            json.dumps({"state": self.state, "deadline": self.deadline.isoformat()}),
            encoding="utf-8",
        )
        os.replace(staged, path)

    @classmethod
    def read(cls, path: Path) -> Heartbeat | None:
        """The heartbeat at ``path``, or ``None`` when absent or unreadable."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(str(data["state"]), datetime.fromisoformat(str(data["deadline"])))
        except (OSError, ValueError, KeyError, TypeError):
            return None


def worker_healthy(path: Path, now: datetime) -> bool:
    """The healthcheck's one bit: a heartbeat present whose deadline is still ahead."""
    beat = Heartbeat.read(path)
    return beat is not None and now < beat.deadline


# --- the child and its ending ------------------------------------------------------------


def ending_line(ending: WorkerEnding) -> str:
    """The one line the child prints: the ending's fields as a JSON object, no content of
    the run in it (the ending carries none).

    >>> ending_line(WorkerEnding(WorkerEndingKind.CLOSED, "run-a", 1, 2, "completed"))
    '{"kind": "closed", "run_id": "run-a", "attempt": 1, "generation": 2, "detail": "completed"}'
    """
    return json.dumps(
        {
            "kind": ending.kind.value,
            "run_id": ending.run_id,
            "attempt": ending.attempt,
            "generation": ending.generation,
            "detail": ending.detail,
        }
    )


def decode_ending_line(line: str) -> WorkerEnding | None:
    """The ending a child's line states, or ``None`` for a line that is not one.

    >>> stated = '{"kind": "fenced", "run_id": "run-a", "attempt": 1, "generation": null, '
    >>> decoded = decode_ending_line(stated + '"detail": "later claim"}')
    >>> decoded == WorkerEnding(WorkerEndingKind.FENCED, "run-a", 1, None, "later claim")
    True
    >>> decode_ending_line("Traceback (most recent call last):") is None
    True
    >>> decode_ending_line(stated.replace("fenced", "unknown") + '"detail": ""}') is None
    True
    """
    try:
        data = json.loads(line)
        kind = WorkerEndingKind(str(data["kind"]))
        generation = data["generation"]
        return WorkerEnding(
            kind,
            str(data["run_id"]),
            int(data["attempt"]),
            None if generation is None else int(generation),
            str(data["detail"]),
        )
    except (ValueError, KeyError, TypeError):
        return None


def _ending_of(stdout: str | None) -> WorkerEnding | None:
    """The ending on the child's last non-empty line, if it printed one."""
    lines = [line for line in (stdout or "").splitlines() if line.strip()]
    return decode_ending_line(lines[-1]) if lines else None


class ChildProcess(Protocol):
    """What the supervisor asks of a spawned child: ``Popen``'s calls, so the real one is
    a ``Popen`` and a test's is a fake with the same four."""

    @property
    def returncode(self) -> int | None: ...

    def communicate(self, *, timeout: float | None = None) -> tuple[Any, Any]: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


ChildCommand = Callable[[WorkRequest], Sequence[str]]
"""The child's command line for one request: the composition root spells it (the demo's
``work-one`` with the request's four fields; the probe's own program)."""

Spawn = Callable[[Sequence[str]], ChildProcess]
"""How the command line becomes a process; ``spawn_child`` is the real one."""


def spawn_child(argv: Sequence[str]) -> ChildProcess:
    """The real spawn: stdout piped for the ending line, stderr and the environment
    inherited, so the child's own lines reach the container's log and its stores and
    credentials are the service's."""
    return subprocess.Popen(list(argv), stdout=subprocess.PIPE, text=True)  # noqa: S603 - the argv is the composition root's, never a visitor's


@dataclass(frozen=True, slots=True)
class ChildLost:
    """A child that returned no ending: terminated at the wall (``at_wall``), or gone on
    its own with the exit code it left and no ending line read."""

    at_wall: bool
    exit_code: int | None
    detail: str


ChildOutcome = WorkerEnding | ChildLost


def _silent(line: str) -> None:
    pass


def end_child(child: ChildProcess, grace: float, report: Callable[[str], None] = _silent) -> None:
    """Terminate, wait the grace, kill if still there, reap and drain the pipe; the order
    the step's ruling fixed, so a stop handler that reached the child ends its segment
    first and a child parked behind a stuck write ends anyway. ``report`` gets a line at
    the terminate and one at a kill, so a log shows which ended it and when."""
    report("the child is terminated")
    child.terminate()
    try:
        child.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        report(f"the child did not end within the grace of {grace:g} seconds; killed")
        child.kill()
    except Drained:
        # The stop signal inside the grace (the probe's rerun found it, the wall and the
        # drain a tenth of a second apart): the container is stopping, so the grace ends
        # now, the child is killed and reaped, and the drain goes on; a child left alive
        # here would outlive the service until Docker's own kill.
        report("drained inside the grace; the child is killed")
        child.kill()
        child.communicate()
        raise
    child.communicate()


def supervise(
    child: ChildProcess,
    *,
    wall: float,
    grace: float,
    report: Callable[[str], None] = _silent,
) -> ChildOutcome:
    """The child waited on for ``wall`` seconds and its ending read; past the wall it is
    ended (``end_child``) and reported lost at the wall; a child gone without an ending
    line is reported lost with its exit code. A drain arriving inside the wait ends the
    child the same way and propagates. ``report`` gets the wall's line and the ending's."""
    try:
        stdout, _ = child.communicate(timeout=wall)
    except subprocess.TimeoutExpired:
        report(f"the wall of {wall:g} seconds passed")
        end_child(child, grace, report)
        return ChildLost(True, child.returncode, f"terminated at the wall of {wall:g} seconds")
    except Drained:
        report("drained while the child worked")
        end_child(child, grace, report)
        raise
    ending = _ending_of(stdout)
    if ending is None:
        return ChildLost(False, child.returncode, "exited without an ending line")
    return ending


# --- the composition --------------------------------------------------------------------


def _raise_drained(signum: int, frame: FrameType | None) -> None:
    raise Drained(0)


def install_stop_handlers() -> None:
    """SIGTERM (Docker's stop, the supervisor's terminate) and SIGINT (a terminal) both
    drain; the service and the child install the same."""
    signal.signal(signal.SIGTERM, _raise_drained)
    signal.signal(signal.SIGINT, _raise_drained)


@dataclass(frozen=True, slots=True)
class ServiceComposition:
    """What the root fixes for the service's life: the sweep composition (its launch the
    service's identity), the child's command line per request and the spawn, the clock
    the heartbeat's deadlines are written from (the root's: this module reads no wall
    clock), the heartbeat's path, the interval, the terminate grace, the sleep, the
    jitter and where the lines go."""

    sweep: SweepComposition
    child_command: ChildCommand
    now: Callable[[], datetime]
    spawn: Spawn = spawn_child
    heartbeat: Path | None = DEFAULT_HEARTBEAT_PATH
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS
    terminate_grace_seconds: float = TERMINATE_GRACE_SECONDS
    sleep: Callable[[float], None] = time.sleep
    jitter: Callable[[], float] = lambda: random.uniform(0.0, 0.5)  # noqa: S311 - a pause, not a secret
    report: Callable[[str], None] = print
    nonces: Callable[[], str] = field(default=lambda: secrets.token_hex(16))

    @property
    def identity(self) -> str:
        return self.sweep.launch


@dataclass(frozen=True, slots=True)
class TickReport:
    """What one tick did: the pass's report, the ending of the work if the child stated
    one, else the loss and the closure the supervisor performed for it."""

    swept: SweepReport
    worked: WorkerEnding | None
    lost: ChildLost | None = None
    closed: SweepReport = ()


# --- the loop ----------------------------------------------------------------------------


def _beat(composition: ServiceComposition, state: str, deadline: datetime) -> None:
    if composition.heartbeat is not None:
        Heartbeat(state, deadline).write(composition.heartbeat)


def _report_pass(composition: ServiceComposition, report: SweepReport) -> None:
    for outcome in report:
        composition.report(
            f"sweep: {action_line(outcome.action)}: "
            f"{'ok' if outcome.carried else 'NOT CARRIED'}: {outcome.detail}"
        )


def start_pass(log: SweepLog, rows: SweepRows, composition: ServiceComposition) -> SweepReport:
    """The pass before the first tick (see the module): with the wall read as zero when the
    slot's holder is a dead service, the sweeper's rule deciding the rest."""
    holder = log.execution_slot()
    dead = (
        holder is not None
        and holder.launch.startswith(SERVICE_PREFIX)
        and holder.launch != composition.identity
    )
    sweeping = composition.sweep
    wall: timedelta | None = None
    if dead:
        assert holder is not None
        composition.report(
            f"start: the slot is held by a dead service {holder.launch} "
            f"(run {holder.run_id} attempt {holder.attempt} generation {holder.generation}); "
            "its attempt is closed by the rule"
        )
        wall = timedelta(0)
    snapshot = snapshot_of(log, rows, sweeping)
    actions = actions_of(
        snapshot, sweeping.configuration, harness_commit=sweeping.harness.commit, wall=wall
    )
    report = tuple(perform(action, log, rows, sweeping) for action in actions)
    _report_pass(composition, report)
    return report


def close_lost(
    log: SweepLog, rows: SweepRows, composition: ServiceComposition, lost: SweptAttempt
) -> SweepReport:
    """The closure of an attempt whose child returned no ending (see the module): a fresh
    snapshot, the rule under a zero wall, its actions kept to this attempt's own,
    performed and reported; none when the rule keeps the attempt (a review window)."""
    sweeping = composition.sweep
    snapshot = snapshot_of(log, rows, sweeping)
    actions = actions_of(
        snapshot,
        sweeping.configuration,
        harness_commit=sweeping.harness.commit,
        wall=timedelta(0),
    )
    own = tuple(action for action in actions if concerns(action, lost.run_id, lost.attempt))
    report = tuple(perform(action, log, rows, sweeping) for action in own)
    _report_pass(composition, report)
    if not report:
        composition.report(
            f"work: run {lost.run_id} attempt {lost.attempt}: the rule keeps the attempt open; "
            "the next pass decides"
        )
    return report


def tick(log: SweepLog, rows: SweepRows, composition: ServiceComposition) -> TickReport:
    """One tick (see the module): the pass, then the one attempt due worked in a child
    under the wall, a lost child's attempt closed by the rule; the idle heartbeat once the
    pass has read the stores, so a store that does not answer lets it go stale."""
    snapshot = snapshot_of(log, rows, composition.sweep)
    _beat(
        composition,
        "idle",
        composition.now() + timedelta(seconds=composition.interval_seconds * IDLE_INTERVALS),
    )
    actions = actions_of(
        snapshot, composition.sweep.configuration, harness_commit=composition.sweep.harness.commit
    )
    swept = tuple(perform(action, log, rows, composition.sweep) for action in actions)
    _report_pass(composition, swept)
    due = work_due(snapshot, harness_commit=composition.sweep.harness.commit)
    if due is None:
        return TickReport(swept, None)
    wall = composition.sweep.configuration.attempt_wall_seconds
    request = WorkRequest(due.run_id, due.attempt, composition.nonces(), composition.identity)
    composition.report(f"work: run {due.run_id} attempt {due.attempt}: claiming")
    _beat(
        composition,
        "working",
        composition.now() + timedelta(seconds=wall) + CLEANUP_ALLOWANCE,
    )
    child = composition.spawn(composition.child_command(request))
    outcome = supervise(
        child,
        wall=wall,
        grace=composition.terminate_grace_seconds,
        report=lambda line: composition.report(
            f"work: run {due.run_id} attempt {due.attempt}: {line}"
        ),
    )
    if isinstance(outcome, WorkerEnding):
        composition.report(
            f"work: run {outcome.run_id} attempt {outcome.attempt}: ending={outcome.kind.value} "
            f"detail={outcome.detail} generation={outcome.generation}"
        )
        return TickReport(swept, outcome)
    composition.report(
        f"work: run {due.run_id} attempt {due.attempt}: the child {outcome.detail} "
        f"(exit code {outcome.exit_code}); the attempt is closed by the rule"
    )
    return TickReport(swept, None, lost=outcome, closed=close_lost(log, rows, composition, due))


def serve(log: SweepLog, rows: SweepRows, composition: ServiceComposition) -> int:
    """The service's life: the start pass, then ticks with the interval between, until the
    stop signal's ``Drained`` arrives anywhere in it; 0 then. A store that does not answer
    inside a tick (the probe's blocked-store cases: the snapshot's read waiting on a lock
    until the statement bound cancels it) is reported and the next tick retries, the
    heartbeat left stale meanwhile so the healthcheck says so; a broken invariant or any
    other fault still ends the process, which the restart policy brings back."""
    composition.report(f"worker: {composition.identity} starting")
    try:
        start_pass(log, rows, composition)
        while True:
            try:
                tick(log, rows, composition)
            except (LogStoreUnavailable, AppStoreUnavailable) as outage:
                composition.report(f"worker: a store did not answer ({outage}); retrying next tick")
            composition.sleep(composition.interval_seconds + composition.jitter())
    except Drained:
        composition.report(f"worker: {composition.identity} drained")
        return 0


__all__ = [
    "CLEANUP_ALLOWANCE",
    "DEFAULT_HEARTBEAT_PATH",
    "DEFAULT_INTERVAL_SECONDS",
    "HEARTBEAT_FILE",
    "IDLE_INTERVALS",
    "SERVICE_PREFIX",
    "TERMINATE_GRACE_SECONDS",
    "ChildCommand",
    "ChildLost",
    "ChildOutcome",
    "ChildProcess",
    "Drained",
    "Heartbeat",
    "ServiceComposition",
    "Spawn",
    "TickReport",
    "close_lost",
    "concerns",
    "decode_ending_line",
    "end_child",
    "ending_line",
    "install_stop_handlers",
    "serve",
    "service_identity",
    "spawn_child",
    "start_pass",
    "supervise",
    "tick",
    "work_due",
    "worker_healthy",
]
