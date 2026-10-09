"""The run's account: one contribution per dispatch, money and tokens released on their own
evidence; an observed amount above its allocation is a breach after which nothing is
authorized; the loop never spends the finalization reserve and a refused loop allocation
enters finalization, after which no loop call opens and one in progress finishes from the
reserve; a call takes one slot whatever its dispatches; every prefix is
checked and not the final balance; and a closed attempt is charged its contributions."""

import pytest

from leaveimpact.core.input_bound import RegisteredInputBound
from leaveimpact.core.run_account import (
    AccountFigures,
    AccountIntent,
    AccountOutcome,
    AccountTransition,
    Authorization,
    AuthorizationDecision,
    CallPurpose,
    CapResource,
    RunAccount,
    account_of,
    authorize,
    figures_of,
    settle,
)
from leaveimpact.core.run_ending import KeptReason, ReservationState
from leaveimpact.core.run_record import Caps
from leaveimpact.core.run_trace import Cost
from leaveimpact.core.token_counting import INPUT_PLUS_OUTPUT_CACHED_INCLUDED, TokenCount

LOOP, FINAL = CallPurpose.LOOP, CallPurpose.FINALIZATION
CALLS, TOKENS, MONEY = CapResource.CALLS, CapResource.TOKENS, CapResource.MONEY
AUTHORIZED = AuthorizationDecision.AUTHORIZED
METHOD = RegisteredInputBound("provider_count", 1)
CAPS = Caps(5, 10_000, 2, 2_000, INPUT_PLUS_OUTPUT_CACHED_INCLUDED, METHOD)
"""Five calls and 10,000 tokens, two calls and 2,000 tokens of them the finalization's: the
loop has three calls and 8,000 tokens."""
ALLOWANCE = 1_000_000


def intent(
    call: int, dispatch: int = 1, tokens: int = 1_000, pico: int = 100, purpose: CallPurpose = LOOP
) -> AccountIntent:
    return AccountIntent(f"call_{call:03d}", dispatch, purpose, tokens, pico)


def outcome(
    call: int,
    dispatch: int = 1,
    *,
    cost: Cost | None = None,
    tokens: TokenCount | None = None,
    sent: bool = True,
) -> AccountOutcome:
    return AccountOutcome(f"call_{call:03d}", dispatch, sent, cost, tokens)


def answered(call: int, dispatch: int = 1, tokens: int = 400, pico: int = 40) -> AccountOutcome:
    """An outcome observed whole in both."""
    return outcome(call, dispatch, cost=Cost(pico, True), tokens=TokenCount(tokens, True))


def held(*transitions: AccountTransition) -> tuple[int, int]:
    account = account_of(transitions)
    return account.tokens, account.pico_usd


# --- One contribution per dispatch ---------------------------------------------------------


def test_an_authorized_dispatch_with_no_outcome_holds_its_allocation() -> None:
    assert held(intent(1)) == (1_000, 100)


def test_an_amount_observed_whole_replaces_its_allocation() -> None:
    assert held(intent(1), answered(1)) == (400, 40)


def test_a_request_that_was_never_sent_holds_nothing() -> None:
    assert held(intent(1), outcome(1, sent=False)) == (0, 0)


def test_an_outcome_with_no_usage_keeps_both_allocations() -> None:
    assert held(intent(1), outcome(1)) == (1_000, 100)


def test_a_zero_cost_rule_zeroes_the_money_and_keeps_the_tokens() -> None:
    assert held(intent(1), outcome(1, cost=Cost(0, True))) == (1_000, 0)


def test_a_floor_sits_inside_its_allocation_and_is_never_added_to_it() -> None:
    partial = outcome(1, cost=Cost(30, False), tokens=TokenCount(300, False))
    assert held(intent(1), partial) == (1_000, 100)


def test_money_and_tokens_are_released_apart() -> None:
    priced_not_counted = outcome(1, cost=Cost(40, True), tokens=TokenCount(400, False))
    assert held(intent(1), priced_not_counted) == (1_000, 40)
    counted_not_priced = outcome(1, cost=Cost(40, False), tokens=TokenCount(400, True))
    assert held(intent(1), counted_not_priced) == (400, 100)


