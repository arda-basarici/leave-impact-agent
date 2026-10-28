"""The sweeper's reading of an open public attempt against the launcher's next-step rule
under a human approval, over every prefix of every history the fixtures hold: the two were
written apart (the lifecycle's rule at the launcher step, the sweeper's at the live-path
commands step and the worker service's step) and the worker service picks what the
sweeper leaves alone, so the two readings must agree, state by state. Where they differ by
design, the segment still open, the sweeper waits for the wall and the launcher would
recover: a public attempt has no automatic recovery (ruling 4), and the wall is the one
liveness rule the sweeper applies, so an open segment gets nothing here with no slot in
the snapshot.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from leaveimpact.agent.worker import HumanApproval
from leaveimpact.app.sweeper import (
    CloseStopped,
    CloseUnclaimed,
    CloseUnrecovered,
    CloseWait,
    FenceAndClose,
    Finalize,
    Publish,
    SweepSnapshot,
    SweptAttempt,
    actions_of,
)
from leaveimpact.launch.plan import NextStep, next_step
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit.log_store_memory import MemoryLog
from tests.unit.test_app_decide import FixedClock
from tests.unit.test_app_sweeper import LIVE, RULES, public, row_of, run_of

CLOSURES = (CloseStopped, CloseUnclaimed, CloseUnrecovered, CloseWait, FenceAndClose, Finalize)


@pytest.mark.parametrize("name", sorted(histories.HISTORIES))
def test_the_sweepers_reading_equals_the_launchers_next_step_where_the_segment_has_ended(
    name: str,
) -> None:
    events = histories.HISTORIES[name]()
    human = HumanApproval()
    for length in range(1, len(events) + 1):
        prefix = public(events[:length], 1)
        log = MemoryLog(clock=FixedClock(prefix[-1].timestamp))
        log.seed(prefix)
        state = log.load(run_of(1), 1, rules=RULES)
        if state.inputs is None:
            continue
        # A second after the last event: no deadline or wait has passed since it.
        at = prefix[-1].timestamp + timedelta(seconds=1)
        attempt = SweptAttempt(
            run_of(1),
            1,
            prefix[0].timestamp,
            state,
            row_of(1, prefix),
            log.publication_of(run_of(1), 1),
        )
        actions = actions_of(SweepSnapshot(at, (attempt,), None), LIVE, harness_commit=cases.COMMIT)
        closures = [action for action in actions if isinstance(action, CLOSURES)]
        step = next_step(state, approval=human)
        where = f"{name!r} at position {length}: {step.value}, planned {actions}"
        match step:
            case NextStep.PUBLISH:
                assert closures == [] and any(isinstance(a, Publish) for a in actions), where
            case NextStep.WORK | NextStep.WAIT:
                assert closures == [], where
            case NextStep.RECOVER | NextStep.HOLD:
                segment = state.current_segment
                assert segment is not None, where
                if state.stopped is not None:
                    assert len(closures) == 1, where
                    assert isinstance(closures[0], Finalize | CloseStopped), where
                elif segment.ended:
                    assert closures == [CloseUnrecovered(run_of(1), 1, state.generation)], where
                else:
                    assert closures == [], where
