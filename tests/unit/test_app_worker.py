"""The worker service over the in-memory stores: the pure selection of the one attempt due
(the launcher's WORK and nothing else), the tick (the pass first, one child, none when
nothing is due), the supervisor over a fake child (the ending read, the wall's terminate,
grace, kill and reap in order, a child gone without a line, the drain inside the wait) and
over a real child program through the real spawn (the pipe, the exit code, the kill of a
child that ignores its terminate), the closure of a lost attempt in the same tick (ended
as unrecovered, open as fenced, a review window kept), the drain (nothing closed, exit 0),
the start pass (a dead service's holder closed by the rule, the review window and the
operator's holder untouched), and the heartbeat's two states behind the healthcheck.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from leaveimpact.agent.commands import WorkRequest
from leaveimpact.agent.log_events import Abandoned, SegmentEnded, WorkerStamp
from leaveimpact.agent.log_store import LogStoreUnavailable, SlotHolder
from leaveimpact.agent.log_transition import Appended
from leaveimpact.agent.worker import WorkerEnding, WorkerEndingKind
from leaveimpact.app.sweeper import (
    CloseUnrecovered,
    CloseWait,
    FenceAndClose,
    SweepLog,
    SweepSnapshot,
    snapshot_of,
)
from leaveimpact.app.worker import (
    CLEANUP_ALLOWANCE,
    IDLE_INTERVALS,
    ChildLost,
    ChildProcess,
    Drained,
    Heartbeat,
    ServiceComposition,
    close_lost,
    ending_line,
    serve,
    service_identity,
    spawn_child,
    start_pass,
    supervise,
    tick,
    work_due,
    worker_healthy,
)
from tests.unit import format_fixtures as cases
from tests.unit.test_app_sweeper import (
    ADMITTED,
    RULES,
    WALL,
    Recording,
    admission_only,
    approval_delivered,
    awaiting,
    closed_completed,
    composition,
    run_of,
    running,
    seeded,
    stopped,
    stores,
)

IDENTITY = service_identity(ADMITTED, "a" * 32)
DEAD = service_identity(ADMITTED - timedelta(hours=1), "b" * 32)
NOW = ADMITTED + timedelta(minutes=1)
CHILD_PROGRAM = Path(__file__).with_name("worker_child_program.py")


# --- the fakes -----------------------------------------------------------------------------


@dataclass
class FakeChild:
    """A child as the supervisor sees it, scripted: ``communicate`` answers with the stdout
    given, raises the timeout (the child still running at the wall), or raises ``Drained``
    (the signal landing inside the wait); ``terminate`` ends it unless it ignores the
    signal, in which case only ``kill`` does; ``wait_raises`` is the signal landing inside
    the grace. ``log`` and ``request`` let the script end
    the segment as a real child's stop handler would, before the exit."""

    stdout: str | type[BaseException] = ""
    ignores_terminate: bool = False
    exit_code: int = 0
    on_terminate: Any = None
    on_communicate: Any = None
    wait_raises: type[BaseException] | None = None
    returncode: int | None = None
    calls: list[str] = field(default_factory=list[str])

    def communicate(self, *, timeout: float | None = None) -> tuple[Any, Any]:
        self.calls.append(f"communicate({timeout})")
        if self.returncode is not None:
            return "", None
        if self.on_communicate is not None:
            self.on_communicate()
        if self.stdout is subprocess.TimeoutExpired:
            raise subprocess.TimeoutExpired("fake child", timeout or 0)
        if isinstance(self.stdout, type):
            raise self.stdout(0)
        self.returncode = self.exit_code
        return self.stdout, None

    def terminate(self) -> None:
        self.calls.append("terminate")
        if self.on_terminate is not None:
            self.on_terminate()
        if not self.ignores_terminate:
            self.returncode = -15

    def kill(self) -> None:
        self.calls.append("kill")
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.calls.append(f"wait({timeout})")
        if self.wait_raises is not None:
            raise self.wait_raises(0)
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake child", timeout or 0)
        return self.returncode


