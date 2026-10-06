"""Every bound held to the count it names, every count to its outcome, every group of counts
to the rule it was retried under. The sixteen format fixtures carry no finding under their
table and policy; each finding kind is reached from a hand-built export; the two
registration parts are marked not evaluated without a policy and the identifiers."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    CountingOperation,
    CountingOperationId,
    CountResult,
    CountServiceError,
    InputBoundSite,
    ModelCallId,
    RunExport,
    cost_of_reported,
)
from leaveimpact.core.attribution import RedispatchPolicy
from leaveimpact.core.input_bound import CountDecision
from leaveimpact.core.usage import ReportedUsage
from leaveimpact.evaluator.count_check import (
    CountCheck,
    CountFinding,
    CountFindingKind,
    check_counts,
    reuse_key,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit.export_fixture import (
    BASIS,
    COUNTING_MODEL,
    INPUT_BOUND,
    METHOD,
    ROLE,
    SELECTION,
    agent_export,
    answered_call,
    count_of,
    request_digest,
    run_export,
)
from tests.unit.format_fixtures import FIXTURES, POLICY
from tests.unit.throwaway_world import loaded_world

KINDS = CountFindingKind
USAGE = {"inputTokens": 120, "outputTokens": 30, "totalTokens": 150}
COST = cost_of_reported(ReportedUsage(USAGE), SELECTION, BASIS)
IDENTIFIERS = {ROLE: COUNTING_MODEL}
CALL = ModelCallId("call-1")


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def one_call(world: SealedWorld) -> RunExport:
    return agent_export(world, world.scenarios[0], (answered_call(1, USAGE, COST),))


def with_counts(export: RunExport, *counts: CountingOperation) -> RunExport:
    return replace(export, trace=replace(export.trace, counting_operations=counts))


def with_bound(export: RunExport, **changes: object) -> RunExport:
    call = export.trace.model_calls[0]
    dispatch = call.dispatches[0]
    bound = replace(dispatch.bound, **changes)
    rebuilt = replace(call, dispatches=(replace(dispatch, bound=bound),))
    return replace(export, trace=replace(export.trace, model_calls=(rebuilt,)))


def failed_count(
    id: str, start: int, reading: CountResult = CountResult.FAILED
) -> CountingOperation:
    """A throttled counting request for the first call's request, at ``start``."""
    return CountingOperation(
        CountingOperationId(id),
        METHOD,
        COUNTING_MODEL,
        request_digest(1),
        1,
        start,
        start + 1,
        CountServiceError(429, "ThrottlingException", "rate exceeded", None, 80),
        reading,
    )


def kinds(export: RunExport, policy: RedispatchPolicy | None = POLICY) -> list[CountFindingKind]:
    return [finding.kind for finding in check_counts(export, policy, IDENTIFIERS).findings]


# --- The producers there are -------------------------------------------------------------------


def test_the_format_fixtures_carry_no_finding_under_their_table_and_policy() -> None:
    operations = dispatches = 0
    for name, build in FIXTURES.items():
        check = check_counts(build(), POLICY, IDENTIFIERS)
        assert (check.registration_evaluated, check.findings) == (True, ()), name
        operations += check.operations
        dispatches += check.dispatches
    # Sixteen exports: fourteen with one count per call, one with two calls, one with three
    # failed counts and no dispatch, one with nothing.
    assert (operations, dispatches) == (18, 17)


def test_a_rules_only_export_reads_nothing_and_is_evaluated(world: SealedWorld) -> None:
    assert check_counts(run_export(world, world.scenarios[0]), POLICY, {}) == CountCheck(
        0, 0, True, ()
    )


def test_the_registration_parts_are_marked_not_evaluated_without_both_values(
    world: SealedWorld,
) -> None:
    export = one_call(world)
    assert check_counts(export, None, IDENTIFIERS).registration_evaluated is False
    assert check_counts(export, POLICY, None).registration_evaluated is False
    assert check_counts(export, POLICY, IDENTIFIERS).registration_evaluated is True


# --- Per dispatch, against the count its bound names ----------------------------------------------


def test_a_bound_resting_on_a_count_that_did_not_count(world: SealedWorld) -> None:
    export = with_counts(one_call(world), failed_count("count-1", 1_100))
    assert kinds(export) == [KINDS.COUNT_DID_NOT_COUNT]


def test_a_count_whose_outcome_came_after_the_intent(world: SealedWorld) -> None:
    # The dispatch's intent is at 1,102; a count answered at 1,111 was not its evidence.
    late = replace(count_of(1), start_position=1_110, outcome_position=1_111)
    assert kinds(with_counts(one_call(world), late)) == [KINDS.COUNT_AFTER_INTENT]


def test_a_count_or_a_bound_covering_another_request(world: SealedWorld) -> None:
    other = replace(count_of(1), request_digest=request_digest(2))
    assert kinds(with_counts(one_call(world), other)) == [KINDS.COUNT_COVERS_ANOTHER_REQUEST]
    assert kinds(with_bound(one_call(world), request_digest=request_digest(2))) == [
        KINDS.COUNT_COVERS_ANOTHER_REQUEST
    ]


