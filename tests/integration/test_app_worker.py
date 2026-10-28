"""The worker service's tick over the real stores: a public attempt admitted and never
claimed is the one due; the child, a fake process whose work claims through the real log
store under the service's identity, takes the slot and ends its segment; the next tick
finds a recovery the sweeper closes as unrecovered, the slot released by ownership; a
child lost at the wall with its segment open is fenced and closed through the real slot in
the same tick; the start pass of a replacement service fences what a dead service of the
same kind left open."""

from __future__ import annotations

import subprocess
from datetime import timedelta

import pytest

from leaveimpact.agent.commands import WorkRequest
from leaveimpact.agent.log_events import Abandoned, SegmentEnded, SegmentStarted, WorkerStamp
from leaveimpact.agent.log_store import LogStore
from leaveimpact.agent.log_transition import Appended
from leaveimpact.agent.worker import WorkerEnding, WorkerEndingKind
from leaveimpact.app.sweeper import CloseUnrecovered, FenceAndClose, Publish
from leaveimpact.app.worker import (
    ChildLost,
    ServiceComposition,
    ending_line,
    service_identity,
    start_pass,
    tick,
)
from tests.integration.log_store_support import Rig, rig
from tests.integration.test_app_sweeper import composition, prepared, replayed
from tests.unit import format_fixtures as cases
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.test_app_sweeper import RULES, admission_only, run_of, running
from tests.unit.test_app_worker import FakeChild, Spawner, argv_of

_ = rig  # the fixture, imported for pytest to find

pytestmark = pytest.mark.integration

IDENTITY = service_identity(cases.ADMITTED, "a" * 32)
DEAD = service_identity(cases.ADMITTED - timedelta(hours=1), "b" * 32)
FIRST = WorkRequest(run_of(1), 1, "nonce-work-1", IDENTITY)


def claim(log: LogStore, request: WorkRequest) -> Appended:
    claimed = log.claim(
        request.run_id,
        request.attempt,
        harness=cases.REVISION,
        nonce=request.nonce,
        launch=request.launch,
        rules=RULES,
    )
    assert isinstance(claimed, Appended), claimed
    held = log.execution_slot()
    assert held is not None and (held.run_id, held.launch) == (request.run_id, request.launch)
    return claimed


def claim_and_end(log: LogStore, request: WorkRequest) -> WorkerEnding:
    """What a child does through the real store before it prints: the claim, the slot
    taken, the segment ended cleanly, as a drained worker leaves an attempt."""
    claimed = claim(log, request)
    ended = log.append(
        request.run_id,
        request.attempt,
        WorkerStamp(claimed.state.generation, len(claimed.state.segments), 1_000),
        SegmentEnded(),
        rules=RULES,
    )
    assert isinstance(ended, Appended), ended
    return WorkerEnding(
        WorkerEndingKind.SEGMENT_ENDED, request.run_id, request.attempt, 1, "ended by the test"
    )


def service(
    log: LogStore, identity: str, lines: list[str], *children: FakeChild
) -> ServiceComposition:
    return ServiceComposition(
        composition(log, InMemoryObjectStore(), launch=identity),
        argv_of,
        lambda: cases.ADMITTED,
        spawn=Spawner(list(children)),
        heartbeat=None,
        terminate_grace_seconds=0.2,
        report=lines.append,
        nonces=iter(f"nonce-work-{n}" for n in range(1, 100)).__next__,
    )


def test_a_tick_works_the_admitted_attempt_through_the_real_slot_and_the_next_closes_it(
    rig: Rig,
) -> None:
    log, store = prepared(rig)
    replayed(log, store, 1, admission_only())
    lines: list[str] = []
    ending = claim_and_end  # the child's work, run from inside the fake's communicate
    child = FakeChild(
        on_communicate=lambda: setattr(child, "stdout", ending_line(ending(log, FIRST)))
    )
    first = tick(log, store, service(log, IDENTITY, lines, child))
    assert first.worked is not None and first.worked.kind is WorkerEndingKind.SEGMENT_ENDED
    assert log.execution_slot() is None, "released by ownership at the segment's end"
    state = log.load(run_of(1), 1, rules=RULES)
    assert state.current_segment is not None and state.current_segment.ended
    claims = [each.event for each in state.events if isinstance(each.event, SegmentStarted)]
    assert [each.launch for each in claims] == [IDENTITY]
    second = tick(log, store, service(log, IDENTITY, lines))
    assert second.worked is None
    assert [outcome.action for outcome in second.swept] == [CloseUnrecovered(run_of(1), 1, 1)]
    closed = log.load(run_of(1), 1, rules=RULES)
    assert closed.closed is not None and isinstance(closed.closed.event, Abandoned)


def test_a_child_lost_at_the_wall_with_its_segment_open_is_fenced_through_the_real_slot(
    rig: Rig,
) -> None:
    """The child claimed and was killed mid-work: the slot is held under the service's own
    identity, the rule under a zero wall fences that generation and closes the attempt in
    the same tick, and the slot is free for the next."""
    log, store = prepared(rig)
    replayed(log, store, 1, admission_only())
    lines: list[str] = []
    child = FakeChild(
        subprocess.TimeoutExpired,
        ignores_terminate=True,
        on_communicate=lambda: claim(log, FIRST),
    )
    report = tick(log, store, service(log, IDENTITY, lines, child))
    assert report.worked is None
    assert report.lost == ChildLost(True, -9, "terminated at the wall of 600 seconds")
    assert [outcome.action for outcome in report.closed] == [FenceAndClose(run_of(1), 1, 1)]
    assert all(outcome.carried for outcome in report.closed), report.closed
    assert log.execution_slot() is None
    closed = log.load(run_of(1), 1, rules=RULES)
    assert closed.closed is not None and isinstance(closed.closed.event, Abandoned)
    following = tick(log, store, service(log, IDENTITY, lines))
    assert any(isinstance(outcome.action, Publish) for outcome in following.swept)


def test_the_start_pass_fences_a_dead_services_holder_through_the_real_slot(rig: Rig) -> None:
    log, store = prepared(rig)
    replayed(log, store, 1, admission_only())
    claimed = log.claim(
        run_of(1), 1, harness=cases.REVISION, nonce="nonce-dead", launch=DEAD, rules=RULES
    )
    assert isinstance(claimed, Appended)
    held = log.execution_slot()
    assert held is not None and held.launch == DEAD
    lines: list[str] = []
    report = start_pass(log, store, service(log, IDENTITY, lines))
    assert [outcome.action for outcome in report] == [FenceAndClose(run_of(1), 1, 1)]
    assert report[0].carried, report[0].detail
    assert log.execution_slot() is None
    assert log.load(run_of(1), 1, rules=RULES).closed is not None
    assert lines[0].startswith(f"start: the slot is held by a dead service {DEAD}")
    # A holder that is not of the service's kind is left alone inside the wall.
    replayed(log, store, 2, running())
    later = start_pass(log, store, service(log, IDENTITY, lines))
    assert not any(getattr(outcome.action, "run_id", None) == run_of(2) for outcome in later)
    assert log.load(run_of(2), 1, rules=RULES).closed is None
