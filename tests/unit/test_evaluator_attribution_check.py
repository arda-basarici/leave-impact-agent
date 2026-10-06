"""Each dispatch's recorded reading is held to the registered attribution table: the rule
must be one the table gives the observation, under no cause or under one a harness can
supply, and the kind beside it that row's. A dispatch that was followed by another names a
row that allows one, the row being the table's and not whatever the record names, an
unresolved dispatch always may be, and a call holds no more dispatches than the registered
bound when one is set. The twelve format 2 cases carry no finding under a table that holds
the rules they name. The check is evaluated only for a run
whose record names the table's digest, and a run it is not evaluated for is counted so."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    UNRESOLVED_RULE,
    Attribution,
    AttributionKind,
    AttributionRow,
    AttributionTable,
    BrokenStream,
    Cause,
    ClientError,
    ClientErrorKind,
    CompleteResponse,
    Dispatch,
    DispatchPhase,
    DispatchSite,
    Failure,
    FailureCategory,
    Match,
    ModelCall,
    ModelCallId,
    NoRecordedOutcome,
    ObservationKind,
    RedispatchPolicy,
    RefusedBeforeSend,
    RunExport,
    ServiceError,
    attribute,
    attribution_table_digest,
)
from leaveimpact.core.model_calls import Observation
from leaveimpact.evaluator.attribution_check import (
    AttributionCheck,
    AttributionFinding,
    AttributionFindingKind,
    check_attributions,
)
from leaveimpact.evaluator.cells import accounting_of, arms, attempt_summary_of, cells_of
from leaveimpact.evaluator.registered import preregistered
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from tests.unit.export_fixture import ROLE, agent_export, dispatch, run_export
from tests.unit.format_fixtures import FIXTURES
from tests.unit.format_fixtures import POLICY as FIXTURE_POLICY
from tests.unit.format_fixtures import TABLE as FIXTURE_TABLE
from tests.unit.registration_fixture import DRAFT, decided, light, named
from tests.unit.throwaway_world import loaded_world

KINDS = AttributionFindingKind
BEHAVIOUR, INFRASTRUCTURE, DEFECT, UNRESOLVED = (
    AttributionKind.BEHAVIOUR,
    AttributionKind.INFRASTRUCTURE,
    AttributionKind.DEFECT,
    AttributionKind.UNRESOLVED,
)
TABLE = AttributionTable(
    (
        AttributionRow("answered", Match(ObservationKind.COMPLETE_RESPONSE), BEHAVIOUR),
        AttributionRow(
            "stream", Match(ObservationKind.BROKEN_STREAM), INFRASTRUCTURE, redispatch=True
        ),
        AttributionRow(
            "own_request",
            Match(ObservationKind.SERVICE_ERROR, cause=Cause.HARNESS_REQUEST_CONTRACT),
            DEFECT,
        ),
        AttributionRow(
            "throttled",
            Match(ObservationKind.SERVICE_ERROR, http_statuses=frozenset({429})),
            INFRASTRUCTURE,
            redispatch=True,
            new_attempt=True,
        ),
        AttributionRow(
            "any_error", Match(ObservationKind.SERVICE_ERROR), INFRASTRUCTURE, unmatched=True
        ),
        AttributionRow(
            "gave_up", Match(ObservationKind.CLIENT_ERROR), INFRASTRUCTURE, redispatch=True
        ),
        AttributionRow("never_sent", Match(ObservationKind.REFUSED_BEFORE_SEND), INFRASTRUCTURE),
    )
)
ANSWER = CompleteResponse("end_turn", 840, 0)
THROTTLE = ServiceError(429, "ThrottlingException", None, "too many requests")
REJECTED = ServiceError(400, "ValidationException", None, "a malformed request")
TIMEOUT = ClientError(ClientErrorKind.TIMEOUT, "timeout")
CALL = ModelCallId("call-1")


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def sent(number: int, observation: Observation, kind: AttributionKind, rule: str) -> Dispatch:
    """Dispatch ``number`` of the first call, recorded as read ``kind`` by ``rule``."""
    made = dispatch(1, observation, kind, number=number)
    return replace(made, attribution=Attribution(kind, rule))


def as_the_table_reads(number: int, observation: Observation) -> Dispatch:
    reading, _ = attribute(TABLE, observation)
    return sent(number, observation, reading.kind, reading.rule)


def call(*dispatches: Dispatch) -> ModelCall:
    return ModelCall(CALL, ROLE, dispatches, None)


def findings(*dispatches: Dispatch, policy: RedispatchPolicy | None = None) -> list[object]:
    check = check_attributions(TABLE, policy, (call(*dispatches),))
    assert check.dispatches == len(dispatches)
    return [(finding.kind, finding.dispatch) for finding in check.findings]


# --- The reading -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "observation",
    [ANSWER, BrokenStream("reset"), THROTTLE, REJECTED, TIMEOUT, RefusedBeforeSend("no body")],
    ids=lambda observation: type(observation).__name__,
)
def test_a_dispatch_recorded_as_the_table_reads_it_has_no_finding(observation: Observation) -> None:
    assert findings(as_the_table_reads(1, observation)) == []


def test_a_defect_row_is_held_to_its_match_and_taken_at_its_word_for_the_cause() -> None:
    # The export holds the rule and not the cause the harness supplied: a service error
    # recorded under the defect row is a reading the table gives, with that row's cause.
    assert findings(sent(1, REJECTED, DEFECT, "own_request")) == []
    # The row reads a service error; a timeout under it is no reading of the table's.
    assert findings(sent(1, TIMEOUT, DEFECT, "own_request")) == [(KINDS.RULE_NOT_THE_TABLES, 1)]


def test_a_rule_the_table_does_not_give_the_observation_is_a_finding() -> None:
    # No such row.
    assert findings(sent(1, ANSWER, BEHAVIOUR, "a-rule")) == [(KINDS.RULE_NOT_THE_TABLES, 1)]
    # A row that exists, and an earlier one takes a 429 before it.
    assert findings(sent(1, THROTTLE, INFRASTRUCTURE, "any_error")) == [
        (KINDS.RULE_NOT_THE_TABLES, 1)
    ]
    # A row of another kind of observation.
    assert findings(sent(1, TIMEOUT, INFRASTRUCTURE, "stream")) == [(KINDS.RULE_NOT_THE_TABLES, 1)]


def test_a_kind_that_is_not_its_rows_reading_is_a_finding() -> None:
    assert findings(sent(1, THROTTLE, BEHAVIOUR, "throttled")) == [(KINDS.READING_NOT_THE_RULES, 1)]


def test_no_recorded_outcome_is_read_by_no_row_under_its_own_rule() -> None:
    assert findings(sent(1, NoRecordedOutcome(), UNRESOLVED, UNRESOLVED_RULE)) == []
    # Under any other rule it does not construct, so there is no such record to find.
    with pytest.raises(ValueError, match="an unresolved dispatch names the rule"):
        sent(1, NoRecordedOutcome(), UNRESOLVED, "never_sent")


# --- What followed ---------------------------------------------------------------------------


def test_a_dispatch_followed_by_another_names_a_row_that_allows_one() -> None:
    again = as_the_table_reads(2, ANSWER)
    assert findings(as_the_table_reads(1, THROTTLE), again) == []
    assert findings(as_the_table_reads(1, REJECTED), again) == [
        (KINDS.REDISPATCHED_AGAINST_ITS_ROW, 1)
    ]
    # Nothing shows an unresolved dispatch was sent: asking again is always allowed.
    assert findings(sent(1, NoRecordedOutcome(), UNRESOLVED, UNRESOLVED_RULE), again) == []
    # A rule the table does not hold is reported once, as the rule.
    assert findings(sent(1, THROTTLE, INFRASTRUCTURE, "a-rule"), again) == [
        (KINDS.RULE_NOT_THE_TABLES, 1)
    ]
    # The row that decides is the table's for the observation. A rejected request
    # recorded under the throttle's rule was still dispatched again where the table allows
    # none, and a throttle recorded under the unmatched rule was not.
    assert findings(sent(1, REJECTED, INFRASTRUCTURE, "throttled"), again) == [
        (KINDS.RULE_NOT_THE_TABLES, 1),
        (KINDS.REDISPATCHED_AGAINST_ITS_ROW, 1),
    ]
    assert findings(sent(1, THROTTLE, INFRASTRUCTURE, "any_error"), again) == [
        (KINDS.RULE_NOT_THE_TABLES, 1)
    ]
    # The last dispatch was followed by nothing, whatever its row allows.
    assert findings(as_the_table_reads(1, REJECTED)) == []


def test_a_call_holds_no_more_dispatches_than_the_bound_when_one_is_set() -> None:
    three = (
        as_the_table_reads(1, THROTTLE),
        as_the_table_reads(2, TIMEOUT),
        as_the_table_reads(3, ANSWER),
    )
    assert findings(*three, policy=RedispatchPolicy(3, 1_000)) == []
    assert findings(*three, policy=RedispatchPolicy(2, 1_000)) == [
        (KINDS.MORE_DISPATCHES_THAN_THE_BOUND, None)
    ]
    unbounded = check_attributions(TABLE, None, (call(*three),))
    assert (unbounded.bound_evaluated, unbounded.findings) == (False, ())


def test_the_format_cases_carry_no_finding_under_a_table_holding_their_rules() -> None:
    read = 0
    for name, build in FIXTURES.items():
        check = check_attributions(FIXTURE_TABLE, FIXTURE_POLICY, build().trace.model_calls)
        assert check.findings == (), name
        read += check.dispatches
    # Sixteen exports, two with no dispatch, one with two dispatches of one call and one with
    # three dispatches over two calls.
    assert read == 17


# --- Where it is evaluated -------------------------------------------------------------------


def under(world: SealedWorld, recorded: Dispatch, *, table: str | None = None) -> RunExport:
    """An agent's export whose one call ended on ``recorded``, a timed-out send, its record
    naming ``table`` (this module's by default)."""
    failure = Failure(
        FailureCategory.INFRASTRUCTURE,
        DispatchSite(CALL, 1, DispatchPhase.SEND),
        "the provider timed out",
    )
    export = agent_export(world, world.scenarios[0], (call(recorded),), failure=failure)
    digest = attribution_table_digest(TABLE) if table is None else table
    return replace(export, record=replace(export.record, attribution_table=digest))


def test_the_check_is_evaluated_only_for_a_run_whose_record_names_the_table(
    world: SealedWorld,
) -> None:
    conforming = under(world, as_the_table_reads(1, TIMEOUT))
    read = evaluate_run(world, conforming, table=TABLE).metrics.attribution
    assert read == AttributionCheck(1, False, ())
    bounded = evaluate_run(world, conforming, table=TABLE, redispatch=RedispatchPolicy(2, 0))
    assert bounded.metrics.attribution == AttributionCheck(1, True, ())
    misread = under(world, sent(1, TIMEOUT, INFRASTRUCTURE, "a-rule"))
    assert evaluate_run(world, misread, table=TABLE).metrics.attribution == AttributionCheck(
        1, False, (AttributionFinding(KINDS.RULE_NOT_THE_TABLES, CALL, 1),)
    )
    # No table at hand, a record that names another table, and a record that names none.
    assert evaluate_run(world, misread).metrics.attribution is None
    another = under(world, sent(1, TIMEOUT, INFRASTRUCTURE, "a-rule"), table="f" * 64)
    assert evaluate_run(world, another, table=TABLE).metrics.attribution is None
    rules_only = run_export(world, world.scenarios[0])
    assert evaluate_run(world, rules_only, table=TABLE).metrics.attribution is None


def test_a_misread_run_and_one_held_to_no_table_are_counted_apart(world: SealedWorld) -> None:
    plan = preregistered(light(decided(named(DRAFT), True))).plan
    misread = under(world, sent(1, TIMEOUT, INFRASTRUCTURE, "a-rule"))
    conforming = replace(under(world, as_the_table_reads(1, TIMEOUT)), run_id="run-9")
    unheld = replace(misread, run_id="run-10")
    runs = [
        evaluate_run(world, misread, table=TABLE),
        evaluate_run(world, conforming, table=TABLE),
        evaluate_run(world, unheld),
    ]
    (arm,) = (held for held in arms(world, runs, plan) if not held.registered)
    whole = cells_of(arm)[0]
    for counts in (accounting_of(whole, plan), attempt_summary_of(whole)):
        assert (counts.with_attribution_findings, counts.attribution_not_evaluated) == (1, 1)
