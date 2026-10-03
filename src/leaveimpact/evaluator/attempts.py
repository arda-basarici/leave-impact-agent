"""A run's attempt history: which attempt is the run, and whether the history can be trusted
to say so.

A run is retried only after an infrastructure failure, a bounded number of times, and its
attempts are numbered from one (the investigator milestone's sixth build step, rulings 3
and 7). The counted attempt is the preregistration's rule. ``FIRST`` measures
first-attempt reliability; ``LAST`` is right only while the harness never retries a
behavioural result; ``EARLIEST_NOT_INFRASTRUCTURE`` is the registered system with its
infrastructure retries: the earliest attempt that did not fail by infrastructure, else the
last. A defect is a stopping outcome like any other: it is not retried because a retry
could conceal it.

Selection and conformance read the same attempts and share one notion of a stopping
outcome, so both are here. Three things a conforming harness never produces are findings
on the run:

- a *gap*: the attempt numbers are not exactly one to the number of attempts. An attempt
  is absent, and which attempt would have been counted cannot be known, under any rule:
  the absent one may be the first, or a stopping outcome before the ones present. The run
  has no counted attempt. It keeps its grades and its costs, is counted as made, and
  enters no quality estimate until its history is repaired.
- an *excess attempt*: an attempt numbered above the registered maximum.
- an *attempt after a stopping outcome*: an attempt whose predecessor is present and did
  not fail by infrastructure.

The last two leave the selection well defined, so the run is counted by the rule and the
finding is counted beside it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.evaluator.grading import Excluded, ExcludedReason
from leaveimpact.evaluator.trace_metrics import Evaluation


class CountedAttempt(StrEnum):
    """Which attempt of a retried run is the run, for everything but the cost ledger."""

    FIRST = "first"
    LAST = "last"
    EARLIEST_NOT_INFRASTRUCTURE = "earliest_not_infrastructure"


class HistoryFinding(StrEnum):
    """What a run's attempts show that the retry protocol never produces; a member is the
    wire format."""

    GAP = "gap"
    EXCESS_ATTEMPT = "excess_attempt"
    ATTEMPT_AFTER_STOPPING_OUTCOME = "attempt_after_stopping_outcome"


def failed_by_infrastructure(evaluation: Evaluation) -> bool:
    """Whether the attempt ended in the one outcome a retry may follow."""
    outcome = evaluation.outcome
    if not isinstance(outcome, Excluded):
        return False
    return outcome.reason is ExcludedReason.FAILED_BY_INFRASTRUCTURE


@dataclass(frozen=True, slots=True)
class RunHistory:
    """One run's attempts in attempt order, the one that counts, and what the history shows.

    ``counted`` is ``None`` exactly when the history has a gap: the selection is
    unverifiable and the run enters no estimate.
    """

    run_id: str
    attempts: tuple[Evaluation, ...]
    counted: Evaluation | None
    findings: tuple[HistoryFinding, ...]

    @property
    def retried(self) -> bool:
        """Whether the run has more than one attempt."""
        return len(self.attempts) > 1

    @property
    def recovered(self) -> bool:
        """Whether an attempt before the counted one failed by infrastructure and the
        counted one did not. A failure after the counted attempt is nothing the run
        recovered from."""
        if self.counted is None or failed_by_infrastructure(self.counted):
            return False
        number = self.counted.outcome.header.attempt
        return any(
            failed_by_infrastructure(attempt)
            for attempt in self.attempts
            if attempt.outcome.header.attempt < number
        )


def run_history(
    run_id: str, attempts: Sequence[Evaluation], rule: CountedAttempt, max_attempts: int
) -> RunHistory:
    """The history of the run ``run_id`` from its ``attempts``, each numbered once.

    Raises ``ValueError`` for a run with no attempt or one attempt number given twice, the
    caller's error and never a property of a run.
    """
    held = tuple(sorted(attempts, key=lambda attempt: attempt.outcome.header.attempt))
    numbers = [attempt.outcome.header.attempt for attempt in held]
    if not held or len(set(numbers)) != len(numbers):
        raise ValueError(f"run {run_id} has attempts, each number once, got {numbers}")
    findings: list[HistoryFinding] = []
    gapped = numbers != list(range(1, len(numbers) + 1))
    if gapped:
        findings.append(HistoryFinding.GAP)
    if numbers[-1] > max_attempts:
        findings.append(HistoryFinding.EXCESS_ATTEMPT)
    if any(
        later.outcome.header.attempt == earlier.outcome.header.attempt + 1
        and not failed_by_infrastructure(earlier)
        for earlier, later in zip(held, held[1:], strict=False)
    ):
        findings.append(HistoryFinding.ATTEMPT_AFTER_STOPPING_OUTCOME)
    counted = None if gapped else _counted(held, rule)
    return RunHistory(run_id, held, counted, tuple(findings))


def _counted(attempts: tuple[Evaluation, ...], rule: CountedAttempt) -> Evaluation:
    match rule:
        case CountedAttempt.FIRST:
            return attempts[0]
        case CountedAttempt.LAST:
            return attempts[-1]
        case CountedAttempt.EARLIEST_NOT_INFRASTRUCTURE:
            for attempt in attempts:
                if not failed_by_infrastructure(attempt):
                    return attempt
            return attempts[-1]


__all__ = [
    "CountedAttempt",
    "HistoryFinding",
    "RunHistory",
    "failed_by_infrastructure",
    "run_history",
]
