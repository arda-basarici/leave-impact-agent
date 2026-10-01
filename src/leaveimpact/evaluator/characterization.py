"""How far the dated view and runtime truth disagree on one world: a characterization, not a grade.

A sealed world can be read two ways. The *dated view* is the sealed fact base, each fact
visible from the day its record was planted. *Runtime truth* is what a run can obtain: the
systems hold every projected record at once and the harness dates what it reads to the
run's day. World assembly proves every sealed key under both, for the normal condition.
What the key does not hold (the verdict of a candidate outside the probe set, anything
under an outage) is proven under neither, and there the two can differ: a record a later
scenario plants is readable when an earlier one runs, and the dated view hides it.

The evaluator grades against runtime truth (the oracle module says why). This module
measures what that choice rests on, for one world and one run condition: the oracle's own
question, what do the rules conclude about this scenario, is asked of both views and the
two answers are compared part by part. Whether the leave is readable at all; the impacts
the rules ground; for each impact both views expect, every organization member's verdict
and reasons, the questions an unknown verdict leaves open, the requirements that apply
and the outcome; the expected constraints; the expected conflicts; the expected unknowns.
That is everything a report is graded against, so a comparison in which no part differs
says a dated oracle would have graded every item of that scenario the same, and one in
which a part differs names the part.

It is a property of the world, the scenario and the condition, never of a run, a model or
a system, so it is computed once per world and reported beside the results, not inside
every evaluation. Under the normal condition the sealed key is proven under both views,
so the impacts, the probed candidates' verdicts, the outcomes, the constraints, the
conflicts and the unknowns cannot differ there without contradicting that proof; what can
is the verdict of a candidate outside the probe set that changes no unknown. Under an
outage nothing is proven and every part can differ.

What a comparison returns names candidates and artifacts and so is truth; a caller that
prints its counts prints no key.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.claims import AssessmentReason, ImpactKey, Verdict
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import EmployeeId, ScenarioId
from leaveimpact.evaluator.oracle import Answerable, ImpactTruth, conclusions_in, runtime_truth
from leaveimpact.evaluator.sealed_world import SealedWorld

Judgment = tuple[Verdict, tuple[AssessmentReason, ...]]
"""A verdict with its reasons: what the two views are compared on, per candidate."""


@dataclass(frozen=True, slots=True)
class VerdictDifference:
    """One candidate for one expected impact whom the two views judge differently."""

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
    """The two views' answers compared under one condition, over every scenario of a world.

    ``answerable`` counts the scenarios both views can answer and ``impacts`` the impacts
    both expect; the candidate pairs are over those impacts. Each ``*_differences`` field
    lists where one part of the answer differs: by scenario for a part that is the
    scenario's, by impact or by candidate for a part that is theirs.
    """

    condition: RunCondition
    scenarios: int
    answerable: int
    impacts: int
    probed_pairs: int
    other_pairs: int
    state_differences: tuple[ScenarioId, ...]
    impact_set_differences: tuple[ScenarioId, ...]
    verdict_differences: tuple[VerdictDifference, ...]
    open_question_differences: tuple[tuple[ScenarioId, ImpactKey, EmployeeId], ...]
    requirement_differences: tuple[tuple[ScenarioId, ImpactKey], ...]
    outcome_differences: tuple[tuple[ScenarioId, ImpactKey], ...]
    constraint_differences: tuple[ScenarioId, ...]
    conflict_differences: tuple[ScenarioId, ...]
    unknown_differences: tuple[ScenarioId, ...]

    def counts(self) -> dict[str, int]:
        """How many differences each part holds, by the part's name: counts and no content."""
        return {
            "the leave readable in one view only": len(self.state_differences),
            "impact sets": len(self.impact_set_differences),
            "must-assess verdicts": sum(d.probed for d in self.verdict_differences),
            "other verdicts": sum(not d.probed for d in self.verdict_differences),
            "open questions": len(self.open_question_differences),
            "requirements": len(self.requirement_differences),
            "outcomes": len(self.outcome_differences),
            "constraints": len(self.constraint_differences),
            "conflicts": len(self.conflict_differences),
            "unknowns": len(self.unknown_differences),
        }

    @property
    def scenarios_differing(self) -> frozenset[ScenarioId]:
        """The scenarios for which any part of the answer differs between the views."""
        return frozenset(
            (
                *self.state_differences,
                *self.impact_set_differences,
                *(difference.scenario_id for difference in self.verdict_differences),
                *(scenario for scenario, _, _ in self.open_question_differences),
                *(scenario for scenario, _ in self.requirement_differences),
                *(scenario for scenario, _ in self.outcome_differences),
                *self.constraint_differences,
                *self.conflict_differences,
                *self.unknown_differences,
            )
        )