@dataclass
class Spawner:
    """The spawn as a fake: the argv asked for, the children handed out in order."""

    children: list[FakeChild] = field(default_factory=list[FakeChild])
    spawned: list[Sequence[str]] = field(default_factory=list[Sequence[str]])

    def __call__(self, argv: Sequence[str]) -> ChildProcess:
        self.spawned.append(tuple(argv))
        return self.children.pop(0)


def ending(request: WorkRequest, kind: WorkerEndingKind = WorkerEndingKind.CLOSED) -> WorkerEnding:
    return WorkerEnding(kind, request.run_id, request.attempt, 1, kind.value)


def ends_segment(log: SweepLog, request: WorkRequest) -> Any:
    """What a real child's stop handler leaves: the claim taken and the segment ended."""

    def end() -> None:
        claimed = log.claim(
            request.run_id,
            request.attempt,
            harness=cases.REVISION,
            nonce=request.nonce,
            launch=request.launch,
            rules=RULES,
        )
        assert isinstance(claimed, Appended), claimed
        ended = log.append(
            request.run_id,
            request.attempt,
            WorkerStamp(claimed.state.generation, len(claimed.state.segments), 1_000),
            SegmentEnded(),
            rules=RULES,
        )
        assert isinstance(ended, Appended), ended

    return end


def claims_only(log: SweepLog, request: WorkRequest) -> Any:
    """What a child killed mid-write leaves: the claim taken and the segment open."""

    def claim() -> None:
        claimed = log.claim(
            request.run_id,
            request.attempt,
            harness=cases.REVISION,
            nonce=request.nonce,
            launch=request.launch,
            rules=RULES,
        )
        assert isinstance(claimed, Appended), claimed

    return claim


def argv_of(request: WorkRequest) -> list[str]:
    return ["child", request.run_id, str(request.attempt), request.nonce, request.launch]


def service(
    recording: Recording,
    spawn: Spawner,
    *,
    heartbeat: Path | None = None,
    lines: list[str] | None = None,
    sleep: list[float] | None = None,
    identity: str = IDENTITY,
) -> ServiceComposition:
    sleeps: list[float] = [] if sleep is None else sleep
    reported: list[str] = [] if lines is None else lines

    def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            raise Drained(0)

    return ServiceComposition(
        composition(recording, launch=identity),
        argv_of,
        lambda: NOW,
        spawn=spawn,
        heartbeat=heartbeat,
        terminate_grace_seconds=0.2,
        sleep=record_sleep,
        jitter=lambda: 0.0,
        report=reported.append,
        nonces=iter(f"nonce-work-{n}" for n in range(1, 100)).__next__,
    )


def snapshot_now(log: SweepLog, rows: object, recording: Recording) -> SweepSnapshot:
    return snapshot_of(log, rows, composition(recording))  # type: ignore[arg-type]


FIRST = WorkRequest(run_of(1), 1, "nonce-work-1", IDENTITY)


# --- the selection -----------------------------------------------------------------------


def test_the_attempt_due_is_the_oldest_first_claim_or_resumption_on_this_commit() -> None:
    """Never claimed: due. The approval delivered after the segment's end: due (a
    resumption). An outstanding request, a cleanly ended segment with nothing outstanding
    (a recovery), another commit's attempt with its approval delivered, a recorded stop
    and a closed one: never. Two due: the first in the snapshot's admission order."""
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    seeded(log, rows, 1, awaiting())
    seeded(log, rows, 2, running())
    ended = log.append(run_of(2), 1, WorkerStamp(1, 1, 2_000), SegmentEnded(), rules=RULES)
    assert isinstance(ended, Appended)
    approval_delivered(log, rows, 3, "c" * 40)
    seeded(log, rows, 4, closed_completed())
    seeded(log, rows, 5, stopped())
    assert work_due(snapshot_now(log, rows, recording), harness_commit=cases.COMMIT) is None
    approval_delivered(log, rows, 6)
    due = work_due(snapshot_now(log, rows, recording), harness_commit=cases.COMMIT)
    assert due is not None and due.run_id == run_of(6)
    seeded(log, rows, 7, admission_only())
    taken = snapshot_now(log, rows, recording)
    candidates = [each for each in taken.attempts if each.run_id in (run_of(6), run_of(7))]
    assert work_due(taken, harness_commit=cases.COMMIT) == candidates[0]


