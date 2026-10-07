"""The worker over the real store and the PostgreSQL saver: the reference run, the fence
between two live workers, and a human approval across two processes.

The unit level shows the worker's behaviour over the in-memory log; this level shows the
same driver against the store it ships with (the event log step's ruling on placement and
acceptance, part 5: two-connection tests with barriers at named boundaries and no sleeps)
and the checkpoint saver on a connection of its own in the test's schema. The fencing
row's live half is here: a worker held inside its send is overtaken by a second worker on
another connection, and the log shows the first contributing nothing after the fence while
its checkpoints stay on its own generation's thread (the ruling on recovery, part 5).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from langgraph.checkpoint.postgres import PostgresSaver

from leaveimpact.agent.log_events import (
    Approved,
    DispatchIntent,
    EventKind,
    LoggedEvent,
    Producer,
    WorkerStamp,
    kind_of,
)
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import calls_of
from leaveimpact.agent.worker import (
    AutomaticApproval,
    HumanApproval,
    Worker,
    WorkerConfiguration,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.core import Approver, decode_export_bytes, export_bytes
from leaveimpact.core.run_parts_json import review_payload_digest
from leaveimpact.core.run_timing import elapsed_ms, evidenced_active_ms
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.integration.log_store_support import Rig, rig
from tests.integration.worker_rig import admitted, saver_on
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.log_store_memory import MemoryLog
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import loaded_world
from tests.unit.worker_support import ScriptedClient, ScriptedCounter, ScriptedTurns

pytestmark = pytest.mark.integration

RULES = histories.RULES
RUN, ATTEMPT = "run-12", 1
LEDGER = "ledger-worker"
PLENTY = 10**15
DEADLINE_SECONDS = 20.0

_ = rig  # the fixture, imported for pytest to find


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def worker_over(
    store: Any,
    inputs: Any,
    world: SealedWorld,
    saver: Any,
    *,
    turns: ScriptedTurns,
    client: ScriptedClient,
    approval: AutomaticApproval | HumanApproval | None = None,
) -> Worker:
    return Worker(
        store,
        WorkerConfiguration.of(inputs),
        cases.REVISION,
        "launch-1",
        RULES,
        turns,
        client,
        ScriptedCounter(),
        systems_holding(world).ports,
        approval if approval is not None else AutomaticApproval(),
        saver,
    )


def kinds(events: Sequence[LoggedEvent]) -> list[str]:
    return [kind_of(e.event).value for e in events]


def checkpoints_of(saver: PostgresSaver, thread: str) -> int:
    return sum(1 for _ in saver.list({"configurable": {"thread_id": thread}}))


# --- The reference run -----------------------------------------------------------------------


def test_the_reference_run_completes_on_the_real_store_and_agrees_with_the_memory_log(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = admitted(rig, world)
    context = world.context_of(world.scenarios[0])
    turns, client = support.two_call_script(context)
    saver = saver_on(rig)
    ending = worker_over(store, inputs, world, saver, turns=turns, client=client).work(
        RUN, ATTEMPT, nonce="nonce-1"
    )
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    events = store.events(RUN, ATTEMPT)
    assert kinds(events)[-5:] == [
        "finalization_entered",
        "approval_requested",
        "approved",
        "resumed",
        "completed",
    ]
    assert support.sends_of(client) == 2
    assert checkpoints_of(saver, f"{RUN}/{ATTEMPT}/1") > 0, "the cursor landed in the schema"
    state = store.load(RUN, ATTEMPT, rules=RULES)
    export = export_of(state)
    assert decode_export_bytes(export_bytes(export)) == export
    timing = export.record.timing
    active, elapsed = evidenced_active_ms(timing), elapsed_ms(timing)
    assert elapsed is not None and active >= 0
    # The same script over the in-memory log: the two logs agree on every settled event.
    memory = MemoryLog()
    memory.seed(support.admission(inputs))
    turns_m, client_m = support.two_call_script(context)
    from langgraph.checkpoint.memory import InMemorySaver

    worker_over(memory, inputs, world, InMemorySaver(), turns=turns_m, client=client_m).work(
        RUN, ATTEMPT, nonce="nonce-1"
    )
    assert support.settled(memory.events(RUN, ATTEMPT)) == support.settled(events)


# --- The fence between two live workers -----------------------------------------------------


class HeldClient(ScriptedClient):
    """A client whose first send waits at the wire until released: the request is in flight
    while another worker takes the attempt over."""

    def __init__(self, inner: ScriptedClient) -> None:
        super().__init__(inner.answers)
        self.in_flight = threading.Event()
        self.release = threading.Event()
        self.held_once = False

    def send(self, requested_profile: str, body: Any) -> Any:
        if not self.held_once:
            self.held_once = True
            self.in_flight.set()
            if not self.release.wait(DEADLINE_SECONDS):
                raise AssertionError("the held send was never released")
        return super().send(requested_profile, body)


def wait_until(predicate: Any) -> None:
    deadline = time.monotonic() + DEADLINE_SECONDS
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("the awaited state never arrived")


def test_a_worker_overtaken_inside_its_send_contributes_nothing_after_the_fence(
    rig: Rig, world: SealedWorld
) -> None:
    store_a, inputs = admitted(rig, world)
    store_b = rig.store()
    context = world.context_of(world.scenarios[0])
    turns_a, client_a = support.two_call_script(context)
    held = HeldClient(client_a)
    turns_b, client_b = support.two_call_script(context)
    saver_a, saver_b = saver_on(rig), saver_on(rig)
    first = worker_over(store_a, inputs, world, saver_a, turns=turns_a, client=held)
    # The second worker waits for a human at its approval, so the attempt is open when the
    # first worker's refusal is read and the fence is what the log shows, not a closure.
    second = worker_over(
        store_b, inputs, world, saver_b, turns=turns_b, client=client_b, approval=HumanApproval()
    )
    with ThreadPoolExecutor(1) as pool:
        running = pool.submit(first.work, RUN, ATTEMPT, nonce="nonce-a")
        assert held.in_flight.wait(DEADLINE_SECONDS), "the first worker never reached its send"
        wait_until(
            lambda: any(
                kind_of(e.event) is EventKind.DISPATCH_INTENT for e in store_b.events(RUN, ATTEMPT)
            )
        )
        ending_b = second.work(RUN, ATTEMPT, nonce="nonce-b")
        held.release.set()
        ending_a = running.result(DEADLINE_SECONDS)
    assert ending_b == WorkerEnding(
        WorkerEndingKind.AWAITING_APPROVAL, RUN, ATTEMPT, 2, "approval requested"
    )
    assert ending_a == WorkerEnding(WorkerEndingKind.FENCED, RUN, ATTEMPT, 1, "generation 2")
    events = store_b.events(RUN, ATTEMPT)
    takeover = next(
        i for i, e in enumerate(events) if kind_of(e.event) is EventKind.SEGMENT_STARTED and i > 1
    )
    after = events[takeover:]
    assert all(
        not isinstance(e.envelope, WorkerStamp) or e.envelope.generation == 2 for e in after
    ), "the fenced generation wrote nothing after the fence"
    state = store_b.load(RUN, ATTEMPT, rules=RULES)
    call = calls_of(state)[0]
    first_intent = call.intents[0].event
    assert isinstance(first_intent, DispatchIntent) and first_intent.number == 1
    assert 1 not in call.outcomes and 2 in call.outcomes, "the in-flight dispatch stays unresolved"
    assert support.sends_of(held) == 1 and support.sends_of(client_b) == 2
    assert checkpoints_of(saver_a, f"{RUN}/{ATTEMPT}/1") > 0
    assert checkpoints_of(saver_b, f"{RUN}/{ATTEMPT}/2") > 0
    assert checkpoints_of(saver_b, f"{RUN}/{ATTEMPT}/1") == checkpoints_of(
        saver_a, f"{RUN}/{ATTEMPT}/1"
    )


# --- A human approval across two processes -------------------------------------------------


def test_a_human_approval_across_two_workers_on_the_real_store(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = admitted(rig, world)
    context = world.context_of(world.scenarios[0])
    turns, client = support.two_call_script(context)
    first = worker_over(
        store, inputs, world, saver_on(rig), turns=turns, client=client, approval=HumanApproval()
    ).work(RUN, ATTEMPT, nonce="nonce-1")
    assert first.kind is WorkerEndingKind.AWAITING_APPROVAL
    state = store.load(RUN, ATTEMPT, rules=RULES)
    request = state.approval_requested
    assert request is not None
    digest = review_payload_digest(request.event.claims, request.event.composition)  # type: ignore[union-attr]
    store.append(
        RUN, ATTEMPT, Producer("approver:test"), Approved(Approver.HUMAN, digest), rules=RULES
    )
    sends = support.sends_of(client)
    second = worker_over(
        store, inputs, world, saver_on(rig), turns=turns, client=client, approval=HumanApproval()
    ).work(RUN, ATTEMPT, nonce="nonce-2")
    assert second == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 2, "completed")
    assert kinds(store.events(RUN, ATTEMPT))[-4:] == [
        "approved",
        "segment_started",
        "resumed",
        "completed",
    ]
    assert support.sends_of(client) == sends, "the replay sent nothing"