def test_a_bound_that_is_not_the_count_returned(world: SealedWorld) -> None:
    assert kinds(with_bound(one_call(world), input_tokens=INPUT_BOUND + 1)) == [
        KINDS.BOUND_NOT_THE_COUNT
    ]


def test_a_bounds_identifier_that_is_not_the_counts_is_also_not_the_registered_one(
    world: SealedWorld,
) -> None:
    assert kinds(with_bound(one_call(world), counting_identifier="another-base")) == [
        KINDS.BOUND_IDENTIFIER_DIFFERS
    ]
    # The count itself asked another identifier than the role registers.
    asked = replace(count_of(1), counting_identifier="another-base")
    assert kinds(with_counts(one_call(world), asked)) == [
        KINDS.BOUND_IDENTIFIER_DIFFERS,
        KINDS.IDENTIFIER_NOT_REGISTERED,
    ]


# --- Per counting operation ---------------------------------------------------------------------


def test_a_reading_that_is_not_what_the_outcome_gives(world: SealedWorld) -> None:
    # A denial read as transient: the misreading the stored reading exists to show.
    denied = CountingOperation(
        CountingOperationId("count-9"),
        METHOD,
        COUNTING_MODEL,
        request_digest(9),
        1,
        1_900,
        1_901,
        CountServiceError(403, "AccessDeniedException", "not allowed", None, 90),
        CountResult.FAILED,
    )
    export = with_counts(one_call(world), count_of(1), denied)
    check = check_counts(export, POLICY, IDENTIFIERS)
    assert check.findings == (
        CountFinding(KINDS.READING_NOT_THE_OUTCOMES, counting_operation=denied.id),
    )


def test_an_unreferenced_count_is_held_to_the_set_of_registered_identifiers(
    world: SealedWorld,
) -> None:
    stray = replace(
        failed_count("count-7", 1_700),
        counting_identifier="another-base",
        request_digest=request_digest(7),
    )
    export = with_counts(one_call(world), count_of(1), stray)
    assert kinds(export) == [KINDS.IDENTIFIER_NOT_REGISTERED]
    assert check_counts(export, POLICY, None).findings == ()


# --- Per group, under the reuse key -------------------------------------------------------------


def test_a_count_made_when_the_decision_was_not_to_count(world: SealedWorld) -> None:
    export = one_call(world)
    again = replace(
        count_of(1),
        id=CountingOperationId("count-1b"),
        start_position=1_150,
        outcome_position=1_151,
    )
    after_a_count = with_counts(export, count_of(1), again)
    check = check_counts(after_a_count, POLICY, IDENTIFIERS)
    assert check.findings == (
        CountFinding(
            KINDS.COUNT_NOT_PERMITTED, counting_operation=again.id, decision=CountDecision.USE
        ),
    )
    # Three transient failures under a maximum of three, then a fourth count.
    fourth = [failed_count(f"retry-{n}", 1_010 + 10 * n) for n in range(1, 4)] + [
        replace(count_of(1), start_position=1_090, outcome_position=1_091)
    ]
    exhausted = with_counts(export, *fourth)
    check = check_counts(exhausted, RedispatchPolicy(3, 0), IDENTIFIERS)
    assert [(f.kind, f.decision) for f in check.findings] == [
        (KINDS.COUNT_NOT_PERMITTED, CountDecision.EXHAUSTED)
    ]
    assert check_counts(exhausted, None, IDENTIFIERS).findings == ()


def test_the_groups_are_by_reuse_key_so_two_requests_are_two_groups(world: SealedWorld) -> None:
    export = agent_export(
        world,
        world.scenarios[0],
        (answered_call(1, USAGE, COST), answered_call(2, USAGE, COST)),
    )
    assert {reuse_key(count) for count in export.trace.counting_operations} == {
        (request_digest(1), COUNTING_MODEL, METHOD),
        (request_digest(2), COUNTING_MODEL, METHOD),
    }
    assert kinds(export) == []


# --- The ending at the input bound --------------------------------------------------------------


def test_a_failure_at_the_input_bound_names_its_groups_last_count_and_an_exhausted_group(
    world: SealedWorld,
) -> None:
    export = FIXTURES["a request whose input bound was never established"]()
    assert kinds(export) == []
    failure = export.record.failure
    assert failure is not None
    # Named: the first of the three, not the last.
    early = replace(failure, site=InputBoundSite(CountingOperationId("count-1")))
    misnamed = replace(export, record=replace(export.record, failure=early))
    assert kinds(misnamed) == [KINDS.SITE_NOT_THE_LAST_COUNT]
    # Two of three consumed: the harness gave up while it could still count.
    two = export.trace.counting_operations[:2]
    gave_up = replace(
        export,
        record=replace(export.record, failure=replace(failure, site=InputBoundSite(two[-1].id))),
        trace=replace(export.trace, counting_operations=two),
    )
    assert [(f.kind, f.decision) for f in check_counts(gave_up, POLICY, IDENTIFIERS).findings] == [
        (KINDS.ENDED_WHILE_COUNT_PERMITTED, CountDecision.COUNT)
    ]
    assert kinds(gave_up, policy=None) == []