# --- the tick ----------------------------------------------------------------------------


def test_a_tick_runs_the_pass_then_spawns_the_child_for_the_one_attempt_due() -> None:
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    spawn = Spawner([FakeChild(ending_line(ending(FIRST)))])
    lines: list[str] = []
    seeded(log, rows, 1, admission_only())
    seeded(log, rows, 2, awaiting())
    report = tick(log, rows, service(recording, spawn, lines=lines))
    assert report.worked is not None and report.worked.kind is WorkerEndingKind.CLOSED
    assert report.lost is None and report.closed == ()
    assert spawn.spawned == [tuple(argv_of(FIRST))]
    assert spawn.children == [] and lines[-2] == f"work: run {run_of(1)} attempt 1: claiming"
    assert lines[-1].startswith(f"work: run {run_of(1)} attempt 1: ending=closed")


def test_a_tick_with_nothing_due_spawns_nothing_and_still_runs_the_pass() -> None:
    log, rows, clock = stores(ADMITTED)
    recording, spawn = Recording(), Spawner()
    seeded(log, rows, 1, awaiting())
    clock.at = awaiting()[7].timestamp + timedelta(days=1)
    report = tick(log, rows, service(recording, spawn))
    assert report.worked is None and spawn.spawned == []
    assert [type(outcome.action) for outcome in report.swept] == [CloseWait]


# --- the supervisor over a fake child ------------------------------------------------------


def test_the_supervisor_reads_the_ending_off_the_childs_last_line() -> None:
    child = FakeChild("a library's chatter\n" + ending_line(ending(FIRST)) + "\n")
    assert supervise(child, wall=5.0, grace=0.2) == ending(FIRST)
    assert child.calls == ["communicate(5.0)"]


def test_past_the_wall_the_child_is_terminated_waited_for_and_reaped_in_order() -> None:
    child = FakeChild(subprocess.TimeoutExpired)
    outcome = supervise(child, wall=5.0, grace=0.2)
    assert outcome == ChildLost(True, -15, "terminated at the wall of 5 seconds")
    assert child.calls == ["communicate(5.0)", "terminate", "wait(0.2)", "communicate(None)"]


def test_a_child_that_ignores_its_terminate_is_killed_after_the_grace() -> None:
    child = FakeChild(subprocess.TimeoutExpired, ignores_terminate=True)
    outcome = supervise(child, wall=5.0, grace=0.2)
    assert outcome == ChildLost(True, -9, "terminated at the wall of 5 seconds")
    assert child.calls == [
        "communicate(5.0)",
        "terminate",
        "wait(0.2)",
        "kill",
        "communicate(None)",
    ]


def test_a_child_gone_without_an_ending_line_is_lost_with_its_exit_code() -> None:
    child = FakeChild("leaveimpact.app: refused: no such run\n", exit_code=1)
    assert supervise(child, wall=5.0, grace=0.2) == ChildLost(
        False, 1, "exited without an ending line"
    )
    assert supervise(FakeChild("", exit_code=0), wall=5.0, grace=0.2) == ChildLost(
        False, 0, "exited without an ending line"
    )


def test_the_drain_inside_the_wait_ends_the_child_the_same_way_and_propagates() -> None:
    child = FakeChild(Drained)
    with pytest.raises(Drained):
        supervise(child, wall=5.0, grace=0.2)
    assert child.calls == ["communicate(5.0)", "terminate", "wait(0.2)", "communicate(None)"]


