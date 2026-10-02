"""The condition a run was observed under, read off its reads: a source is unreachable exactly when
a read of it came back unreachable, a malformed record and a refused call change nothing, and a
source that both answered and failed is mixed in either order."""

from leaveimpact.core import (
    AbsentOutcome,
    DefectOutcome,
    Operation,
    OperationId,
    Outcome,
    PrefetchOrigin,
    RecordsOutcome,
    RefusedCallOutcome,
    RunCondition,
    Source,
    UnreachableOutcome,
    observed_condition,
)

NORMAL = RunCondition.all_reachable()


def reads(*outcomes: tuple[Source | None, Outcome]) -> tuple[Operation, ...]:
    """Prefetch reads in the order given, one operation per (source, outcome)."""
    return tuple(
        Operation(OperationId(f"op-{number}"), PrefetchOrigin(), "a_tool", source, {}, outcome)
        for number, (source, outcome) in enumerate(outcomes, start=1)
    )


def unreachable(source: Source) -> tuple[Source, Outcome]:
    return (source, UnreachableOutcome(source, "no answer after the retries"))


def answered(source: Source) -> tuple[Source, Outcome]:
    return (source, RecordsOutcome(()))


def test_a_run_whose_every_read_answered_ran_under_the_normal_condition() -> None:
    assert observed_condition(reads()).condition == NORMAL
    observed = observed_condition(
        reads(answered(Source.FRAPPE), (Source.JIRA, AbsentOutcome()), answered(Source.CORPUS))
    )
    assert observed.condition == NORMAL and not observed.is_mixed


def test_a_source_is_unreachable_exactly_when_a_read_of_it_came_back_unreachable() -> None:
    observed = observed_condition(
        reads(answered(Source.FRAPPE), unreachable(Source.JIRA), answered(Source.CALENDAR))
    )
    assert observed.condition == NORMAL.without(Source.JIRA)
    assert not observed.is_mixed
    both = observed_condition(reads(unreachable(Source.JIRA), unreachable(Source.CORPUS)))
    assert both.condition == NORMAL.without(Source.JIRA, Source.CORPUS)


def test_a_malformed_record_and_a_refused_call_are_not_an_outage() -> None:
    # The source answered a record that could not be translated: a defect, not a condition.
    defect = (Source.JIRA, DefectOutcome(Source.JIRA, "issue 10042", "no status"))
    # The wrapper refused the arguments: no source was asked, known or not.
    refused_known = (Source.JIRA, RefusedCallOutcome("a limit above the bound"))
    refused_unknown = (None, RefusedCallOutcome("no such tool"))
    observed = observed_condition(reads(defect, refused_known, refused_unknown))
    assert observed.condition == NORMAL and not observed.is_mixed


def test_a_source_that_both_answered_and_failed_is_mixed_in_either_order() -> None:
    answered_then_failed = observed_condition(
        reads(answered(Source.JIRA), unreachable(Source.JIRA), answered(Source.FRAPPE))
    )
    assert answered_then_failed.condition == NORMAL.without(Source.JIRA)
    assert answered_then_failed.mixed == frozenset({Source.JIRA})
    failed_then_answered = observed_condition(
        reads(unreachable(Source.JIRA), answered(Source.JIRA))
    )
    assert failed_then_answered.mixed == frozenset({Source.JIRA})
    # One source down for the whole run beside another that answered is a plain outage.
    whole_run = observed_condition(reads(unreachable(Source.JIRA), answered(Source.CALENDAR)))
    assert not whole_run.is_mixed
    # A malformed record does not make its unreachable source mixed: it is no completed read.
    defect = (Source.JIRA, DefectOutcome(Source.JIRA, "issue 10042", "no status"))
    assert not observed_condition(reads(defect, unreachable(Source.JIRA))).is_mixed
