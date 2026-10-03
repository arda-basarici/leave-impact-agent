"""Two readings of a cell that are raw counts and carry no interval: whether repeated runs of
a scenario agree, and what the runs of a degraded-condition arm did.

*Repeat consistency* (the investigator milestone's sixth build step, ruling 4). When a
scenario is run more than once, an estimate over its pass fraction does not say whether
the system passes some scenarios always and others never, or every scenario some of the
time. Per scenario, on one check: its counted runs all pass, all fail, or disagree. A
scenario is classified only when the comparison is whole: every intended run was made,
each with a verifiable attempt history, and the check applies to each. The others are
counted as incomplete and never guessed at. With one intended run there is nothing to
compare, and the diagnostic is not produced.

*The degraded table* (ruling 2). Under an assignment that leaves the leave or the policy
unreadable there is no claim-level answer to grade against, so the arm's runs are
described and not scored. Four things are kept apart, each run in exactly one row:

- *exposure*: whether the run met the outage it was assigned. A source scheduled out that
  the trace shows reachable was never exercised, and the run says nothing about the
  outage. A run with no trace to read (an excluded one) has no exposure to state.
- *outcome*: the evaluator's, graded, limited by reason or excluded by reason. An
  assignment does not decide it: a corpus outage a system never touched is a graded run.
- *report*: empty or non-empty for a completed report, and none for an excluded run, so a
  failed attempt is never counted as an empty report, which is the abstention the
  degraded states are meant to produce.
- *replay*: what the run's own reads make of the report. A report is many claims and a
  row is one run, so the run takes the worst standing any of its claims has: contradicted
  before unsupported before reproduced. A structurally invalid report was not replayed,
  and an empty or an absent one has nothing to replay.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.enums import Source
from leaveimpact.evaluator.cells import Cell, Preregistered
from leaveimpact.evaluator.grading import (
    Excluded,
    ExcludedReason,
    Graded,
    LimitedReason,
)
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.tables import Check
from leaveimpact.evaluator.trace_metrics import Evaluation

# --- Repeat consistency --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RepeatConsistency:
    """How a cell's scenarios fare across their repeats on one check: scenarios, by whether
    their runs all pass, all fail or disagree, and the ones that cannot be classified."""

    check: str
    arm: str
    scenarios: int
    all_pass: int
    all_fail: int
    disagree: int
    incomplete: int


def repeat_consistency(cell: Cell, check: Check, plan: Preregistered) -> RepeatConsistency | None:
    """``check`` across the repeats of each scenario of ``cell``; ``None`` when the plan
    intends one run, there being nothing to compare."""
    if plan.intended_repeats < 2:
        return None
    tally: Counter[str] = Counter()
    for runs in cell.scenarios:
        answers = [check.of(run) for run in runs.counted]
        whole = (
            runs.missing == 0
            and runs.unverifiable == 0
            and len(answers) >= plan.intended_repeats
            and None not in answers
        )
        if not whole:
            tally["incomplete"] += 1
        elif all(answers):
            tally["all_pass"] += 1
        elif not any(answers):
            tally["all_fail"] += 1
        else:
            tally["disagree"] += 1
    return RepeatConsistency(
        check.name,
        cell.arm.name,
        len(cell.scenarios),
        tally["all_pass"],
        tally["all_fail"],
        tally["disagree"],
        tally["incomplete"],
    )


# --- The degraded table --------------------------------------------------------------------


class Exposure(StrEnum):
    """Whether a run met the outage it was assigned; a member is the wire format."""

    EXERCISED = "exercised"
    UNEXERCISED = "unexercised"
    NOT_OBSERVED = "not_observed"


class OutcomeKind(StrEnum):
    """The three outcomes the evaluator gives a run."""

    GRADED = "graded"
    LIMITED = "limited"
    EXCLUDED = "excluded"


class ReportState(StrEnum):
    """What a run reported: a completed report, empty or not, or none at all."""

    EMPTY = "empty"
    NON_EMPTY = "non_empty"
    NONE = "none"


class ReplayState(StrEnum):
    """What a run's own reads make of its report, as the worst standing among its claims."""

    REPRODUCED = "reproduced"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    NOT_EVALUATED = "not_evaluated"
    NOTHING_TO_REPLAY = "nothing_to_replay"


@dataclass(frozen=True, slots=True)
class DegradedRow:
    """How many counted runs of a cell share one exposure, outcome, report and replay;
    ``reason`` is the outcome's own for a limited or an excluded run."""

    exposure: Exposure
    outcome: OutcomeKind
    reason: LimitedReason | ExcludedReason | None
    report: ReportState
    replay: ReplayState
    runs: int


def degraded_table(cell: Cell) -> tuple[DegradedRow, ...]:
    """The counted runs of ``cell`` by exposure, outcome, report and replay: the rows that
    occur, in a fixed order, their counts adding up to the counted runs."""
    tally = Counter(_described(run) for runs in cell.scenarios for run in runs.counted)
    return tuple(
        DegradedRow(*key, count)
        for key, count in sorted(
            tally.items(), key=lambda item: tuple(str(part) for part in item[0])
        )
    )


_Described = tuple[
    Exposure, OutcomeKind, LimitedReason | ExcludedReason | None, ReportState, ReplayState
]


def _described(run: Evaluation) -> _Described:
    outcome = run.outcome
    if isinstance(outcome, Excluded):
        return (
            Exposure.NOT_OBSERVED,
            OutcomeKind.EXCLUDED,
            outcome.reason,
            ReportState.NONE,
            ReplayState.NOTHING_TO_REPLAY,
        )
    scheduled_out = frozenset(Source) - run.assigned.reachable
    exercised = not (scheduled_out & outcome.condition.reachable)
    exposure = Exposure.EXERCISED if exercised else Exposure.UNEXERCISED
    if isinstance(outcome, Graded):
        kind, reason = OutcomeKind.GRADED, None
    else:
        kind, reason = OutcomeKind.LIMITED, outcome.reason
    grounding = outcome.grounding
    if grounding is None:
        # A structurally invalid claim set: claims were reported and none was replayed.
        return exposure, kind, reason, ReportState.NON_EMPTY, ReplayState.NOT_EVALUATED
    if not grounding.claims:
        return exposure, kind, reason, ReportState.EMPTY, ReplayState.NOTHING_TO_REPLAY
    standings = {claim.standing for claim in grounding.claims}
    if Standing.CONTRADICTED in standings:
        replay = ReplayState.CONTRADICTED
    elif Standing.UNSUPPORTED in standings:
        replay = ReplayState.UNSUPPORTED
    else:
        replay = ReplayState.REPRODUCED
    return exposure, kind, reason, ReportState.NON_EMPTY, replay


__all__ = [
    "DegradedRow",
    "Exposure",
    "OutcomeKind",
    "RepeatConsistency",
    "ReplayState",
    "ReportState",
    "degraded_table",
    "repeat_consistency",
]
