"""The narration stream over the real producer on the real stores (the narration step's
acceptance): a stream opened over an admitted attempt before any worker claims it, the
rules-only run then worked by the real worker from another thread and another connection,
its lines arriving on the stream as the log records them, the approval request observed
while the worker is held at the approval and the attempt is still open, and the closing
frame ending the stream after the worker is let go. Observing a line before the worker may
close is what makes this the live case; every line read after completion would prove only
the replay. The lines are the narration's over the closed log, read back through a session
of its own, so the stream and the timeline agree."""

from __future__ import annotations

import threading
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from leaveimpact.agent.log_events import Producer
from leaveimpact.agent.log_transition import AttemptState
from leaveimpact.agent.worker import WorkerEnding, WorkerEndingKind
from leaveimpact.app.main import Services, create_app
from leaveimpact.app.narration import narration
from leaveimpact.app.public import PublicationDraft, PublicId
from leaveimpact.app.store import Published
from leaveimpact.app.stream import CLOSED_EVENT, Pacing
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.integration.log_store_support import Rig, rig
from tests.integration.test_app_surface import app_store
from tests.integration.worker_rig import (
    ATTEMPT,
    RULES,
    RUN,
    WorkRequest,
    admitted,
    composition,
    saver_on,
    work,
)
from tests.unit import worker_support as support
from tests.unit.publishable_fixture import CONFIGURATION
from tests.unit.test_app_stream import frames_of
from tests.unit.throwaway_world import loaded_world

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

CODE = "b" * 40
SLUG = "live-real"
FAST = Pacing(tick_seconds=0.05, heartbeat_seconds=30.0, bound=2)


class GatedApproval:
    """The automatic policy, held at the approval until the test lets it go: ``reached`` is
    set when the worker asks, and the worker waits on ``proceed``."""

    identity = "policy:automatic"

    def __init__(self) -> None:
        self.reached = threading.Event()
        self.proceed = threading.Event()

    def approver(self, state: AttemptState) -> Producer | None:
        self.reached.set()
        assert self.proceed.wait(timeout=60), "the test lets the worker go"
        return Producer(self.identity)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def test_a_stream_over_a_live_run_delivers_its_lines_before_the_worker_closes_it(
    rig: Rig, world: SealedWorld
) -> None:
    named = support.SCRIPTS["rules-only"]
    log, inputs = admitted(rig, world, inputs_for=named.inputs)
    context = inputs.context
    store = app_store(rig)
    store.ensure_schema()
    written = store.publish(
        PublicationDraft(
            PublicId(SLUG),
            RUN,
            ATTEMPT,
            context.world_version,
            context.scenario_id,
            "A run followed live",
            "operator:test",
        )
    )
    assert isinstance(written, Published)
    services = Services(
        code_version=CODE,
        configuration=replace(CONFIGURATION, served_world_version=context.world_version),
        ready_versions=lambda: frozenset({context.world_version}),
        app_schema=store.schema_supported,
        rows=store,
        log_sessions=rig.store,
        rules=RULES,
    )
    approval = GatedApproval()
    composed = composition(inputs, world, saver_on(rig), approval=approval, script=named)
    endings: list[WorkerEnding] = []
    worker = threading.Thread(
        target=lambda: endings.append(
            work(WorkRequest(RUN, ATTEMPT, "nonce-1", "launch-1"), log, composed)
        )
    )
    client = TestClient(create_app(services, FAST))
    with client.stream("GET", f"/replays/{SLUG}/events") as response:
        assert response.status_code == 200
        frames = frames_of(response.iter_lines())
        first = next(frames)
        assert first["data"]["position"] == 1 and "run admitted" in first["data"]["text"]
        worker.start()
        assert approval.reached.wait(timeout=120), "the worker reaches the approval"
        seen = [first]
        while seen[-1]["data"]["kind"] != "approval_requested":
            seen.append(next(frames))
        # The worker is held at the approval: the attempt is open, and the stream has
        # delivered every line up to the request while it is.
        observer = rig.store()
        try:
            held = observer.load(RUN, ATTEMPT, rules=RULES)
        finally:
            observer.close()
        assert held.closed is None
        assert "awaits the decision" in seen[-1]["data"]["text"]
        assert [frame["data"]["position"] for frame in seen] == list(range(1, len(seen) + 1))
        approval.proceed.set()
        worker.join(timeout=120)
        rest = list(frames)
    assert endings == [WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")]
    assert rest[-1]["event"] == CLOSED_EVENT and rest[-1]["data"]["status"] == "completed"
    reader = rig.store()
    try:
        closed = reader.load(RUN, ATTEMPT, rules=RULES)
    finally:
        reader.close()
    lines = narration(closed, RULES)
    received = [*seen, *rest]
    assert [frame["data"]["position"] for frame in received] == [line.position for line in lines]
    assert [frame["data"]["text"] for frame in received] == [line.text for line in lines]
    assert RUN not in client.get(f"/replays/{SLUG}/timeline").text
