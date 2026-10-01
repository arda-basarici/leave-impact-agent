"""The condition a run was observed under, read off its trace: which sources answered and which
could not.

A run's condition is derived, never taken on trust (the run-policy ruling of the
investigator milestone's entry): a source is unreachable for a run when a read of it came
back unreachable, and only then. The record block stores the condition the harness
believed; the trace is the authority, and the caller that compares the two reports a
disagreement as a harness finding. An outage that was scheduled and never exercised is not
here at all, since a system that never called the failed source ran under no outage.

Only an ``unreachable`` outcome counts. A malformed record is a defect, the source did
answer; a refused call never reached a source. ``core``'s ``is_failed_read`` groups the
unreachable and the malformed for another question (was a source asked and the read
failed) and is not the test this module needs.

A *mixed* source is one that both answered a read and came back unreachable in the same
run, in either order. The registered outage is injected per source for the whole run, so
it cannot produce one; an unscheduled fault of a real vendor can. A conforming harness
stops calling a source after its first unreachable outcome, so the reverse order should
not occur, and the classification is total anyway. A run with a mixed source has no
expected answer derivable from the sealed world alone, because what it could conclude
depends on what it happened to read before the fault; the caller reports it apart.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.run_trace import RunTrace, UnreachableOutcome, is_completed_read


@dataclass(frozen=True, slots=True)
class ObservedCondition:
    """What a trace shows of its sources: the reachable ones, and the unreachable ones that
    had also answered."""

    condition: RunCondition
    mixed: frozenset[Source]

    @property
    def is_mixed(self) -> bool:
        """Whether any source both answered and failed in this run."""
        return bool(self.mixed)


def observed_condition(trace: RunTrace) -> ObservedCondition:
    """The condition ``trace`` was observed under.

    Every source is reachable except those with an ``unreachable`` outcome; ``mixed`` holds
    the unreachable sources that also completed a read.

    >>> observed_condition(RunTrace((), (), ())).condition == RunCondition.all_reachable()
    True
    """
    unreachable = frozenset(
        operation.outcome.source
        for operation in trace.operations
        if isinstance(operation.outcome, UnreachableOutcome)
    )
    answered = frozenset(
        operation.source
        for operation in trace.operations
        if operation.source is not None and is_completed_read(operation.outcome)
    )
    return ObservedCondition(
        RunCondition.all_reachable().without(*unreachable), unreachable & answered
    )


__all__ = ["ObservedCondition", "observed_condition"]