def compare_views(world: SealedWorld, condition: RunCondition) -> ViewComparison:
    """The dated view's answer against runtime truth's under ``condition``, every scenario at
    its run day.

    Both answers come from ``conclusions_in``, the oracle's core, so what is compared is
    what the grader would be handed under each view.
    """
    answerable = impacts = probed = other = 0
    states: list[ScenarioId] = []
    impact_sets: list[ScenarioId] = []
    verdicts: list[VerdictDifference] = []
    open_questions: list[tuple[ScenarioId, ImpactKey, EmployeeId]] = []
    requirements: list[tuple[ScenarioId, ImpactKey]] = []
    outcomes: list[tuple[ScenarioId, ImpactKey]] = []
    constraints: list[ScenarioId] = []
    conflicts: list[ScenarioId] = []
    unknowns: list[ScenarioId] = []
    for scenario in world.scenarios:
        today, name = scenario.spec.today, scenario.spec.id
        dated = conclusions_in(world, scenario, world.facts.at(today, condition))
        runtime = conclusions_in(
            world, scenario, runtime_truth(world, scenario).at(today, condition)
        )
        if not (isinstance(dated, Answerable) and isinstance(runtime, Answerable)):
            if isinstance(dated, Answerable) != isinstance(runtime, Answerable):
                states.append(name)
            continue
        answerable += 1
        if {truth.key for truth in dated.impacts} != {truth.key for truth in runtime.impacts}:
            impact_sets.append(name)
        for before in dated.impacts:
            after = runtime.impact(before.key)
            if after is None:
                continue
            impacts += 1
            probed += len(before.probe)
            other += len(before.assessments) - len(before.probe)
            for old, new in zip(before.assessments, after.assessments, strict=True):
                if (old.verdict, old.reasons) != (new.verdict, new.reasons):
                    verdicts.append(
                        VerdictDifference(
                            name,
                            before.key,
                            old.employee_id,
                            old.employee_id in before.probe,
                            (old.verdict, old.reasons),
                            (new.verdict, new.reasons),
                        )
                    )
                elif old.unresolved != new.unresolved:
                    open_questions.append((name, before.key, old.employee_id))
            if _required(before) != _required(after):
                requirements.append((name, before.key))
            if before.outcome is not after.outcome:
                outcomes.append((name, before.key))
        if dated.constraints != runtime.constraints:
            constraints.append(name)
        if set(dated.conflicts) != set(runtime.conflicts):
            conflicts.append(name)
        if dated.unknowns != runtime.unknowns:
            unknowns.append(name)
    return ViewComparison(
        condition=condition,
        scenarios=len(world.scenarios),
        answerable=answerable,
        impacts=impacts,
        probed_pairs=probed,
        other_pairs=other,
        state_differences=tuple(states),
        impact_set_differences=tuple(impact_sets),
        verdict_differences=tuple(verdicts),
        open_question_differences=tuple(open_questions),
        requirement_differences=tuple(requirements),
        outcome_differences=tuple(outcomes),
        constraint_differences=tuple(constraints),
        conflict_differences=tuple(conflicts),
        unknown_differences=tuple(unknowns),
    )


def _required(truth: ImpactTruth) -> tuple[int, tuple[object, ...]]:
    """What an impact asks of a plan, comparable across views: the count, and each readable
    requirement by its clause and content. The fact stating it is left out, since the two
    views date one fact differently."""
    return (
        truth.required,
        tuple((resolved.clause_id, resolved.requirement) for resolved in truth.requirements),
    )


__all__ = ["Judgment", "VerdictDifference", "ViewComparison", "compare_views"]
