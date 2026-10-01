"""How far the dated view and runtime truth disagree on one world: a characterization, not a grade.

A sealed world can be read two ways. The *dated view* is the sealed fact base, each fact
visible from the day its record was planted. *Runtime truth* is what a run can obtain: the
systems hold every projected record at once and the harness dates what it reads to the
run's day. World assembly proves every sealed key under both, for the normal condition.
What the key does not hold (the verdict of a candidate outside the probe set, anything
under an outage) is proven under neither, and there the two can differ: a record a later
scenario plants is readable when an earlier one runs, and the dated view hides it.

The evaluator grades against runtime truth (the oracle module says why). This module
measures what that choice rests on, for one world: per run condition, every sealed impact
assessed over the whole organization under both views, the pairs whose verdict or reasons
differ, and the impacts whose expected outcome differs. It is a property of the world, the
scenario and the condition, never of a run, a model or a system, so it is computed once
per world and reported beside the results, not inside every evaluation. A difference
among the probed candidates under the normal condition would contradict assembly's proof;
elsewhere a difference is a candidate a dated oracle would have judged otherwise.

The comparison is of candidate judgments and outcomes for the sealed impacts, and no
wider. It does not compare the impact sets the rules derive under each view, nor the
expected constraints, conflicts or unknown claims; a count of zero here says the two
views agree on every verdict, reason and outcome, never that they agree on everything
the oracle expects.

The rules are asked with the sealed leave span under every condition, so under a
condition in which the leave itself is unreadable the counts describe the rules and not an
expectation: the oracle has no claim-level answer there.

What it returns names candidates and artifacts and so is truth; a caller that prints
counts prints no key.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.claims import AssessmentReason, ImpactKey, Verdict
from leaveimpact.core.facts import FactView, RunCondition
from leaveimpact.core.ids import EmployeeId, ScenarioId
from leaveimpact.core.plans import expected_action
from leaveimpact.evaluator.oracle import runtime_truth
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world.construction import Reading, read_impacts, required_count_for
from leaveimpact.world.scenario import Scenario

Judgment = tuple[Verdict, tuple[AssessmentReason, ...]]
"""A verdict with its reasons: what the two views are compared on, per candidate."""


@dataclass(frozen=True, slots=True)
class VerdictDifference:
    """One candidate for one sealed impact whom the two views judge differently."""

    scenario_id: ScenarioId
    impact: ImpactKey
    employee_id: EmployeeId
    probed: bool
    """Whether the candidate is in the impact's sealed must-assess set."""
    dated: Judgment
    runtime: Judgment

    @property
    def flips(self) -> bool:
        """Whether the verdict itself differs, and not only the reasons under one verdict."""
        return self.dated[0] is not self.runtime[0]


@dataclass(frozen=True, slots=True)
class ViewComparison:
    """The two views compared under one condition, over every sealed impact of a world."""

    condition: RunCondition
    probed_pairs: int
    other_pairs: int
    impacts: int
    verdict_differences: tuple[VerdictDifference, ...]
    outcome_differences: tuple[tuple[ScenarioId, ImpactKey], ...]


def compare_views(world: SealedWorld, condition: RunCondition) -> ViewComparison:
    """The dated view against runtime truth under ``condition``, every scenario at its run day.

    Each sealed impact is read under both views over the whole organization, through the
    reading pass every other consumer of the rules uses.
    """
    universe = tuple(employee.id for employee in world.org.employees)
    probed = other = impacts = 0
    verdicts: list[VerdictDifference] = []
    outcomes: list[tuple[ScenarioId, ImpactKey]] = []
    for scenario in world.scenarios:
        today = scenario.spec.today
        dated_view = world.facts.at(today, condition)
        runtime_view = runtime_truth(world, scenario).at(today, condition)
        dated = _readings(dated_view, scenario, universe)
        runtime = _readings(runtime_view, scenario, universe)
        for expected, before, after in zip(scenario.key.impacts, dated, runtime, strict=True):
            impacts += 1
            probe = {authored.employee_id for authored in expected.must_assess}
            probed += len(probe)
            other += len(universe) - len(probe)
            for old, new in zip(before.assessments, after.assessments, strict=True):
                if (old.verdict, old.reasons) != (new.verdict, new.reasons):
                    verdicts.append(
                        VerdictDifference(
                            scenario.spec.id,
                            expected.key,
                            old.employee_id,
                            old.employee_id in probe,
                            (old.verdict, old.reasons),
                            (new.verdict, new.reasons),
                        )
                    )
            if _outcome(dated_view, scenario, before) is not _outcome(
                runtime_view, scenario, after
            ):
                outcomes.append((scenario.spec.id, expected.key))
    return ViewComparison(condition, probed, other, impacts, tuple(verdicts), tuple(outcomes))


def _readings(
    view: FactView, scenario: Scenario, universe: tuple[EmployeeId, ...]
) -> tuple[Reading, ...]:
    leave = scenario.investigated_leave
    return read_impacts(
        view,
        [expected.key for expected in scenario.key.impacts],
        scenario.key.constraints,
        leave.employee_id,
        leave.span,
        scenario.spec.reference_timezone,
        universe,
    )


def _outcome(view: FactView, scenario: Scenario, reading: Reading) -> object:
    required = required_count_for(
        view,
        reading.impact,
        scenario.key.constraints,
        scenario.investigated_leave.span,
        scenario.spec.reference_timezone,
    )
    return expected_action((assessment.verdict for assessment in reading.assessments), required)


__all__ = ["Judgment", "VerdictDifference", "ViewComparison", "compare_views"]