def test_each_dispatch_of_a_call_is_its_own_contribution() -> None:
    account = account_of([intent(1), outcome(1), intent(1, 2), answered(1, 2)])
    assert (account.tokens, account.pico_usd) == (1_000 + 400, 100 + 40)
    assert account.calls == 1
    assert account.dispatches_of("call_001") == 2


# --- Sequences no log holds ----------------------------------------------------------------


def test_a_dispatch_numbered_out_of_turn_is_refused() -> None:
    with pytest.raises(ValueError, match="authorized out of turn; its next dispatch is 1"):
        account_of([intent(1, 2)])
    with pytest.raises(ValueError, match="its next dispatch is 2"):
        account_of([intent(1), intent(1)])


def test_an_outcome_needs_its_authorization_and_is_given_once() -> None:
    with pytest.raises(ValueError, match="which was never authorized"):
        account_of([answered(1)])
    with pytest.raises(ValueError, match="has one outcome; a second was given"):
        account_of([intent(1), answered(1), answered(1)])


def test_the_account_is_unchanged_by_applying_a_transition_to_it() -> None:
    before = account_of([intent(1)])
    after = before.after(answered(1))
    assert before.tokens == 1_000
    assert after.tokens == 400


# --- Breach --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("observed", "resources", "holds"),
    [
        (outcome(1, cost=Cost(40, True), tokens=TokenCount(1_001, True)), (TOKENS,), (1_001, 40)),
        (outcome(1, cost=Cost(101, True), tokens=TokenCount(400, True)), (MONEY,), (400, 101)),
        (
            outcome(1, cost=Cost(150, False), tokens=TokenCount(1_500, False)),
            (TOKENS, MONEY),
            (1_500, 150),
        ),
    ],
    ids=["tokens whole", "money whole", "both, on a floor"],
)
def test_an_observed_amount_above_its_allocation_is_held_as_observed_and_listed(
    observed: AccountOutcome, resources: tuple[CapResource, ...], holds: tuple[int, int]
) -> None:
    account = account_of([intent(1), observed])
    assert [line.breached for line in account.breached] == [resources]
    assert (account.tokens, account.pico_usd) == holds


def test_an_amount_equal_to_its_allocation_is_no_breach() -> None:
    exact = outcome(1, cost=Cost(100, True), tokens=TokenCount(1_000, True))
    assert account_of([intent(1), exact]).breached == ()


def test_nothing_is_authorized_after_a_breach_whatever_room_is_left() -> None:
    breached = account_of(
        [intent(1), outcome(1, cost=Cost(40, True), tokens=TokenCount(1_001, True))]
    )
    for request in (intent(2, tokens=1), intent(2, tokens=1, purpose=FINAL)):
        decision = authorize(breached, CAPS, ALLOWANCE, request, finalization_entered=False)
        assert decision == Authorization(AuthorizationDecision.BREACHED)


# --- Authorization -------------------------------------------------------------------------


def test_a_dispatch_that_fits_is_authorized() -> None:
    assert authorize(
        RunAccount(), CAPS, ALLOWANCE, intent(1), finalization_entered=False
    ).authorized


def test_the_loop_may_fill_its_room_exactly_and_not_one_token_more() -> None:
    account = account_of([intent(1, tokens=7_000)])
    assert authorize(
        account, CAPS, ALLOWANCE, intent(2, tokens=1_000), finalization_entered=False
    ).authorized
    over = authorize(account, CAPS, ALLOWANCE, intent(2, tokens=1_001), finalization_entered=False)
    assert over == Authorization(AuthorizationDecision.ENTER_FINALIZATION, (TOKENS,))


def test_finalization_may_spend_the_reserve_the_loop_could_not() -> None:
    account = account_of([intent(1, tokens=7_000)])
    request = intent(2, tokens=3_000, purpose=FINAL)
    assert authorize(account, CAPS, ALLOWANCE, request, finalization_entered=False).authorized


def test_a_finalization_allocation_that_does_not_fit_ends_the_run_at_its_cap() -> None:
    account = account_of([intent(1, tokens=7_000)])
    request = intent(2, tokens=3_001, purpose=FINAL)
    decision = authorize(account, CAPS, ALLOWANCE, request, finalization_entered=False)
    assert decision == Authorization(AuthorizationDecision.AT_CAP, (TOKENS,))