def test_the_drain_inside_the_grace_kills_the_child_reaps_it_and_propagates() -> None:
    """The wall passed and the terminate's grace is running when the stop signal lands
    (the probe's rerun: the wall and the drain a tenth of a second apart): the child is
    killed and reaped before the drain goes on, never left alive behind the service."""
    child = FakeChild(subprocess.TimeoutExpired, ignores_terminate=True, wait_raises=Drained)
    lines: list[str] = []
    with pytest.raises(Drained):
        supervise(child, wall=5.0, grace=0.2, report=lines.append)
    assert child.calls == [
        "communicate(5.0)",
        "terminate",
        "wait(0.2)",
        "kill",
        "communicate(None)",
    ]
    assert child.returncode == -9
    assert lines[-1] == "drained inside the grace; the child is killed"


# --- the supervisor over a real child -----------------------------------------------------


def program(*arguments: str) -> list[str]:
    return [sys.executable, str(CHILD_PROGRAM), *arguments]


def test_the_real_spawn_reads_the_ending_through_the_pipe_and_reaps_the_child() -> None:
    child = spawn_child(program("ending", ending_line(ending(FIRST))))
    assert supervise(child, wall=20.0, grace=1.0) == ending(FIRST)
    assert child.returncode == 0


def test_the_real_spawn_reports_a_child_that_died_with_its_code() -> None:
    child = spawn_child(program("die", "3"))
    assert supervise(child, wall=20.0, grace=1.0) == ChildLost(
        False, 3, "exited without an ending line"
    )


def test_the_real_spawn_ends_a_child_that_outlives_the_wall() -> None:
    """A child that sleeps past the wall and ignores its terminate where the platform lets
    it (POSIX; on Windows a terminate is a kill) is gone when the supervisor returns, its
    return code the signal's or the kill's."""
    child = spawn_child(program("hang"))
    outcome = supervise(child, wall=0.5, grace=0.5)
    assert isinstance(outcome, ChildLost) and outcome.at_wall
    assert child.returncode is not None and child.returncode != 0


# --- the closure of a lost attempt --------------------------------------------------------


def test_a_child_lost_at_the_wall_with_its_segment_ended_is_closed_as_unrecovered_at_once() -> None:
    """The child's stop handler ended the segment on the terminate; the tick's closure
    finds a clean end whose next claim would be a recovery and closes it by the rule in
    the same tick, the next pass finding nothing to do."""
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    child = FakeChild(subprocess.TimeoutExpired, on_terminate=ends_segment(log, FIRST))
    spawn = Spawner([child])
    lines: list[str] = []
    seeded(log, rows, 1, admission_only())
    report = tick(log, rows, service(recording, spawn, lines=lines))
    assert report.worked is None
    assert report.lost == ChildLost(True, -15, "terminated at the wall of 600 seconds")
    assert [outcome.action for outcome in report.closed] == [CloseUnrecovered(run_of(1), 1, 1)]
    assert all(outcome.carried for outcome in report.closed)
    closed = log.load(run_of(1), 1, rules=RULES)
    assert closed.closed is not None and isinstance(closed.closed.event, Abandoned)
    assert any(
        "the child terminated at the wall of 600 seconds (exit code -15)" in line for line in lines
    )
    assert f"work: run {run_of(1)} attempt 1: the wall of 600 seconds passed" in lines
    assert f"work: run {run_of(1)} attempt 1: the child is terminated" in lines
    assert not any("killed" in line for line in lines)
    following = tick(log, rows, service(recording, Spawner()))
    assert [type(outcome.action).__name__ for outcome in following.swept] == [
        "Publish",
        "WriteInventory",
    ], "the next pass publishes the closed attempt and closes nothing"


