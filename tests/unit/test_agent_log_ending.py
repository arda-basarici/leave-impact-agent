"""The agent's projection of a closed log into the eligibility function's vocabulary agrees
with the evaluator's projection of the same attempt's export on every fixture (the event log
step's ruling on placement, part 1: two projections into one set of inputs), and refuses an
open attempt. The admission reads the predecessor through the agent's; the attempt history
reads exports through the evaluator's; a fixture where they differ is a defect in one."""

from __future__ import annotations

from dataclasses import replace

import pytest

from leaveimpact.agent.log_ending import eligibility_ending_of
from leaveimpact.agent.log_events import (
    DispatchOutcome,
    Failed,
    LoggedEvent,
    LoggedSettlement,
    WorkerStamp,
)
from leaveimpact.agent.log_reader import export_of
from leaveimpact.agent.log_transition import Appended, fold, next_state
from leaveimpact.core import (
    Attribution,
    AttributionKind,
    DispatchPhase,
    DispatchSite,
    FailureCategory,
    ModelCallId,
    ServiceError,
    eligibility,
)
from leaveimpact.core.run_account import settle
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


def test_a_failing_call_whose_attribution_the_table_disowns_projects_to_nothing_on_both_sides() -> (
    None
):
    """The log accepts a worker's reading as execution evidence (the transition checks the
    row and its kind, not the match); eligibility is not granted on one the table does not
    give the observation, and the evaluator gives the call no standing: both sides None."""
    events = histories.HISTORIES["a cut call"]()
    state = fold(events[:6], histories.RULES)
    held = events[6].event
    assert isinstance(held, DispatchOutcome)
    mislabelled = replace(
        held,
        observation=ServiceError(429, "ThrottlingException", None, "too many requests"),
        response=None,
        attribution=Attribution(AttributionKind.INFRASTRUCTURE, "stream"),
        zero_cost_rule=None,
    )
    appended = next_state(state, replace(events[6], event=mislabelled), histories.RULES)
    assert isinstance(appended, Appended) and appended.state.stopped is not None
    computed = settle(appended.state.account)
    closing = Failed(
        FailureCategory.INFRASTRUCTURE,
        DispatchSite(ModelCallId("call-1"), 1, DispatchPhase.SEND),
        "the call failed by infrastructure and no further dispatch is permitted",
        LoggedSettlement(computed.charged_pico_usd, computed.state, computed.kept_reason, 3),
    )
    logged = LoggedEvent(8, events[7].timestamp, WorkerStamp(1, 1, 1_600), closing)
    closed = next_state(appended.state, logged, histories.RULES)
    assert isinstance(closed, Appended)
    final = closed.state
    assert eligibility_ending_of(final, histories.RULES) is None
    export = export_of(final)
    calls = export.trace.model_calls
    attribution = check_attributions(cases.TABLE, cases.POLICY, calls)
    assert [finding.kind.value for finding in attribution.findings] == ["rule_not_the_tables"]
    checked = check_calls(calls, export.record.failure, cases.TABLE, cases.POLICY, attribution)
    assert evaluator_ending_of(export, checked, cases.POLICY) is None
