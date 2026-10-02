"""The answer-side measures are read off a graded run's rows, as a numerator and a denominator.
A truthful report is at the ceiling of every one. A required claim left out costs recall and
no precision; a wrong payload costs recall, both precisions and payload accuracy; an optional
claim that is right counts for precision and not for recall. Claims hung on an unexpected
impact count against strict precision and are left out of the type-local one. A structurally
invalid report is in every denominator and no numerator, and a run that was not graded is in
no measure at all."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    CandidateAssessment,
    Claim,
    ClaimType,
    CoverageAction,
    Source,
    SourceConflict,
    Verdict,
)
from leaveimpact.core.ids import LeaveId, claim_id
from leaveimpact.core.refs import employee_ref
from leaveimpact.evaluator.grading import Graded, Limited
from leaveimpact.evaluator.measures import (
    ANSWER_MEASURES,
    Counts,
    Measure,
    conflict_observations,
    payload_accuracy,
    recall,
    strict_precision,
    type_local_precision,
    unexpected_by_standing,
)
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from tests.unit.evaluation_fixture import NORMAL, evaluated, truthful
from tests.unit.export_fixture import provider_failed_export
from tests.unit.report_fixture import of_type, renumbered, swapped, without
from tests.unit.throwaway_world import loaded_world

ASSESSMENT, ACTION = ClaimType.CANDIDATE_ASSESSMENT, ClaimType.COVERAGE_ACTION
CONFLICT = ClaimType.SOURCE_CONFLICT
SPARE = 9_000


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def counts(measure: Measure, evaluation: Evaluation) -> Counts:
    found = measure.of(evaluation)
    assert found is not None, measure.name
    return found


def probed(
    world: SealedWorld, verdict: Verdict
) -> tuple[Scenario, tuple[Claim, ...], CandidateAssessment]:
    """A scenario whose truthful report holds an assessment of a probed candidate with
    ``verdict``, with the report and that claim."""
    for scenario in world.scenarios:
        oracle = oracle_for(world, scenario, NORMAL)
        assert isinstance(oracle, Answerable)
        report = truthful(world, scenario, NORMAL)
        for claim in of_type(report, CandidateAssessment):
            truth = oracle.impact(claim.impact_key)
            if truth and claim.employee_id in truth.probe and claim.verdict is verdict:
                return scenario, report, claim
    raise AssertionError(f"no probed {verdict.value} assessment")


def test_a_truthful_report_is_at_the_ceiling_of_every_answer_measure(world: SealedWorld) -> None:
    held = dict.fromkeys((measure.name for measure in ANSWER_MEASURES), 0)
    for scenario in world.scenarios:
        evaluation = evaluated(world, scenario)
        for measure in ANSWER_MEASURES:
            numerator, denominator = counts(measure, evaluation)
            assert numerator == denominator, (scenario.spec.id, measure.name)
            held[measure.name] += denominator
        # The per-type counts add up to the count over all claims.
        for family in (recall, strict_precision, type_local_precision):
            by_type = sum(counts(family(kind), evaluation)[1] for kind in ClaimType)
            assert by_type == counts(family(), evaluation)[1]
    # Every measure had something to count somewhere in the set: none passes vacuously.
    assert all(total > 0 for total in held.values()), held
    # 27: recall and the two precisions over all and per type, payload accuracy where a
    # claim type has a payload, and a conflict's observations.
    assert len(ANSWER_MEASURES) == 27
    assert held["recall: all claims"] == 161
    assert held["strict precision: all claims"] > held["recall: all claims"]


def test_a_required_claim_left_out_costs_recall_and_no_precision(world: SealedWorld) -> None:
    scenario, report, claim = probed(world, Verdict.NON_VIABLE)
    whole = evaluated(world, scenario)
    lacking = evaluated(world, scenario, claims=without(report, claim))
    right, required = counts(recall(ASSESSMENT), whole)
    assert counts(recall(ASSESSMENT), lacking) == (right - 1, required)
    for precision in (strict_precision, type_local_precision):
        correct, reported = counts(precision(ASSESSMENT), whole)
        assert counts(precision(ASSESSMENT), lacking) == (correct - 1, reported - 1)


def test_a_wrong_payload_costs_recall_both_precisions_and_payload_accuracy(
    world: SealedWorld,
) -> None:
    scenario, report, claim = probed(world, Verdict.NON_VIABLE)
    whole = evaluated(world, scenario)
    wrong = replace(claim, verdict=Verdict.VIABLE, reasons=())
    mistaken = evaluated(world, scenario, claims=swapped(report, claim, wrong))
    for measure in (recall, strict_precision, type_local_precision, payload_accuracy):
        numerator, denominator = counts(measure(ASSESSMENT), whole)
        # Held with the wrong payload: still reported, still required, never a true positive.
        assert counts(measure(ASSESSMENT), mistaken) == (numerator - 1, denominator)


def test_an_optional_claim_that_is_right_counts_for_precision_and_not_for_recall(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    oracle = oracle_for(world, scenario, NORMAL)
    assert isinstance(oracle, Answerable)
    report = truthful(world, scenario, NORMAL)
    outside = next(
        claim
        for claim in of_type(report, CandidateAssessment)
        if claim.employee_id not in oracle.impacts[0].probe
        and claim.impact_key == oracle.impacts[0].key
    )
    whole = evaluated(world, scenario)
    lacking = evaluated(world, scenario, claims=without(report, outside))
    assert counts(recall(ASSESSMENT), lacking) == counts(recall(ASSESSMENT), whole)
    correct, reported = counts(strict_precision(ASSESSMENT), whole)
    assert counts(strict_precision(ASSESSMENT), lacking) == (correct - 1, reported - 1)


def test_claims_on_an_unexpected_impact_count_against_strict_precision_only(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    report = truthful(world, scenario, NORMAL)
    assessment = of_type(report, CandidateAssessment)[0]
    action = of_type(report, CoverageAction)[0]
    another_leave = replace(assessment.impact_key, leave_id=LeaveId("leave_999"))
    hung = (
        replace(assessment, impact_key=another_leave, claim_id=claim_id(SPARE)),
        replace(
            action,
            impact_key=another_leave,
            claim_id=claim_id(SPARE + 1),
            derived_from_claim_ids=(),
        ),
    )
    whole = evaluated(world, scenario)
    cascaded = evaluated(world, scenario, claims=(*report, *hung))
    assert isinstance(cascaded.outcome, Graded) and cascaded.outcome.rows.structurally_valid
    for kind in (ASSESSMENT, ACTION):
        correct, reported = counts(strict_precision(kind), whole)
        assert counts(strict_precision(kind), cascaded) == (correct, reported + 1)
        # The wrong impact is charged at the impact; these are not charged again for it.
        assert counts(type_local_precision(kind), cascaded) == (correct, reported)
    correct, reported = counts(strict_precision(), whole)
    assert counts(strict_precision(), cascaded) == (correct, reported + 2)
    assert counts(type_local_precision(), cascaded) == (correct, reported)
    assert counts(recall(), cascaded) == counts(recall(), whole)
    # They are counted by what they are, beside the ratios.
    assert unexpected_by_standing(cascaded) == {
        (ASSESSMENT, "on_an_unexpected_impact"): 1,
        (ACTION, "on_an_unexpected_impact"): 1,
    }
    assert unexpected_by_standing(whole) == {}


def test_a_conflict_resolved_rightly_from_an_observation_nobody_made_is_seen_on_its_own_axis(
    world: SealedWorld,
) -> None:
    scenario, report, conflict = next(
        (scenario, report, conflicts[0])
        for scenario in world.scenarios
        if (conflicts := of_type(report := truthful(world, scenario, NORMAL), SourceConflict))
    )
    first, *rest = conflict.observations
    held = {observation.value for observation in conflict.observations}
    somebody_else = next(
        employee_ref(employee.id)
        for employee in world.org.employees
        if employee_ref(employee.id) not in held
    )
    forged = replace(conflict, observations=(replace(first, value=somebody_else), *rest))
    honest = evaluated(world, scenario)
    invented = evaluated(world, scenario, claims=swapped(report, conflict, forged))
    # The payload is the value that stands and the rule that chose it, and both are right:
    # every measure of the payload is where it was (the matching ruling of the third step).
    for measure in (recall, strict_precision, payload_accuracy):
        assert counts(measure(CONFLICT), invented) == counts(measure(CONFLICT), honest)
    # What the sources were said to hold is its own flag and its own measure.
    assert counts(conflict_observations(), honest) == (1, 1)
    assert counts(conflict_observations(), invented) == (0, 1)


def test_a_structurally_invalid_report_is_in_every_denominator_and_no_numerator(
    world: SealedWorld,
) -> None:
    scenario = world.scenarios[0]
    report = truthful(world, scenario, NORMAL)
    whole = evaluated(world, scenario)
    invalid = evaluated(world, scenario, claims=(*report, renumbered(report[0], 9_999)))
    assert isinstance(invalid.outcome, Graded) and not invalid.outcome.rows.structurally_valid
    assert counts(recall(), invalid) == (0, counts(recall(), whole)[1])
    for precision in (strict_precision, type_local_precision):
        assert counts(precision(), invalid) == (0, len(report) + 1)
    # Nothing was matched, so no payload was judged and no observation checked.
    assert counts(payload_accuracy(), invalid) == (0, 0)
    assert counts(conflict_observations(), invalid) == (0, 0)
    # Not matched is not unexpected: the oracle was never asked, and the accounting counts
    # the report as structurally invalid.
    assert unexpected_by_standing(invalid) == {}


def test_a_run_that_was_not_graded_is_in_no_answer_measure(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    limited = evaluated(
        world, scenario, down=(Source.FRAPPE,), claims=truthful(world, scenario, NORMAL)
    )
    excluded = evaluate_run(world, provider_failed_export(world, scenario))
    assert isinstance(limited.outcome, Limited)
    for evaluation in (limited, excluded):
        assert all(measure.of(evaluation) is None for measure in ANSWER_MEASURES)
        assert unexpected_by_standing(evaluation) is None
