"""The three registered checks: yes-or-no questions of one run, each defined mechanically.

The preregistration names its checks and the tables take any (the investigator
milestone's sixth build step, ruling 4); these are the ones a registration can name. Each
answers ``True`` or ``False`` for a run it applies to and ``None`` for one it does not,
and the two readings of a table do the rest: conditionally a run it does not apply to is
left out, end to end it did not pass.

*Correct whole* is the grade's own reading of a graded run (``grading.correct_whole``):
structurally valid, every required row reported, every reported row's payload right, no
unexpected or unmatched row, no plan finding against the oracle. It reads no
report-coherence finding, coverage gap, grounding or citation, and is not extended to.

*Expected action* reads the action rows of a graded run and nothing else: every required
action reported, every reported action of the expected kind, none unexpected or unmatched.
Whether the people an assign names are valid is not part of it; that is inside correct
whole, through the oracle's plan findings. A structurally invalid report fails: a report
that cannot be read stated no action.

*Reproduced whole* asks whether a run's own reads support its whole report: a structurally
valid report, every claim's replay standing reproduced. It needs no expected answer, so it
applies to a limited run as it does to a graded one. A structurally invalid report fails.
An empty report is outside it: there is nothing to reproduce, which is a different
statement from everything reproduced, so it is counted apart and does not pass end to end.
"""

from __future__ import annotations

from leaveimpact.evaluator.grading import Excluded, Graded, action_matches, correct_whole
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.rows import Expectation
from leaveimpact.evaluator.tables import Check
from leaveimpact.evaluator.trace_metrics import Evaluation


def _correct_whole(evaluation: Evaluation) -> bool | None:
    outcome = evaluation.outcome
    return correct_whole(outcome) if isinstance(outcome, Graded) else None


def _expected_action(evaluation: Evaluation) -> bool | None:
    outcome = evaluation.outcome
    if not isinstance(outcome, Graded):
        return None
    if not outcome.rows.structurally_valid:
        return False
    for row in outcome.rows.actions:
        if row.expectation in (Expectation.UNEXPECTED, Expectation.NOT_MATCHED):
            return False
        if row.expectation is Expectation.REQUIRED and row.claim_id is None:
            return False
        if action_matches(row) is False:
            return False
    return True


def _reproduced_whole(evaluation: Evaluation) -> bool | None:
    outcome = evaluation.outcome
    if isinstance(outcome, Excluded):
        return None
    grounding = outcome.grounding
    if grounding is None:
        # Not replayed: the claim set was structurally invalid.
        return False
    if not grounding.claims:
        return None
    return all(claim.standing is Standing.REPRODUCED for claim in grounding.claims)


CORRECT_WHOLE = Check("correct_whole", _correct_whole)
EXPECTED_ACTION = Check("expected_action", _expected_action)
REPRODUCED_WHOLE = Check("reproduced_whole", _reproduced_whole)

__all__ = ["CORRECT_WHOLE", "EXPECTED_ACTION", "REPRODUCED_WHOLE"]