def test_a_child_killed_with_its_segment_open_is_fenced_and_closed_at_once() -> None:
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    child = FakeChild(
        subprocess.TimeoutExpired, ignores_terminate=True, on_terminate=claims_only(log, FIRST)
    )
    seeded(log, rows, 1, admission_only())
    lines: list[str] = []
    report = tick(log, rows, service(recording, Spawner([child]), lines=lines))
    assert report.lost == ChildLost(True, -9, "terminated at the wall of 600 seconds")
    assert any(
        line.endswith("did not end within the grace of 0.2 seconds; killed") for line in lines
    )
    assert [outcome.action for outcome in report.closed] == [FenceAndClose(run_of(1), 1, 1)]
    assert all(outcome.carried for outcome in report.closed)
    assert log.load(run_of(1), 1, rules=RULES).closed is not None


def test_a_child_that_died_without_a_line_is_closed_by_the_same_rule() -> None:
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    seeded(log, rows, 1, admission_only())
    # The child claimed and ended its segment, then died before its line.
    child = FakeChild(
        "Traceback (most recent call last):\n", exit_code=1, on_communicate=ends_segment(log, FIRST)
    )
    report = tick(log, rows, service(recording, Spawner([child])))
    assert report.lost == ChildLost(False, 1, "exited without an ending line")
    assert [outcome.action for outcome in report.closed] == [CloseUnrecovered(run_of(1), 1, 1)]


def test_a_child_lost_before_its_claim_leaves_the_attempt_due_again_and_touches_no_other() -> None:
    """The child died before claiming: the rule under a zero wall closes an unclaimed
    attempt only after the wait, so the attempt stays due for the next tick, and the other
    attempt in the snapshot (its approval outstanding) is not touched by the closure."""
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    lines: list[str] = []
    seeded(log, rows, 1, awaiting())
    seeded(log, rows, 2, admission_only())
    report = tick(log, rows, service(recording, Spawner([FakeChild("", exit_code=0)]), lines=lines))
    assert report.lost == ChildLost(False, 0, "exited without an ending line")
    assert report.closed == ()
    assert lines[-1] == (
        f"work: run {run_of(2)} attempt 1: the rule keeps the attempt open; the next pass decides"
    )
    assert log.load(run_of(1), 1, rules=RULES).closed is None
    assert log.load(run_of(2), 1, rules=RULES).closed is None
    due = work_due(snapshot_now(log, rows, recording), harness_commit=cases.COMMIT)
    assert due is not None and due.run_id == run_of(2)


def test_the_closure_of_a_lost_child_keeps_an_outstanding_review_window() -> None:
    """The child requested the approval, ended its segment and was lost: the rule under a
    zero wall keeps the request to its deadline, the closure performs nothing and says so."""
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    lines: list[str] = []
    seeded(log, rows, 1, awaiting())
    report = close_lost(log, rows, service(recording, Spawner(), lines=lines), FIRST)
    assert report == ()
    assert lines == [
        f"work: run {run_of(1)} attempt 1: the rule keeps the attempt open; the next pass decides"
    ]
    assert log.load(run_of(1), 1, rules=RULES).closed is None


def test_the_closure_of_a_lost_child_leaves_a_takeover_of_its_attempt_alone() -> None:
    """The child claimed and was killed; an operator took the attempt over before the
    supervisor's snapshot (the external read's first finding): the zero wall's fence names
    the operator's generation, which is not the child's claim, so nothing is closed."""
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    lines: list[str] = []
    seeded(log, rows, 1, admission_only())

    def claim_then_takeover() -> None:
        claims_only(log, FIRST)()
        taken = log.claim(
            run_of(1),
            1,
            harness=cases.REVISION,
            nonce="nonce-op",
            launch="launch-lifecycle-7",
            rules=RULES,
        )
        assert isinstance(taken, Appended) and taken.state.generation == 2

    child = FakeChild(
        subprocess.TimeoutExpired, ignores_terminate=True, on_terminate=claim_then_takeover
    )
    report = tick(log, rows, service(recording, Spawner([child]), lines=lines))
    assert report.lost is not None and report.closed == ()
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.closed is None and state.generation == 2
    assert lines[-1].endswith("the rule keeps the attempt open; the next pass decides")


