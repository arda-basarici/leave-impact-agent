"""Eligibility for a new attempt: every ending has one rule; a graded result and a defect
permit nothing; a send failure follows its row; an abandonment permits a new attempt only
when no dispatch was ever authorized; a recorded defect keeps precedence over what closed
the attempt; and a rule that grants is still held to the registered category and maximum."""

import pytest

from leaveimpact.core.eligibility import (
    Abandoned,
    Completed,
    Eligibility,
    EligibilityRule,
    EndedByDefect,
    Ending,
    InputBoundExhausted,
    OtherInfrastructure,
    ReportedAtCap,
    SendFailure,
    UnresolvedAtMaximum,
    new_attempt_eligibility,
)
from leaveimpact.core.registration import RetryRule
from leaveimpact.core.run_record import FailureCategory

RETRY = RetryRule(FailureCategory.INFRASTRUCTURE, 3)

GRANTED: tuple[tuple[Ending, EligibilityRule], ...] = (
    (SendFailure("throttled", True), EligibilityRule.SEND_ROW),
    (UnresolvedAtMaximum(), EligibilityRule.UNRESOLVED_AT_MAXIMUM),
    (InputBoundExhausted(), EligibilityRule.INPUT_BOUND_EXHAUSTED),
    (Abandoned(0), EligibilityRule.ABANDONED_BEFORE_ANY_INTENT),
)
DENIED: tuple[tuple[Ending, EligibilityRule], ...] = (
    (Completed(), EligibilityRule.GRADED_RESULT),
    (ReportedAtCap(), EligibilityRule.GRADED_RESULT),
    (EndedByDefect(), EligibilityRule.DEFECT),
    (SendFailure("denied", False), EligibilityRule.SEND_ROW),
    (Abandoned(1), EligibilityRule.ABANDONED_AFTER_AN_INTENT),
    (Abandoned(7), EligibilityRule.ABANDONED_AFTER_AN_INTENT),
    (OtherInfrastructure("prefetch"), EligibilityRule.NO_RULE_NAMES_THE_ENDING),
    (OtherInfrastructure("event_append"), EligibilityRule.NO_RULE_NAMES_THE_ENDING),
    (OtherInfrastructure("checkpoint_resume"), EligibilityRule.NO_RULE_NAMES_THE_ENDING),
    (OtherInfrastructure("composition"), EligibilityRule.NO_RULE_NAMES_THE_ENDING),
)


def decide(
    ending: Ending | None,
    *,
    recorded_defect: bool = False,
    attempt: int = 1,
    retry: RetryRule = RETRY,
) -> Eligibility:
    return new_attempt_eligibility(
        ending, recorded_defect=recorded_defect, attempt=attempt, retry=retry
    )


def test_every_kind_of_ending_is_decided_by_a_case_here() -> None:
    """The closed vocabulary, counted: a new ending type without a row in these two tables
    fails here before it can go undecided."""
    covered = {type(ending) for ending, _ in (*GRANTED, *DENIED)}
    assert covered == set(Ending.__value__.__args__)


@pytest.mark.parametrize(("ending", "rule"), GRANTED, ids=lambda value: str(value))
def test_an_ending_a_rule_grants_permits_a_new_attempt(
    ending: Ending, rule: EligibilityRule
) -> None:
    decided = decide(ending)
    assert (decided.permitted, decided.rule) == (True, rule)


@pytest.mark.parametrize(("ending", "rule"), DENIED, ids=lambda value: str(value))
def test_an_ending_no_rule_grants_permits_none(ending: Ending, rule: EligibilityRule) -> None:
    decided = decide(ending)
    assert (decided.permitted, decided.rule) == (False, rule)


def test_a_send_failure_names_the_row_whose_flag_was_read() -> None:
    assert decide(SendFailure("throttled", True)).row == "throttled"
    assert decide(SendFailure("denied", False)).row == "denied"
    assert decide(UnresolvedAtMaximum()).row is None


def test_an_open_attempt_permits_nothing() -> None:
    assert decide(None) == Eligibility(False, EligibilityRule.PREDECESSOR_OPEN)


@pytest.mark.parametrize("ending", [ending for ending, _ in GRANTED], ids=lambda value: str(value))
def test_a_recorded_defect_keeps_precedence_over_what_closed_the_attempt(ending: Ending) -> None:
    decided = decide(ending, recorded_defect=True)
    assert decided == Eligibility(False, EligibilityRule.RECORDED_DEFECT)


def test_a_defect_ending_is_named_as_the_defect_it_is() -> None:
    decided = decide(EndedByDefect(), recorded_defect=True)
    assert decided == Eligibility(False, EligibilityRule.DEFECT)


@pytest.mark.parametrize("ending", [ending for ending, _ in GRANTED], ids=lambda value: str(value))
def test_the_registered_maximum_ends_the_attempts(ending: Ending) -> None:
    assert decide(ending, attempt=2).permitted
    last = decide(ending, attempt=3)
    assert (last.permitted, last.rule) == (False, EligibilityRule.MAXIMUM_REACHED)
    assert decide(ending, attempt=4).rule is EligibilityRule.MAXIMUM_REACHED


def test_under_a_maximum_of_one_no_attempt_follows_the_first() -> None:
    once = RetryRule(FailureCategory.INFRASTRUCTURE, 1)
    decided = decide(UnresolvedAtMaximum(), retry=once)
    assert decided == Eligibility(False, EligibilityRule.MAXIMUM_REACHED)


def test_the_maximum_keeps_the_row_a_send_failure_was_read_by() -> None:
    decided = decide(SendFailure("throttled", True), attempt=3)
    assert decided == Eligibility(False, EligibilityRule.MAXIMUM_REACHED, "throttled")


def test_an_ending_that_permits_nothing_is_named_by_its_own_rule_at_any_attempt() -> None:
    for attempt in (1, 3, 9):
        assert decide(Completed(), attempt=attempt).rule is EligibilityRule.GRADED_RESULT


@pytest.mark.parametrize(
    ("ending", "message"),
    [
        (lambda: Abandoned(-1), "the dispatch intents logged is at least 0"),
        (lambda: SendFailure("", True), "an attribution rule"),
        (lambda: OtherInfrastructure(" "), "a failure site"),
    ],
)
def test_an_ending_is_refused_outside_its_shape(ending: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        ending()  # type: ignore[operator]


def test_an_attempt_is_numbered_from_one() -> None:
    with pytest.raises(ValueError, match="an attempt number is at least 1"):
        decide(Completed(), attempt=0)
