"""The account check: every authorization a run recorded, replayed over the account as it stood,
and what the run holds against its caps and its reservation.

A model request is authorized before it is sent, on its worst case in tokens and in money,
and that allocation stands until evidence replaces it; the run's account is the fold of its
authorizations and outcomes in the order the log held them (``core.run_account``, the event
log step's ruling on the ledger). The harness ran that fold under the attempt's lock before
each dispatch. This runs it again from the export, which holds every intent and outcome
with its position, and asks the same function the same question before each recorded
intent: would this have been authorized over the account as it then stood? A balance
checked at the end alone would pass a run that overspent in the middle and was released
afterwards, which is why every prefix is checked and the final figures are reported beside.

The export is projected into the account's transitions and nothing else: one intent per
dispatch, its allocations as recorded and its purpose read off the position at which the
run entered finalization (every intent after it is finalization, every one before it the
loop's); one outcome per dispatch that recorded one, sent unless the client refused the
request, the cost as recorded, the tokens as the registered counting rule reads the raw
usage with the classes the embedded price table proves absent-as-zero for the role's
selection. The fold refuses only a sequence no log holds, a dispatch numbered out of turn
or an outcome for no intent, and the export's constructors already fix numbering and
order, so a refusal here is a construction defect and never a finding.

Findings, per dispatch in the trace's order and then per run:

- *An intent the account would not authorize.* The decision names why: a loop allocation
  that did not fit below the finalization reserve, a finalization allocation that did not
  fit the cap, a dispatch after a breach, a call dispatched again under another purpose.
  The resources short are listed where room decided. The account's sixth decision, a loop
  dispatch after finalization, no export can state: the purpose is read off the position,
  so every intent after the finalization position is finalization, and a call dispatched
  on both sides of it reads as a change of purpose.
- *An allocation that is not the arithmetic.* The token allocation is the bound plus the
  output maximum; the money allocation is the worst case under the role's selection and the
  embedded rates. A basis that cannot price a worst case is its own finding, as a missing
  rate is in the cost check.
- *An input above its bound.* The sum of the reported input-side counters, plain, read from a
  cache and written to one, above the input bound the dispatch rested on. Compared whether
  or not the usage is complete: a floor above the bound is already a breach, whatever the
  missing counters would add. A usage reporting no input-side counter is not compared. The
  account's own breach reads the whole count against the whole allocation, inside which an
  input above its bound can hide under an output below its maximum, so both are made.
- *A breach.* A dispatch observed above its allocation in tokens or in money, by the
  account's own reading.
- *A settlement the reservation does not state.* The charged amount, or the state with its
  reason, recomputed by ``settle`` over the account and compared with the record's.
- *Tokens above the cap, money above the allowance.* The account's final figures, known
  amounts with retained allocations and floors inside them, against the caps and the
  reservation. A replay that found no breach cannot produce either; they are reported
  because the account is what a report reads.

Evaluated for every export whose record holds a reservation, a rules-only export among them
(no dispatch, a settlement at zero compared with the record's). Not evaluated, ``None``,
when the record holds none. Raises nothing for what a record states.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.input_bound import worst_case_tokens
from leaveimpact.core.model_calls import Dispatch, ModelCall, Sends
from leaveimpact.core.pricing import INPUT_SIDE_CLASSES, absent_as_zero, worst_case_cost
from leaveimpact.core.run_account import (
    AccountIntent,
    AccountOutcome,
    AccountTransition,
    AuthorizationDecision,
    CallPurpose,
    CapResource,
    RunAccount,
    Settlement,
    authorize,
    settle,
)
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import PricingSelection, RunRecord
from leaveimpact.core.run_trace import ModelCallId
from leaveimpact.core.token_counting import count_tokens


class AccountFindingKind(StrEnum):
    """What the replay can find; a member is the wire format. The order is append-only."""

    INTENT_NOT_AUTHORIZED = "intent_not_authorized"
    TOKEN_ALLOCATION_DIFFERS = "token_allocation_differs"
    MONEY_ALLOCATION_DIFFERS = "money_allocation_differs"
    MONEY_ALLOCATION_UNPRICEABLE = "money_allocation_unpriceable"
    INPUT_ABOVE_BOUND = "input_above_bound"
    BREACHED = "breached"
    CHARGED_DIFFERS = "charged_differs"
    RESERVATION_STATE_DIFFERS = "reservation_state_differs"
    TOKENS_ABOVE_CAP = "tokens_above_cap"
    MONEY_ABOVE_ALLOWANCE = "money_above_allowance"


@dataclass(frozen=True, slots=True)
class AccountFinding:
    """One finding, by kind and where: the call and the dispatch's number, or neither for
    one about the run. ``decision`` is held for an intent the account would not authorize
    and ``resources`` for that and for a breach, what was short or what was exceeded."""

    kind: AccountFindingKind
    model_call: ModelCallId | None = None
    dispatch: int | None = None
    decision: AuthorizationDecision | None = None
    resources: tuple[CapResource, ...] = ()


@dataclass(frozen=True, slots=True)
class AccountCheck:
    """The run's account after every transition, the settlement it computes, and the
    findings. ``tokens``, ``pico_usd`` and ``calls`` are what the run holds against its
    token cap, its allowance and its call cap."""

    tokens: int
    pico_usd: int
    calls: int
    settlement: Settlement
    findings: tuple[AccountFinding, ...]


def account_transitions(export: RunExport) -> tuple[AccountTransition, ...]:
    """The transitions of ``export``'s run in position order: an intent per dispatch and an
    outcome per dispatch that recorded one, read as the module says."""
    record, trace = export.record, export.trace
    selections = dict(record.pricing_selections)
    entered = trace.finalization_entered
    at: list[tuple[int, AccountTransition]] = []
    for call in trace.model_calls:
        selection = selections.get(call.role)
        zero: frozenset[str] = (
            frozenset() if selection is None else absent_as_zero(selection, record.pricing)
        )
        # A call keeps the purpose it was first authorized under: the one its first
        # dispatch's position gives, whatever the entry's position relative to the rest.
        opened = call.dispatches[0].intent_position
        purpose = (
            CallPurpose.FINALIZATION
            if entered is not None and opened > entered
            else CallPurpose.LOOP
        )
        for dispatch in call.dispatches:
            at.append(
                (
                    dispatch.intent_position,
                    AccountIntent(
                        call.id,
                        dispatch.number,
                        purpose,
                        dispatch.allocation_tokens,
                        dispatch.allocation,
                    ),
                )
            )
            if dispatch.outcome_position is None:
                continue
            sent = dispatch.sends is not Sends.NONE
            tokens = (
                None
                if dispatch.usage is None
                else count_tokens(record.caps.counting_rule, dispatch.usage, zero)
            )
            at.append(
                (
                    dispatch.outcome_position,
                    AccountOutcome(
                        call.id,
                        dispatch.number,
                        sent=sent,
                        cost=dispatch.cost if sent else None,
                        tokens=tokens if sent else None,
                    ),
                )
            )
    return tuple(transition for _, transition in sorted(at, key=lambda item: item[0]))


def check_account(export: RunExport) -> AccountCheck | None:
    """The account of the run ``export`` records, its authorizations replayed, with every
    finding; ``None`` when the record holds no reservation. Raises nothing for what the
    record states."""
    record = export.record
    reservation = record.reservation
    if reservation is None:
        return None
    kinds = AccountFindingKind
    refused: dict[tuple[str, int], tuple[AuthorizationDecision, tuple[CapResource, ...]]] = {}
    entered = export.trace.finalization_entered
    intent_positions = {
        (str(call.id), dispatch.number): dispatch.intent_position
        for call in export.trace.model_calls
        for dispatch in call.dispatches
    }
    account = RunAccount()
    for transition in account_transitions(export):
        if isinstance(transition, AccountIntent):
            position = intent_positions[transition.call, transition.dispatch]
            decision = authorize(
                account,
                record.caps,
                reservation.pico_usd,
                transition,
                finalization_entered=entered is not None and position > entered,
            )
            if not decision.authorized:
                refused[transition.call, transition.dispatch] = (
                    decision.decision,
                    decision.short_of,
                )
        account = account.after(transition)

    selections = dict(record.pricing_selections)
    lines = {(line.intent.call, line.intent.dispatch): line for line in account.lines}
    findings: list[AccountFinding] = []
    for call in export.trace.model_calls:
        for dispatch in call.dispatches:
            key = (call.id, dispatch.number)
            if key in refused:
                decision, short = refused[key]
                findings.append(
                    AccountFinding(
                        kinds.INTENT_NOT_AUTHORIZED, call.id, dispatch.number, decision, short
                    )
                )
            findings.extend(
                AccountFinding(kind, call.id, dispatch.number)
                for kind in _allocation_findings(call, dispatch, selections.get(call.role), record)
            )
            if _input_above_bound(dispatch):
                findings.append(AccountFinding(kinds.INPUT_ABOVE_BOUND, call.id, dispatch.number))
            breached = lines[key].breached
            if breached:
                findings.append(
                    AccountFinding(kinds.BREACHED, call.id, dispatch.number, None, breached)
                )

    settlement = settle(account)
    if settlement.charged_pico_usd != reservation.charged_pico_usd:
        findings.append(AccountFinding(kinds.CHARGED_DIFFERS))
    if (settlement.state, settlement.kept_reason) != (reservation.state, reservation.kept_reason):
        findings.append(AccountFinding(kinds.RESERVATION_STATE_DIFFERS))
    if account.tokens > record.caps.token_cap:
        findings.append(AccountFinding(kinds.TOKENS_ABOVE_CAP, resources=(CapResource.TOKENS,)))
    if account.pico_usd > reservation.pico_usd:
        findings.append(AccountFinding(kinds.MONEY_ABOVE_ALLOWANCE, resources=(CapResource.MONEY,)))
    return AccountCheck(
        account.tokens, account.pico_usd, account.calls, settlement, tuple(findings)
    )


def _allocation_findings(
    call: ModelCall,
    dispatch: Dispatch,
    selection: PricingSelection | None,
    record: RunRecord,
) -> tuple[AccountFindingKind, ...]:
    """How the dispatch's two allocations differ from the arithmetic they were computed by."""
    kinds = AccountFindingKind
    found: list[AccountFindingKind] = []
    if dispatch.allocation_tokens != worst_case_tokens(dispatch.bound, dispatch.output_maximum):
        found.append(kinds.TOKEN_ALLOCATION_DIFFERS)
    if selection is None:
        found.append(kinds.MONEY_ALLOCATION_UNPRICEABLE)
        return tuple(found)
    try:
        expected = worst_case_cost(
            dispatch.bound.input_tokens, dispatch.output_maximum, selection, record.pricing
        )
    except ValueError:
        found.append(kinds.MONEY_ALLOCATION_UNPRICEABLE)
        return tuple(found)
    if dispatch.allocation != expected:
        found.append(kinds.MONEY_ALLOCATION_DIFFERS)
    return tuple(found)


def _input_above_bound(dispatch: Dispatch) -> bool:
    """Whether the input-side counters the dispatch's usage reports sum above its bound; a
    usage reporting none of them is not compared."""
    if dispatch.usage is None:
        return False
    reported = [
        value
        for value in (dispatch.usage.counters.value(name) for name in INPUT_SIDE_CLASSES)
        if value is not None
    ]
    return bool(reported) and sum(reported) > dispatch.bound.input_tokens


__all__ = [
    "AccountCheck",
    "AccountFinding",
    "AccountFindingKind",
    "account_transitions",
    "check_account",
]