def test_an_orphan_admission_without_its_rows_is_never_due() -> None:
    """The start that lost its app rows (a documented crash state): nobody can watch the
    attempt, so no child is spawned for it and the sweeper's wait cancels it (the external
    read's second finding: a claimed orphan with an open segment had no closure)."""
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    seeded(log, rows, 1, admission_only(), row=False)
    assert work_due(snapshot_now(log, rows, recording), harness_commit=cases.COMMIT) is None
    spawn = Spawner()
    assert tick(log, rows, service(recording, spawn)).worked is None and spawn.spawned == []


# --- the drain --------------------------------------------------------------------------


def test_the_drain_inside_the_wait_ends_the_child_and_the_loop_exits_0_closing_nothing() -> None:
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    child = FakeChild(Drained, on_terminate=ends_segment(log, FIRST))
    lines: list[str] = []
    seeded(log, rows, 1, admission_only())
    assert serve(log, rows, service(recording, Spawner([child]), lines=lines)) == 0
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.closed is None
    assert state.current_segment is not None and state.current_segment.ended
    assert child.calls[-1] == "communicate(None)"
    assert lines[-1] == f"worker: {IDENTITY} drained" and lines[0] == f"worker: {IDENTITY} starting"


def test_a_store_that_does_not_answer_is_retried_next_tick_with_the_heartbeat_left_stale(
    tmp_path: Path,
) -> None:
    """The probe's blocked-store cases: the snapshot's read raised the store's
    unavailability out of the tick and the first build's loop died on it. The loop reports
    and retries; the heartbeat is written only after a pass has read the stores, so three
    intervals later the healthcheck reads the outage."""
    log, rows, _ = stores(ADMITTED)
    beat = tmp_path / "heartbeat.json"
    recording = Recording()
    lines: list[str] = []
    sleeps: list[float] = []
    outages = iter([False, True])  # the start pass answers; the first tick's read does not
    original = log.now

    def now_or_outage() -> datetime:
        if next(outages, False):
            raise LogStoreUnavailable("statement failed: QueryCanceled")
        return original()

    log.now = now_or_outage  # type: ignore[method-assign]
    composition = service(recording, Spawner(), heartbeat=beat, lines=lines, sleep=sleeps)
    assert serve(log, rows, composition) == 0
    assert any("a store did not answer (statement failed: QueryCanceled)" in line for line in lines)
    assert Heartbeat.read(beat) is not None, "the second tick's pass wrote it"
    assert len(sleeps) == 2, "the outage's tick slept and the next tick ran"


def test_the_drain_between_ticks_exits_0_too() -> None:
    log, rows, _ = stores(ADMITTED)
    recording, spawn = Recording(), Spawner()
    sleeps: list[float] = []
    assert serve(log, rows, service(recording, spawn, sleep=sleeps)) == 0
    assert len(sleeps) == 2 and spawn.spawned == []


# --- the start pass -----------------------------------------------------------------------


