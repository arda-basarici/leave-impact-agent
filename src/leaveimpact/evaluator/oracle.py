"""The oracle: what the rules conclude about a scenario under a run condition, over runtime truth.

A sealed key holds the conclusions of the normal run condition and a bounded probe set of
candidates. Grading needs more than that: the verdict of a candidate the key does not
list, and everything a run should conclude when a source was down. Neither is stored
(DESIGN, "What a valid answer is": expected verdicts are derived per run condition), so
the evaluator derives them, here, through the one reading pass construction and world
assembly use, and anchors the derivation on the sealed key.

*Runtime truth* is the fact base a run can actually obtain: the organization, every
scenario's work items and documents, the leaves and events overlapping the scenario's
window, each dated to the run's day, with the authored facts admitted through their
carriers (``world.runtime_view``, the call world assembly makes). The planting dates of
the sealed base do not gate it. A record another scenario plants later is in the systems
when this scenario runs, a run can read it, and a truth that hid it would grade a correct
reading wrong; the sealed keys were proven under both views, and what the key does not
hold is derived under this one.

The oracle answers in one of three states, and two of them are the absence of an answer.
*Answerable*: the rules' conclusions follow. *Unreadable leave*: the investigated leave's
record is not readable under the condition, so the run could establish neither who is
leaving nor when. *Unreadable policy*: the source that holds what clauses require is
unreachable. In both there is no claim-level expectation at all, which is a state and not
an empty answer, since an empty expected set would let a silent report score perfectly.

Both are asked before the rules because the rules would go on concluding without them.
They take the leave's span as a premise. And they take the sealed constraints as an
input, which is knowledge only the policy source gives a run: which clause applies to an
artifact, and whether any does. With that source down the rules still say "unknown" for an
impact a clause governs and leave an ungoverned one unchanged, a distinction no run can
see. A system that always assigns would be right on the ungoverned impacts and one that
always says unknown on the governed ones, neither on both except by luck, and the
expected unknowns would name a clause nobody could have read. So the state holds for every
scenario under that condition, governed or not, and it is stated by the evidence domain of
what a clause requires, not by a source's name.

Under a condition the expected impacts are the ones the rules ground there
(``derive_impacts``), never the sealed impacts filtered afterwards; only a grounded
impact carries assessments, an outcome and a probe set, the probe set being the sealed
one for that impact. A constraint is expected when its clause is readable and it applies
to a grounded impact. The expected conflicts and unknowns are read off the same readings.

Under the normal condition the answer must be the sealed key: the same impacts, the
authored verdict and reasons for every probed candidate, each outcome, the expected
conflicts and unknowns, the constraints. ``OracleDisagrees`` says this module derived
something else, a defect of the evaluator and never of a run. World loading has already
shown the rules reproduce every key; this shows the oracle, the code that feeds the
grader, does.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from leaveimpact.core.claims import ConstraintKey, CoverageActionKind, ImpactKey
from leaveimpact.core.closure import KnownTrue, Unresolved, establish
from leaveimpact.core.facts import FactBase, FactView, RunCondition
from leaveimpact.core.grounding import derive_impacts
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.plans import expected_action, required_count
from leaveimpact.core.predicates import PredicateName, predicate
from leaveimpact.core.refs import EntityRef, clause_ref
from leaveimpact.core.viability import (
    Assessment,
    ResolvedRequirement,
    applicable_requirements,
    need_of,
)
from leaveimpact.core.worldtime import DateSpan
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world.construction import Reading, expectations_of, read_impacts
from leaveimpact.world.runtime_view import runtime_facts, runtime_records
from leaveimpact.world.scenario import ExpectedConflict, ExpectedUnknown, Scenario


class OracleDisagrees(Exception):
    """Under the normal condition the oracle did not derive the sealed key: an evaluator defect.

    The message names the scenario and which part of the key differs, never the key's
    content.
    """


@dataclass(frozen=True, slots=True)
class ImpactTruth:
    """What the rules conclude about one impact the leaver holds under the condition.

    ``probe`` is the sealed must-assess set for this impact, the candidates whose
    assessments a report is required to hold, in the key's order; empty for an impact no
    key lists. ``assessments`` cover the whole organization in its order, so a candidate
    outside the probe set has a verdict here too. ``requirements`` are the clause-backed
    requirements that apply and could be read, ``required`` the number of viable people
    they ask for, and ``outcome`` the action the truth expects.
    """

    key: ImpactKey
    probe: tuple[EmployeeId, ...]
    assessments: tuple[Assessment, ...]
    requirements: tuple[ResolvedRequirement, ...]
    required: int
    outcome: CoverageActionKind

    def assessment_of(self, employee: EmployeeId) -> Assessment | None:
        """The rules' assessment of ``employee`` for this impact; ``None`` outside the
        organization."""
        for assessment in self.assessments:
            if assessment.employee_id == employee:
                return assessment
        return None


@dataclass(frozen=True, slots=True)
class Answerable:
    """The rules' conclusions about ``scenario`` under ``condition``.

    ``view`` is runtime truth as that condition sees it, kept so a claim the oracle does not
    expect can still be asked of the rules. ``impacts`` hold the sealed impacts that remain
    grounded, in the key's order, then any other the rules ground. ``unknowns`` are the
    complete derived set, one per candidate, subject, fact and reason.
    """

    scenario: Scenario
    condition: RunCondition
    view: FactView
    universe: tuple[EmployeeId, ...]
    impacts: tuple[ImpactTruth, ...]
    constraints: tuple[ConstraintKey, ...]
    conflicts: tuple[ExpectedConflict, ...]
    unknowns: tuple[ExpectedUnknown, ...]

    def impact(self, key: ImpactKey) -> ImpactTruth | None:
        """The truth about the expected impact ``key``, or ``None`` when it is not expected."""
        for truth in self.impacts:
            if truth.key == key:
                return truth
        return None


@dataclass(frozen=True, slots=True)
class UnreadableLeave:
    """The investigated leave's record cannot be read under ``condition``: no claim-level
    expectation exists, and that is a different statement from "nothing is expected"."""

    scenario: Scenario
    condition: RunCondition


@dataclass(frozen=True, slots=True)
class UnreadablePolicy:
    """What clauses require cannot be read under ``condition``, so which constraints govern an
    impact, and whether any does, is something no run could establish: no claim-level
    expectation exists, for a scenario a clause governs and for one none does alike."""

    scenario: Scenario
    condition: RunCondition


type Oracle = Answerable | UnreadableLeave | UnreadablePolicy


def runtime_truth(world: SealedWorld, scenario: Scenario) -> FactBase:
    """The fact base a run of ``scenario`` can obtain from ``world``, dated to its run day."""
    records = runtime_records(
        world.org,
        [other.owned for other in world.scenarios],
        scenario.spec,
        [brief for other in world.scenarios for brief in other.briefs],
    )
    authored = [fact for other in world.scenarios for fact in other.authored_facts]
    return runtime_facts(records, scenario.spec.today, authored)


def oracle_for(world: SealedWorld, scenario: Scenario, condition: RunCondition) -> Oracle:
    """What the rules conclude about ``scenario`` of ``world`` under ``condition``.

    ``UnreadableLeave`` when the leave's record is not readable there, ``UnreadablePolicy``
    when what clauses require is not; the leave is asked first. Raises ``OracleDisagrees``
    when ``condition`` is the normal one and the answer is not the sealed key.
    """
    view = runtime_truth(world, scenario).at(scenario.spec.today, condition)
    answer = conclusions_in(world, scenario, view)
    if isinstance(answer, Answerable) and condition == RunCondition.all_reachable():
        _require_the_sealed_key(answer)
    return answer


def conclusions_in(world: SealedWorld, scenario: Scenario, view: FactView) -> Oracle:
    """What the rules conclude about ``scenario`` in ``view``, whichever reading of the world
    the view is.

    The oracle is this over runtime truth, and ``oracle_for`` is the grader's entry: it
    builds that view and anchors the answer on the sealed key. This is exposed for the one
    other caller, the characterization, which asks the same question of the dated view to
    measure where the two readings part. Nothing is anchored here.
    """
    condition = view.condition
    if not _leave_is_readable(view, scenario):
        return UnreadableLeave(scenario, condition)
    if not condition.reaches(predicate(PredicateName.REQUIRES).evidence_domain):
        return UnreadablePolicy(scenario, condition)
    key, spec, leave = scenario.key, scenario.spec, scenario.investigated_leave
    universe = tuple(employee.id for employee in world.org.employees)
    grounded = derive_impacts(
        view, spec.leave_id, leave.employee_id, leave.span, spec.reference_timezone
    ).grounded
    sealed = [expected.key for expected in key.impacts]
    ordered = [impact for impact in sealed if impact in grounded]
    ordered.extend(impact for impact in grounded if impact not in sealed)
    readings = read_impacts(
        view,
        ordered,
        key.constraints,
        leave.employee_id,
        leave.span,
        spec.reference_timezone,
        universe,
    )
    probes = {
        expected.key: tuple(authored.employee_id for authored in expected.must_assess)
        for expected in key.impacts
    }
    truths: list[ImpactTruth] = []
    scopes: list[frozenset[EntityRef]] = []
    for reading in readings:
        requirements, scope = _requirements_and_scope(
            view, reading.impact, key.constraints, leave.span, spec.reference_timezone
        )
        scopes.append(scope)
        truths.append(_impact_truth(reading, requirements, probes.get(reading.impact, ())))
    expectations = expectations_of(view, readings)
    return Answerable(
        scenario=scenario,
        condition=condition,
        view=view,
        universe=universe,
        impacts=tuple(truths),
        constraints=_expected_constraints(view, key.constraints, scopes),
        conflicts=expectations.conflicts,
        unknowns=expectations.unknowns,
    )


def _leave_is_readable(view: FactView, scenario: Scenario) -> bool:
    """Whether the record of the investigated leave is among what ``view`` can read."""
    return any(
        fact.evidence.target.id == scenario.spec.leave_id
        for fact in view.facts_of(PredicateName.ON_LEAVE)
    )


def _requirements_and_scope(
    view: FactView,
    impact: ImpactKey,
    constraints: Sequence[ConstraintKey],
    leave_span: DateSpan,
    reference_timezone: str,
) -> tuple[tuple[ResolvedRequirement, ...], frozenset[EntityRef]]:
    """The readable requirements that apply to ``impact``, and what a constraint may name to
    apply to it: the artifact, and its component when that could be read."""
    need = need_of(view, impact, leave_span, reference_timezone)
    if isinstance(need, Unresolved):
        return (), frozenset({impact.artifact})
    scope = {impact.artifact}
    if isinstance(need.component, EntityRef):
        scope.add(need.component)
    resolved = tuple(
        requirement
        for requirement in applicable_requirements(view, need, constraints)
        if isinstance(requirement, ResolvedRequirement)
    )
    return resolved, frozenset(scope)


def _impact_truth(
    reading: Reading, requirements: tuple[ResolvedRequirement, ...], probe: tuple[EmployeeId, ...]
) -> ImpactTruth:
    required = required_count(requirements)
    return ImpactTruth(
        key=reading.impact,
        probe=probe,
        assessments=reading.assessments,
        requirements=requirements,
        required=required,
        outcome=expected_action(
            (assessment.verdict for assessment in reading.assessments), required
        ),
    )


def _expected_constraints(
    view: FactView, constraints: Sequence[ConstraintKey], scopes: Iterable[frozenset[EntityRef]]
) -> tuple[ConstraintKey, ...]:
    """The sealed constraints a run under this condition can establish: the clause readable,
    and what it applies to within the scope of an impact the rules ground."""
    in_scope = frozenset[EntityRef]().union(*scopes)
    return tuple(
        constraint
        for constraint in constraints
        if constraint.applies_to in in_scope
        and isinstance(
            establish(view, clause_ref(constraint.clause_id), PredicateName.REQUIRES), KnownTrue
        )
    )


def _require_the_sealed_key(answer: Answerable) -> None:
    """Refuse an answer under the normal condition that is not the sealed key."""
    key = answer.scenario.key
    differing: list[str] = []
    if [truth.key for truth in answer.impacts] != [expected.key for expected in key.impacts]:
        differing.append("impacts")
    for expected in key.impacts:
        truth = answer.impact(expected.key)
        if truth is None:
            continue
        if truth.outcome is not expected.outcome:
            differing.append("an outcome")
        for authored in expected.must_assess:
            derived = truth.assessment_of(authored.employee_id)
            if derived is None or (derived.verdict, derived.reasons) != (
                authored.verdict,
                authored.reasons,
            ):
                differing.append("a must-assess verdict")
    if answer.constraints != key.constraints:
        differing.append("constraints")
    if answer.conflicts != key.expected_conflicts:
        differing.append("expected conflicts")
    if answer.unknowns != key.expected_unknowns:
        differing.append("expected unknowns")
    if differing:
        raise OracleDisagrees(
            f"{key.scenario_id}: under the normal condition the oracle's "
            f"{', '.join(dict.fromkeys(differing))} are not the sealed key's"
        )


__all__ = [
    "Answerable",
    "ImpactTruth",
    "Oracle",
    "OracleDisagrees",
    "UnreadableLeave",
    "UnreadablePolicy",
    "conclusions_in",
    "oracle_for",
    "runtime_truth",
]
