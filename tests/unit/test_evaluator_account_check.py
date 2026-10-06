"""Every authorization a run recorded, replayed over the account as it stood, and what the
run holds against its caps and reservation. The producers there are carry no finding: the
sixteen format fixtures, the never-claimed attempt among them with a settlement at zero
compared with its reservation. A rules-only export records no reservation and is not
evaluated. Each finding kind is reached from a hand-built export, and the decisions a replay
can reach are the four an export can state, since an intent's purpose is read off its
position and no intent after the finalization position is a loop's."""

from dataclasses import replace

import pytest

from leaveimpact.core import (
    Answer,
    AttributionKind,
    Caps,
    CompleteResponse,
    KeptReason,
    ModelCall,
    ModelCallId,
    NoRecordedOutcome,
    PricingBasis,
    ReportedUsage,
    ReservationState,
    RunExport,
    cost_of_reported,
)
from leaveimpact.core.run_account import (
    AccountIntent,
    AccountOutcome,
    AuthorizationDecision,
    CallPurpose,
    CapResource,
    Settlement,
)
from leaveimpact.evaluator.account_check import (
    AccountFinding,
    AccountFindingKind,
    account_transitions,
    check_account,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.unit.export_fixture import (
    ALLOCATION,
    ALLOCATION_TOKENS,
    BASIS,
    METHOD,
    ROLE,
    SELECTION,
    agent_export,
    answered_call,
    dispatch,
    run_export,
)
from tests.unit.format_fixtures import FIXTURES
from tests.unit.throwaway_world import loaded_world

KINDS = AccountFindingKind
DECISIONS = AuthorizationDecision
RULE = "input_plus_output_cached_included"
USAGE = {"inputTokens": 120, "outputTokens": 30, "totalTokens": 150}
ABOVE = {"inputTokens": 5_000, "outputTokens": 100, "totalTokens": 5_100}
"""A usage above the allocation in tokens (5,100 of 4,608) and above the bound in input
(5,000 of 4,096), priced below the money allocation."""
CALL = ModelCallId("call-1")


def priced(usage: dict[str, int]) -> ModelCall:
    """The first call, answered with ``usage`` and priced as the harness prices it."""
    return answered_call(1, usage, cost_of_reported(ReportedUsage(usage), SELECTION, BASIS))


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def one_call(world: SealedWorld, usage: dict[str, int] = USAGE) -> RunExport:
    return agent_export(world, world.scenarios[0], (priced(usage),))


def with_caps(export: RunExport, caps: Caps) -> RunExport:
    return replace(export, record=replace(export.record, caps=caps))


def finalized_at(export: RunExport, position: int) -> RunExport:
    return replace(export, trace=replace(export.trace, finalization_entered=position))


def findings(export: RunExport) -> list[tuple[AccountFindingKind, int | None]]:
    check = check_account(export)
    assert check is not None
    return [(finding.kind, finding.dispatch) for finding in check.findings]


# --- The producers there are -------------------------------------------------------------------


def test_the_format_fixtures_project_into_the_account_and_carry_no_finding() -> None:
    for name, build in FIXTURES.items():
        export = build()
        check = check_account(export)
        assert check is not None, name
        assert check.findings == (), name
        reservation = export.record.reservation
        assert reservation is not None
        assert check.settlement == Settlement(
            reservation.charged_pico_usd, reservation.state, reservation.kept_reason
        ), name


def test_the_projection_reads_purpose_off_the_position_and_tokens_by_the_rule(
    world: SealedWorld,
) -> None:
    export = one_call(world)
    intent, outcome = account_transitions(export)
    assert intent == AccountIntent(CALL, 1, CallPurpose.LOOP, ALLOCATION_TOKENS, ALLOCATION)
    assert isinstance(outcome, AccountOutcome)
    assert (outcome.sent, outcome.cost) == (True, priced(USAGE).dispatches[0].cost)
    # The fixture's basis marks both cache classes absent-as-zero: the count is established.
    assert outcome.tokens is not None
    assert (outcome.tokens.tokens, outcome.tokens.established) == (150, True)
    intent, _ = account_transitions(finalized_at(export, 1_050))
    assert isinstance(intent, AccountIntent) and intent.purpose is CallPurpose.FINALIZATION


def test_a_never_claimed_attempt_settles_at_zero_and_a_rules_only_record_is_not_evaluated(
    world: SealedWorld,
) -> None:
    check = check_account(FIXTURES["an attempt admitted and never claimed"]())
    assert check is not None
    assert (check.tokens, check.pico_usd, check.calls, check.settlement, check.findings) == (
        0,
        0,
        0,
        Settlement(0, ReservationState.RECONCILED, None),
        (),
    )
    rules_only = run_export(world, world.scenarios[0])
    assert rules_only.record.reservation is None
    assert check_account(rules_only) is None


# --- An intent the account would not authorize --------------------------------------------------


def test_a_loop_intent_that_does_not_fit_below_the_reserve_entered_finalization(
    world: SealedWorld,
) -> None:
    # The loop's token room is 4,000; the dispatch was allocated 4,608.
    check = check_account(with_caps(one_call(world), Caps(20, 5_000, 2, 1_000, RULE, METHOD)))
    assert check is not None
    assert check.findings == (
        AccountFinding(
            KINDS.INTENT_NOT_AUTHORIZED,
            CALL,
            1,
            DECISIONS.ENTER_FINALIZATION,
            (CapResource.TOKENS,),
        ),
    )


def test_a_finalization_intent_that_does_not_fit_is_at_the_cap(world: SealedWorld) -> None:
    export = finalized_at(with_caps(one_call(world), Caps(20, 4_000, 2, 0, RULE, METHOD)), 1_050)
    check = check_account(export)
    assert check is not None
    assert check.findings == (
        AccountFinding(
            KINDS.INTENT_NOT_AUTHORIZED, CALL, 1, DECISIONS.AT_CAP, (CapResource.TOKENS,)
        ),
    )


def test_a_dispatch_after_a_breach_is_refused_and_the_breach_is_its_own_finding(
    world: SealedWorld,
) -> None:
    export = agent_export(world, world.scenarios[0], (priced(ABOVE), answered_call(2, USAGE, None)))
    # The second call reports usage the harness did not price: nothing to breach there.
    check = check_account(export)
    assert check is not None
    assert check.findings == (
        AccountFinding(KINDS.INPUT_ABOVE_BOUND, CALL, 1),
        AccountFinding(KINDS.BREACHED, CALL, 1, None, (CapResource.TOKENS,)),
        AccountFinding(KINDS.INTENT_NOT_AUTHORIZED, ModelCallId("call-2"), 1, DECISIONS.BREACHED),
    )
    # The breached dispatch holds its observed count, the other its established 150.
    assert check.tokens == 5_100 + 150


def test_a_call_dispatched_again_across_the_finalization_position_changed_purpose(
    world: SealedWorld,
) -> None:
    unresolved = dispatch(1, NoRecordedOutcome(), AttributionKind.UNRESOLVED)
    cost = cost_of_reported(ReportedUsage(USAGE), SELECTION, BASIS)
    answered = dispatch(
        1,
        CompleteResponse("end_turn", 840, 0),
        AttributionKind.BEHAVIOUR,
        usage=USAGE,
        cost=cost,
        number=2,
    )
    call = ModelCall(CALL, ROLE, (unresolved, answered), Answer(True, (), ()))
    export = agent_export(world, world.scenarios[0], (call,))
    # Dispatch 1's intent is at 1,102 and dispatch 2's at 1,104; finalization between them.
    check = check_account(finalized_at(export, 1_103))
    assert check is not None
    assert check.findings == (
        AccountFinding(KINDS.INTENT_NOT_AUTHORIZED, CALL, 2, DECISIONS.PURPOSE_CHANGED),
    )


# --- Allocations, the bound and the settlement --------------------------------------------------


def test_an_allocation_that_is_not_the_arithmetic_is_found_per_resource(
    world: SealedWorld,
) -> None:
    export = one_call(world)
    call = export.trace.model_calls[0]
    wrong = replace(
        call.dispatches[0], allocation_tokens=ALLOCATION_TOKENS + 1, allocation=ALLOCATION - 1
    )
    miscomputed = replace(
        export, trace=replace(export.trace, model_calls=(replace(call, dispatches=(wrong,)),))
    )
    # The dispatch was priced whole, so the settlement charges its cost, not its allocation.
    assert findings(miscomputed) == [
        (KINDS.TOKEN_ALLOCATION_DIFFERS, 1),
        (KINDS.MONEY_ALLOCATION_DIFFERS, 1),
    ]


def test_a_basis_that_cannot_price_the_worst_case_is_a_finding(world: SealedWorld) -> None:
    # Without a cache-write rate the worst case has no bound; the usage still prices.
    rows = tuple(row for row in BASIS.rows if row.token_class != "cache_write_input_tokens")
    thin = PricingBasis(BASIS.table_digest, BASIS.currency, BASIS.effective_from, rows)
    export = agent_export(world, world.scenarios[0], (priced(USAGE),), basis=thin)
    assert findings(export) == [(KINDS.MONEY_ALLOCATION_UNPRICEABLE, 1)]


def test_an_input_above_its_bound_is_found_on_a_floor_too(world: SealedWorld) -> None:
    # No output counter: the token count is a floor below the allocation, no breach, and
    # the cost is incomplete, so the settlement keeps the allocation on both sides.
    assert findings(one_call(world, {"inputTokens": 4_097})) == [(KINDS.INPUT_ABOVE_BOUND, 1)]
    # No input-side counter at all: nothing to compare.
    assert findings(one_call(world, {"outputTokens": 30})) == []


def test_a_settlement_the_reservation_does_not_state_is_found_by_amount_and_by_state(
    world: SealedWorld,
) -> None:
    export = one_call(world)
    reservation = export.record.reservation
    assert reservation is not None

    def stating(**changes: object) -> RunExport:
        return replace(
            export, record=replace(export.record, reservation=replace(reservation, **changes))
        )

    assert findings(stating(charged_pico_usd=1)) == [(KINDS.CHARGED_DIFFERS, None)]
    kept = stating(state=ReservationState.KEPT, kept_reason=KeptReason.USAGE_INCOMPLETE)
    assert findings(kept) == [(KINDS.RESERVATION_STATE_DIFFERS, None)]


def test_tokens_above_the_cap_and_money_above_the_allowance_are_run_findings(
    world: SealedWorld,
) -> None:
    export = with_caps(one_call(world, ABOVE), Caps(20, 5_000, 2, 0, RULE, METHOD))
    assert findings(export) == [
        (KINDS.INPUT_ABOVE_BOUND, 1),
        (KINDS.BREACHED, 1),
        (KINDS.TOKENS_ABOVE_CAP, None),
    ]
    reservation = export.record.reservation
    assert reservation is not None
    short = replace(
        export, record=replace(export.record, reservation=replace(reservation, pico_usd=0))
    )
    assert [kind for kind, _ in findings(short)] == [
        KINDS.INTENT_NOT_AUTHORIZED,
        KINDS.INPUT_ABOVE_BOUND,
        KINDS.BREACHED,
        KINDS.TOKENS_ABOVE_CAP,
        KINDS.MONEY_ABOVE_ALLOWANCE,
    ]