def test_the_loop_has_the_call_cap_less_the_reserve() -> None:
    three = account_of([intent(1), answered(1), intent(2), answered(2), intent(3), answered(3)])
    fourth = authorize(three, CAPS, ALLOWANCE, intent(4), finalization_entered=False)
    assert fourth == Authorization(AuthorizationDecision.ENTER_FINALIZATION, (CALLS,))
    assert authorize(
        three, CAPS, ALLOWANCE, intent(4, purpose=FINAL), finalization_entered=True
    ).authorized


def test_a_later_dispatch_of_a_call_takes_no_slot() -> None:
    three = account_of([intent(1), answered(1), intent(2), answered(2), intent(3), outcome(3)])
    assert three.calls == 3
    assert authorize(three, CAPS, ALLOWANCE, intent(3, 2), finalization_entered=False).authorized


def test_a_slot_is_not_given_back_by_a_refusal_or_a_release() -> None:
    account = account_of(
        [intent(1), outcome(1, sent=False), intent(2), outcome(2, sent=False), intent(3)]
    )
    assert (account.tokens, account.calls) == (1_000, 3)
    decision = authorize(account, CAPS, ALLOWANCE, intent(4), finalization_entered=False)
    assert decision == Authorization(AuthorizationDecision.ENTER_FINALIZATION, (CALLS,))


def test_finalization_calls_end_at_the_call_cap() -> None:
    transitions: list[AccountTransition] = []
    for call in (1, 2, 3):
        transitions += [intent(call), answered(call)]
    for call in (4, 5):
        transitions += [intent(call, purpose=FINAL), answered(call)]
    decision = authorize(
        account_of(transitions), CAPS, ALLOWANCE, intent(6, purpose=FINAL),
        finalization_entered=True,
    )
    assert decision == Authorization(AuthorizationDecision.AT_CAP, (CALLS,))


def test_money_that_does_not_fit_the_allowance_is_named() -> None:
    account = account_of([intent(1, pico=900)])
    loop = authorize(account, CAPS, 1_000, intent(2, pico=101), finalization_entered=False)
    assert loop == Authorization(AuthorizationDecision.ENTER_FINALIZATION, (MONEY,))
    final = authorize(
        account, CAPS, 1_000, intent(2, pico=101, purpose=FINAL), finalization_entered=True
    )
    assert final == Authorization(AuthorizationDecision.AT_CAP, (MONEY,))
    assert authorize(
        account, CAPS, 1_000, intent(2, pico=100), finalization_entered=False
    ).authorized


def test_everything_a_request_does_not_fit_in_is_named_in_one_order() -> None:
    three = account_of([intent(1, tokens=3_000), intent(2, tokens=3_000), intent(3, tokens=2_000)])
    decision = authorize(three, CAPS, 300, intent(4, tokens=1, pico=1), finalization_entered=False)
    assert decision.short_of == (CALLS, TOKENS, MONEY)


def test_released_room_is_spent_again() -> None:
    account = account_of([intent(1, tokens=8_000), answered(1, tokens=500)])
    assert authorize(
        account, CAPS, ALLOWANCE, intent(2, tokens=7_500), finalization_entered=False
    ).authorized


def test_a_retained_allocation_still_holds_its_room() -> None:
    account = account_of([intent(1, tokens=8_000), outcome(1)])
    decision = authorize(
        account, CAPS, ALLOWANCE, intent(1, 2, tokens=1), finalization_entered=False
    )
    assert decision == Authorization(AuthorizationDecision.ENTER_FINALIZATION, (TOKENS,))


def test_no_loop_call_opens_after_the_entry_into_finalization() -> None:
    account = account_of([intent(1), outcome(1)])
    decision = authorize(account, CAPS, ALLOWANCE, intent(2), finalization_entered=True)
    assert decision == Authorization(AuthorizationDecision.LOOP_AFTER_FINALIZATION)


