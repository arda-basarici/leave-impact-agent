"""The four recovery cases the first live run's design read required before the live group,
each over the real store (the step's amendments to forks 1, 9, 10 and 12).

*A completion the transport reported uncertainly.* The launcher reads the attempt's state
before any re-send: a closed attempt reads as publish, and a work command re-sent to it
anyway claims nothing and writes nothing. *The human-waiting pause.* A worker under the human
policy ends its segment at the approval request; the state reads as wait, the reviewer reads
the frozen payload and delivers over its digest, the state reads as work, and the next work
command resumes to the closing. *The recorded stop with an open segment.* A worker that
reached its stopping failure and could not record the closing leaves the attempt open with
the stop in the log; the state reads as recover, and the terminal path closes it by that
failure over the log alone, the export keeping the dead segment's unrecorded end. *The
upload before the record.* A publication whose process died between the put and the
published record is retried against a store that lets the instance put and not read back:
the presence is adopted under the pending record the first command wrote, and nothing is
uploaded twice.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from leaveimpact.adapters.wiring import RunExportPublisher, Upload, run_export_publisher_over
from leaveimpact.agent.commands import (
    ApprovalDelivery,
    CommandRefused,
    PublishRequest,
    ReviewPayload,
    ReviewRequest,
    TerminalComposition,
    WorkRequest,
    deliver_approval,
    finalize,
    publish,
    review_approval,
    work,
)
from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_store import LogStore, LogStoreUnavailable
from leaveimpact.agent.log_transition import AttemptState, Rules, Transition
from leaveimpact.agent.worker import (
    AutomaticApproval,
    HumanApproval,
    WorkerConfiguration,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.inventory import PublicationStatus
from leaveimpact.core.run_record import FailureCategory
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.launch.plan import RECOVERY_BOUND, NextStep, next_step
from tests.integration.log_store_support import Rig, rig
from tests.integration.worker_rig import (
    ATTEMPT,
    RULES,
    RUN,
    admitted,
    completed,
    composition,
    saver_on,
)
from tests.unit import format_fixtures as cases
from tests.unit import worker_support as support
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.throwaway_world import loaded_world

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


# --- 1. a completion the transport reported uncertainly -----------------------------------------


def test_an_uncertain_completion_is_read_from_the_log_and_a_blind_resend_writes_nothing(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = completed(rig, world)
    before = store.load(RUN, ATTEMPT, rules=RULES)
    assert next_step(before, recoveries=0, approval=AutomaticApproval()) is NextStep.PUBLISH
    resent = work(
        WorkRequest(RUN, ATTEMPT, "nonce-resend", "launch-2"),
        store,
        composition(inputs, world, saver_on(rig)),
    )
    assert resent == WorkerEnding(WorkerEndingKind.CLOSED_ALREADY, RUN, ATTEMPT, 1, "completed")
    after = store.load(RUN, ATTEMPT, rules=RULES)
    assert after.events == before.events, "a re-sent work on a closed attempt writes nothing"


# --- 2. the human-waiting pause -----------------------------------------------------------------


def test_the_human_pause_reads_as_wait_then_work_and_the_resume_closes(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = admitted(rig, world)
    human = HumanApproval()
    assert next_step(store.load(RUN, ATTEMPT, rules=RULES), recoveries=0, approval=human) is (
        NextStep.WORK
    )
    paused = work(
        WorkRequest(RUN, ATTEMPT, "nonce-1", "launch-1"),
        store,
        composition(inputs, world, saver_on(rig), approval=HumanApproval()),
    )
    assert paused.kind is WorkerEndingKind.AWAITING_APPROVAL
    waiting = store.load(RUN, ATTEMPT, rules=RULES)
    assert next_step(waiting, recoveries=RECOVERY_BOUND, approval=human) is NextStep.WAIT
    reviewed = review_approval(ReviewRequest(RUN, ATTEMPT), store, rules=RULES)
    assert isinstance(reviewed, ReviewPayload) and not reviewed.approved
    delivered = deliver_approval(
        ApprovalDelivery(RUN, ATTEMPT, "human:reviewer", reviewed.digest), store, rules=RULES
    )
    assert not isinstance(delivered, CommandRefused)
    assert next_step(store.load(RUN, ATTEMPT, rules=RULES), recoveries=0, approval=human) is (
        NextStep.WORK
    )
    resumed = work(
        WorkRequest(RUN, ATTEMPT, "nonce-2", "launch-2"),
        store,
        composition(inputs, world, saver_on(rig), approval=HumanApproval()),
    )
    assert resumed == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 2, "completed")
    assert next_step(store.load(RUN, ATTEMPT, rules=RULES), recoveries=0, approval=human) is (
        NextStep.PUBLISH
    )


# --- 3. the recorded stop with an open segment --------------------------------------------------


class _ClosingLost:
    """The real store as the worker's log commands, whose first closing append fails as the
    log unavailable: the process reached its stopping failure and died before the closing
    was recorded."""

    def __init__(self, inner: LogStore) -> None:
        self._inner = inner
        self.lost = 0

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        return self._inner.load(run_id, attempt, rules=rules)

    def claim(self, *args: Any, **kwargs: Any) -> Transition:
        return self._inner.claim(*args, **kwargs)

    def append(self, *args: Any, **kwargs: Any) -> Transition:
        return self._inner.append(*args, **kwargs)

    def close_attempt(self, *args: Any, **kwargs: Any) -> Transition:
        if self.lost == 0:
            self.lost += 1
            raise LogStoreUnavailable("the connection dropped at the closing")
        return self._inner.close_attempt(*args, **kwargs)

    def now(self) -> datetime:
        return self._inner.now()


def test_a_recorded_stop_with_an_open_segment_is_recovered_by_the_terminal_path(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = admitted(rig, world)
    lossy = _ClosingLost(store)
    stopped = work(
        WorkRequest(RUN, ATTEMPT, "nonce-1", "launch-1"),
        lossy,  # type: ignore[arg-type]
        composition(inputs, world, saver_on(rig), script=support.SCRIPTS["throttled"]),
    )
    # The closing is appended from inside the graph's terminal step, so the store's fault
    # reaches the worker as the log unavailable; the attempt is left open either way.
    assert stopped == WorkerEnding(WorkerEndingKind.LEFT_OPEN, RUN, ATTEMPT, 1, "log unavailable")
    state = store.load(RUN, ATTEMPT, rules=RULES)
    assert state.closed is None and state.stopped is not None
    assert state.current_segment is not None and not state.current_segment.ended
    automatic = AutomaticApproval()
    assert next_step(state, recoveries=0, approval=automatic) is NextStep.RECOVER
    assert next_step(state, recoveries=RECOVERY_BOUND, approval=automatic) is NextStep.HOLD
    ending = finalize(
        WorkRequest(RUN, ATTEMPT, "nonce-2", "launch-2"),
        store,
        TerminalComposition(WorkerConfiguration.of(inputs), cases.REVISION, RULES),
    )
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 2, "failed")
    export = export_of(store.load(RUN, ATTEMPT, rules=RULES))
    failure = export.record.failure
    assert failure is not None and failure.category is FailureCategory.INFRASTRUCTURE
    assert (failure.category, failure.site) == (state.stopped.category, state.stopped.site)
    assert [segment.end_recorded for segment in export.record.timing.segments] == [False, True]


# --- 4. the upload before the record ------------------------------------------------------------


class _DiedAfterThePut:
    """A publisher whose process dies right after the object is put, before the command can
    write the published record."""

    def __init__(self, inner: RunExportPublisher) -> None:
        self._inner = inner

    def __call__(
        self, version: WorldVersion, run_id: str, attempt: int, reader: str, content: bytes
    ) -> Upload:
        self._inner(version, run_id, attempt, reader, content)
        raise SystemExit("the process died after the put")


def test_an_upload_before_the_record_is_adopted_under_the_pending_record_on_retry(
    rig: Rig, world: SealedWorld
) -> None:
    store, _ = completed(rig, world)
    memory = InMemoryObjectStore(readable=False)
    with pytest.raises(SystemExit):
        publish(
            PublishRequest(RUN, ATTEMPT, cases.COMMIT),
            store,
            _DiedAfterThePut(run_export_publisher_over(memory)),
            rules=RULES,
        )
    pending = store.publication_of(RUN, ATTEMPT)
    assert isinstance(pending, PublicationRecord) and pending.state is PublicationStatus.PENDING
    assert len(memory.objects) == 1
    record = publish(
        PublishRequest(RUN, ATTEMPT, cases.COMMIT),
        store,
        run_export_publisher_over(memory),
        rules=RULES,
    )
    assert isinstance(record, PublicationRecord) and record.state is PublicationStatus.PUBLISHED
    assert (record.object_identity, record.object_digest) == (
        pending.object_identity,
        pending.object_digest,
    )
    assert len(memory.objects) == 1, "nothing is uploaded twice"
