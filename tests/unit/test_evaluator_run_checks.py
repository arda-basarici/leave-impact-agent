"""Reproduced whole on a report that left out a premise: every claim it holds still replays as
reproduced, and the check fails all the same."""

from leaveimpact.core import CandidateAssessment, Impact
from leaveimpact.evaluator.grading import Graded
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.run_checks import REPRODUCED_WHOLE
from tests.unit.evaluation_fixture import NORMAL, evaluated, truthful
from tests.unit.throwaway_world import loaded_world


def test_a_report_that_omits_an_impact_its_assessments_rest_on_is_not_reproduced_whole() -> None:
    world = loaded_world("golden")
    scenario = next(
        s
        for s in world.scenarios
        if any(isinstance(claim, Impact) for claim in truthful(world, s, NORMAL))
    )
    whole = truthful(world, scenario, NORMAL)
    assert REPRODUCED_WHOLE.of(evaluated(world, scenario)) is True

    impact = next(claim for claim in whole if isinstance(claim, Impact))
    without = tuple(claim for claim in whole if claim is not impact)
    evaluation = evaluated(world, scenario, claims=without)
    outcome = evaluation.outcome
    assert isinstance(outcome, Graded) and outcome.grounding is not None
    resting = [
        record
        for record, claim in zip(outcome.grounding.claims, without, strict=True)
        if isinstance(claim, CandidateAssessment) and claim.impact_key == impact.key
    ]
    # The claims that rested on the omitted impact are each reproduced, with a premise the
    # report does not hold: the state the check read as a pass before it read premises.
    assert resting
    assert all(record.standing is Standing.REPRODUCED for record in resting)
    assert all(record.missing_premises for record in resting)
    assert all(
        record.standing is Standing.REPRODUCED or record.missing_premises
        for record in outcome.grounding.claims
    )
    assert REPRODUCED_WHOLE.of(evaluation) is False