def test_a_loop_call_in_progress_at_the_entry_finishes_from_the_reserve() -> None:
    """Amendment 2 of the graph step's rulings: the call keeps its loop purpose, its re-dispatch
    is measured against the whole caps once finalization is entered, and one that does not fit
    even so ends the run at its cap."""
    account = account_of([intent(1, tokens=7_000), outcome(1)])
    again = intent(1, 2, tokens=2_000)
    before = authorize(account, CAPS, ALLOWANCE, again, finalization_entered=False)
    assert before == Authorization(AuthorizationDecision.ENTER_FINALIZATION, (TOKENS,))
    assert authorize(account, CAPS, ALLOWANCE, again, finalization_entered=True).authorized
    assert authorize(
        account, CAPS, ALLOWANCE, intent(1, 2, tokens=3_000), finalization_entered=True
    ).authorized
    over = authorize(
        account, CAPS, ALLOWANCE, intent(1, 2, tokens=3_001), finalization_entered=True
    )
    assert over == Authorization(AuthorizationDecision.AT_CAP, (TOKENS,))
    assert account.purpose_of("call_001") is LOOP


def test_a_call_keeps_the_purpose_it_was_first_authorized_under() -> None:
    account = account_of([intent(1), outcome(1)])
    decision = authorize(
        account, CAPS, ALLOWANCE, intent(1, 2, purpose=FINAL), finalization_entered=True
    )
    assert decision == Authorization(AuthorizationDecision.PURPOSE_CHANGED)


def test_a_balance_that_ends_inside_the_cap_can_hide_a_prefix_that_was_not() -> None:
    """Two loop dispatches of 5,000 against a loop room of 8,000: once both are answered at
    400 the account holds 800, and only the check of the second authorization against the
    account before it shows the run was over its room."""
    first, second = intent(1, tokens=5_000), intent(2, tokens=5_000)
    final = account_of([first, second, answered(1), answered(2)])
    assert final.tokens == 800
    assert authorize(RunAccount(), CAPS, ALLOWANCE, first, finalization_entered=False).authorized
    at_second = authorize(account_of([first]), CAPS, ALLOWANCE, second, finalization_entered=False)
    assert at_second == Authorization(AuthorizationDecision.ENTER_FINALIZATION, (TOKENS,))


def test_a_history_whose_every_prefix_is_authorized_stays_inside_its_caps() -> None:
    """The property the account exists for, on a history built by asking it: whatever is
    authorized in turn, with outcomes inside their allocations, never holds more than the
    caps and the allowance at any point."""
    account = RunAccount()
    sizes = [3_000, 2_500, 2_500, 1_500, 900, 900, 400]
    for call, size in enumerate(sizes, start=1):
        request = intent(call, tokens=size, pico=size)
        decision = authorize(account, CAPS, 9_000, request, finalization_entered=False)
        if decision.decision is AuthorizationDecision.ENTER_FINALIZATION:
            request = intent(call, tokens=size, pico=size, purpose=FINAL)
            decision = authorize(account, CAPS, 9_000, request, finalization_entered=False)
        if not decision.authorized:
            continue
        account = account.after(request)
        assert account.tokens <= CAPS.token_cap
        assert account.pico_usd <= 9_000
        assert account.calls <= CAPS.call_cap
        observed = (answered(call), outcome(call), outcome(call, sent=False))[call % 3]
        account = account.after(observed)
    assert not account.breached
    assert account.in_finalization


# --- Settlement ----------------------------------------------------------------------------


def test_a_run_priced_whole_is_reconciled_to_its_cost() -> None:
    account = account_of([intent(1), answered(1, pico=40), intent(2), answered(2, pico=25)])
    settled = settle(account)
    assert (settled.charged_pico_usd, settled.state, settled.kept_reason) == (
        65,
        ReservationState.RECONCILED,
        None,
    )


def test_a_request_never_sent_and_a_zero_cost_send_are_priced_whole() -> None:
    account = account_of(
        [intent(1), outcome(1, sent=False), intent(1, 2), outcome(1, 2, cost=Cost(0, True))]
    )
    assert settle(account).state is ReservationState.RECONCILED
    assert settle(account).charged_pico_usd == 0


def test_incomplete_usage_keeps_the_allocation_in_the_charge() -> None:
    account = account_of(
        [intent(1), answered(1, pico=40), intent(2), outcome(2, cost=Cost(30, False))]
    )
    settled = settle(account)
    assert (settled.charged_pico_usd, settled.state, settled.kept_reason) == (
        140,
        ReservationState.KEPT,
        KeptReason.USAGE_INCOMPLETE,
    )