def test_the_start_pass_closes_a_dead_services_open_segment_and_keeps_a_review_window() -> None:
    """The slot held by another identity of the service's kind: the holder's open segment
    is fenced and closed at once, not at the wall; an outstanding request on a dead
    service's attempt is kept to its deadline; the same identity, or the lifecycle's,
    runs a normal pass and fences nothing inside the wall."""
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    lines: list[str] = []
    seeded(log, rows, 1, running())
    log.slot = SlotHolder(run_of(1), 1, 1, DEAD, ADMITTED - timedelta(seconds=1))
    report = start_pass(log, rows, service(recording, Spawner(), lines=lines))
    assert [outcome.action for outcome in report] == [FenceAndClose(run_of(1), 1, 1)]
    assert report[0].carried and log.load(run_of(1), 1, rules=RULES).closed is not None
    assert lines[0].startswith(f"start: the slot is held by a dead service {DEAD}")
    log, rows, _ = stores(ADMITTED)
    seeded(log, rows, 2, awaiting()[:8])  # requested, the segment still open: the worker died
    log.slot = SlotHolder(run_of(2), 1, 1, DEAD, ADMITTED - timedelta(seconds=1))
    report = start_pass(log, rows, service(Recording(), Spawner()))
    assert report == () and log.load(run_of(2), 1, rules=RULES).closed is None
    for holder in (IDENTITY, "launch-lifecycle-7"):
        log, rows, _ = stores(ADMITTED)
        seeded(log, rows, 3, running())
        log.slot = SlotHolder(run_of(3), 1, 1, holder, ADMITTED - timedelta(seconds=1))
        assert start_pass(log, rows, service(Recording(), Spawner())) == ()
        assert log.load(run_of(3), 1, rules=RULES).closed is None


def test_the_start_pass_leaves_a_takeover_between_its_slot_read_and_its_snapshot_alone() -> None:
    """The dead holder is read at generation 1; an operator takes the attempt over before
    the snapshot (the external read's first finding): the zero wall's fence names
    generation 2, which is not the holder that was read, and the operator's attempt stays
    open."""
    log, rows, _ = stores(ADMITTED)
    recording = Recording()
    seeded(log, rows, 1, running())
    log.slot = SlotHolder(run_of(1), 1, 1, DEAD, ADMITTED - timedelta(seconds=1))
    original = log.execution_slot
    reads: list[int] = []

    def slot_then_takeover() -> SlotHolder | None:
        holder = original()
        reads.append(1)
        if len(reads) == 1:
            taken = log.claim(
                run_of(1),
                1,
                harness=cases.REVISION,
                nonce="nonce-op",
                launch="launch-lifecycle-7",
                rules=RULES,
            )
            assert isinstance(taken, Appended) and taken.state.generation == 2
        return holder

    log.execution_slot = slot_then_takeover  # type: ignore[method-assign]
    report = start_pass(log, rows, service(recording, Spawner()))
    assert report == ()
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.closed is None and state.generation == 2


# --- the heartbeat ------------------------------------------------------------------------


def test_the_heartbeat_carries_a_deadline_idle_per_tick_and_working_at_the_claim(
    tmp_path: Path,
) -> None:
    log, rows, _ = stores(ADMITTED)
    beat = tmp_path / "heartbeat.json"
    recording = Recording()
    tick(log, rows, service(recording, Spawner(), heartbeat=beat))
    idle = Heartbeat.read(beat)
    assert idle is not None
    assert idle == Heartbeat("idle", NOW + timedelta(seconds=2.0 * IDLE_INTERVALS))
    assert worker_healthy(beat, NOW) and not worker_healthy(beat, idle.deadline)
    seeded(log, rows, 1, admission_only())
    spawn = Spawner([FakeChild(ending_line(ending(FIRST)))])
    tick(log, rows, service(recording, spawn, heartbeat=beat))
    working = Heartbeat.read(beat)
    assert working is not None
    assert working == Heartbeat("working", NOW + WALL + CLEANUP_ALLOWANCE)
    assert worker_healthy(beat, NOW + WALL) and not worker_healthy(beat, working.deadline)
    assert not worker_healthy(tmp_path / "absent.json", NOW)
    beat.write_text("{not json", encoding="utf-8")
    assert not worker_healthy(beat, NOW)


@pytest.mark.parametrize("token", ["a" * 32, "0f" * 16])
def test_the_service_identity_carries_the_prefix_the_instant_and_the_token(token: str) -> None:
    identity = service_identity(datetime(2026, 10, 28, 9, 5, 7, tzinfo=UTC), token)
    assert identity == f"worker-20261028T090507Z-{token}"
