"""The agent's projection of a closed log into the eligibility function's vocabulary agrees
with the evaluator's projection of the same attempt's export on every fixture (the event log
step's ruling on placement, part 1: two projections into one set of inputs), and refuses an
open attempt. The admission reads the predecessor through the agent's; the attempt history
reads exports through the evaluator's; a fixture where they differ is a defect in one."""

from __future__ import annotations

import pytest

from leaveimpact.agent.log_ending import eligibility_ending_of
from leaveimpact.agent.log_transition import fold
from leaveimpact.core import eligibility
from leaveimpact.evaluator.attribution_check import check_attributions
from leaveimpact.evaluator.call_check import check_calls
from leaveimpact.evaluator.eligibility_check import ending_of as evaluator_ending_of
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories


@pytest.mark.parametrize("name", list(histories.HISTORIES))
def test_the_agents_projection_is_the_evaluators_on_every_fixture(name: str) -> None:
    state = fold(histories.HISTORIES[name](), histories.RULES)
    export = cases.FIXTURES[name]()
    calls = export.trace.model_calls
    checked = check_calls(
        calls,
        export.record.failure,
        cases.TABLE,
        cases.POLICY,
        check_attributions(cases.TABLE, cases.POLICY, calls),
    )
    expected = evaluator_ending_of(export, checked, cases.POLICY)
    assert expected is not None, "every fixture's ending projects"
    assert eligibility_ending_of(state, histories.RULES) == expected


def test_the_fixtures_reach_four_of_the_vocabularys_kinds() -> None:
    """Measured at the build: the sixteen histories end completed, by defect, abandoned
    (before and after an intent) and with the input bound exhausted; no fixture ends by a
    send failure or unresolved at the maximum, which the admission's refusal reasons for
    those kinds therefore rest on the function's own tests for."""
    endings = [
        eligibility_ending_of(fold(build(), histories.RULES), histories.RULES)
        for build in histories.HISTORIES.values()
    ]
    assert {type(ending) for ending in endings} == {
        eligibility.Completed,
        eligibility.EndedByDefect,
        eligibility.Abandoned,
        eligibility.InputBoundExhausted,
    }
    assert {e.dispatch_intents for e in endings if isinstance(e, eligibility.Abandoned)} == {0, 1}


def test_an_open_attempt_has_no_eligibility_ending() -> None:
    open_history = histories.HISTORIES["a cut call"]()[:-1]
    with pytest.raises(ValueError, match="open attempt has no ending"):
        eligibility_ending_of(fold(open_history, histories.RULES), histories.RULES)