def test_an_outcome_with_no_usage_and_no_rule_is_kept_as_incomplete() -> None:
    settled = settle(account_of([intent(1), outcome(1)]))
    assert (settled.charged_pico_usd, settled.kept_reason) == (100, KeptReason.USAGE_INCOMPLETE)


def test_an_unresolved_dispatch_is_stated_before_incomplete_usage() -> None:
    account = account_of([intent(1), outcome(1, cost=Cost(30, False)), intent(1, 2)])
    settled = settle(account)
    assert (settled.charged_pico_usd, settled.kept_reason) == (
        200,
        KeptReason.UNRESOLVED_DISPATCH,
    )


def test_a_breached_dispatch_is_charged_what_was_observed() -> None:
    account = account_of([intent(1), outcome(1, cost=Cost(170, True), tokens=TokenCount(9, True))])
    assert settle(account).charged_pico_usd == 170


def test_incomplete_tokens_alone_do_not_keep_the_reservation() -> None:
    account = account_of(
        [intent(1), outcome(1, cost=Cost(40, True), tokens=TokenCount(400, False))]
    )
    assert settle(account).state is ReservationState.RECONCILED


# --- The figures ---------------------------------------------------------------------------


def figures(*transitions: AccountTransition) -> tuple[int, int, int]:
    found = figures_of(account_of(transitions))
    return found.known_pico_usd, found.retained_pico_usd, found.total_pico_usd


def test_an_empty_account_has_nothing_known_and_nothing_retained() -> None:
    assert figures() == (0, 0, 0)


def test_an_unresolved_dispatch_is_retained_whole_and_known_nowhere() -> None:
    assert figures(intent(1)) == (0, 100, 100)


def test_an_amount_priced_whole_is_known_and_retains_nothing() -> None:
    assert figures(intent(1), answered(1)) == (40, 0, 40)


def test_an_amount_priced_in_part_is_known_inside_its_retained_allocation() -> None:
    assert figures(intent(1), outcome(1, cost=Cost(30, False))) == (30, 70, 100)


def test_a_request_never_sent_is_neither_known_nor_retained() -> None:
    assert figures(intent(1), outcome(1, sent=False)) == (0, 0, 0)


def test_a_breached_dispatch_is_known_whole() -> None:
    assert figures(intent(1), outcome(1, cost=Cost(170, True), tokens=TokenCount(9, True))) == (
        170,
        0,
        170,
    )


def test_the_total_is_the_settlement_charge_over_a_mixed_account() -> None:
    account = account_of(
        [intent(1), outcome(1, cost=Cost(30, False)), intent(2), answered(2), intent(3)]
    )
    found = figures_of(account)
    assert (found.known_pico_usd, found.retained_pico_usd) == (70, 170)
    assert found.total_pico_usd == settle(account).charged_pico_usd == account.pico_usd


def test_figures_whose_total_is_not_the_sum_are_refused() -> None:
    with pytest.raises(ValueError, match="the total is the known consumption plus"):
        AccountFigures(1, 2, 4)


# --- The inputs ----------------------------------------------------------------------------


def test_an_outcome_that_was_never_sent_carries_no_amounts() -> None:
    with pytest.raises(ValueError, match="never sent has no cost and no tokens"):
        outcome(1, sent=False, tokens=TokenCount(1, True))


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"dispatch": 0}, "a dispatch number is at least 1"),
        ({"allocation_tokens": -1}, "an allocation in tokens is at least 0"),
        ({"allocation_pico_usd": -1}, "an allocation in pico-dollars is at least 0"),
        ({"purpose": "loop"}, "a call's purpose"),
        ({"call": ""}, "a model call id"),
    ],
)
def test_an_intent_is_refused_outside_its_shape(fields: dict[str, object], message: str) -> None:
    shape: dict[str, object] = {
        "call": "call_001",
        "dispatch": 1,
        "purpose": LOOP,
        "allocation_tokens": 1,
        "allocation_pico_usd": 1,
    }
    with pytest.raises(ValueError, match=message):
        AccountIntent(**{**shape, **fields})  # type: ignore[arg-type]
