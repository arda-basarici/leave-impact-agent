"""A run's account: what its dispatches hold against its caps, and what may be authorized next.

A model request is authorized before it is sent, on its worst case in tokens and in money,
and that allocation stands until evidence replaces it (the event log step's ruling on the
ledger). The account is the fold of a run's authorizations and outcomes in the order the
log holds them. Three callers run the one function here over the same plain inputs: the
worker before it authorizes a dispatch, the closing event to settle the run's reservation,
and the evaluator, which rebuilds the same sequence from an export and checks every
authorization against the account as it stood before it. A balance checked only at the end
would pass a run that overspent in the middle and was released afterwards.

*One contribution per dispatch*, money and tokens apart, since a price does not determine a
token count and the two are released on different evidence:

- nothing was sent, on evidence (the client refused the request): nothing is held;
- the amount was observed whole (usage priced complete, a count established): the observed
  amount replaces the allocation;
- the amount was observed in part: the allocation is kept, the known part sitting inside
  it and never added to it;
- nothing was observed (no outcome, or an outcome with no usage): the allocation is kept.

A rule under which a send cost nothing zeroes its money and says nothing of its tokens.
How a dispatch was attributed plays no part in any of this.

*A breach* is an observed amount above its allocation. The allocation was claimed as an
upper bound, so a breach means a bound was false; the account then holds the observed
amount, the dispatch is listed, and nothing further is authorized. The run's guarantee,
that its contributions stay inside its allowance, holds while no dispatch is breached and
is not claimed otherwise.

*Authorization.* The loop may not spend the finalization reserve: a loop allocation that
does not fit below it sends the run into finalization, and never past it. A finalization
allocation that does not fit ends the run at its cap, reporting what it holds. A logical
call takes a slot of the call cap when its first dispatch is authorized and keeps it; a
later dispatch of the same call takes none, and nothing gives a slot back, so the call cap
bounds the investigation's model interactions while tokens and money account for every
dispatch. A call keeps the purpose it was first authorized under.

*Settlement.* While an attempt is open its whole reservation is held against the spend
threshold, covering what it may still authorize. When it closes, the reservation is
replaced by the sum of its dispatches' money contributions. The reservation is reconciled
when every send was priced whole and is otherwise kept, the unresolved dispatch named
before incomplete usage when both apply; in both cases the amount charged is that sum.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.enums import require_member
from leaveimpact.core.run_ending import KeptReason, ReservationState
from leaveimpact.core.run_record import Caps
from leaveimpact.core.run_trace import Cost, require_integer, require_opaque_id
from leaveimpact.core.token_counting import TokenCount


class CallPurpose(StrEnum):
    """What a logical call is for; a member is the wire format."""

    LOOP = "loop"
    FINALIZATION = "finalization"


@dataclass(frozen=True, slots=True)
class AccountIntent:
    """One dispatch's authorization: the call and the dispatch's number within it, the
    call's purpose, and the worst case it was authorized on."""

    call: str
    dispatch: int
    purpose: CallPurpose
    allocation_tokens: int
    allocation_pico_usd: int

    def __post_init__(self) -> None:
        require_opaque_id(self.call, "a model call id")
        require_integer(self.dispatch, "a dispatch number", minimum=1)
        require_member(self.purpose, CallPurpose, "a call's purpose")
        require_integer(self.allocation_tokens, "an allocation in tokens")
        require_integer(self.allocation_pico_usd, "an allocation in pico-dollars")


@dataclass(frozen=True, slots=True)
class AccountOutcome:
    """What a dispatch's recorded outcome established about its amounts.

    ``sent`` is false only on evidence that nothing left: the client refused the request.
    ``cost`` is the priced usage, or a complete zero under a zero-cost rule, or ``None``
    when nothing was priced. ``tokens`` is the usage counted under the run's rule, or
    ``None`` when the outcome carried no usage.

    >>> AccountOutcome("call_001", 1, sent=False, cost=Cost(0, True), tokens=None)
    Traceback (most recent call last):
    ...
    ValueError: a request that was never sent has no cost and no tokens
    """

    call: str
    dispatch: int
    sent: bool
    cost: Cost | None
    tokens: TokenCount | None

    def __post_init__(self) -> None:
        require_opaque_id(self.call, "a model call id")
        require_integer(self.dispatch, "a dispatch number", minimum=1)
        if not self.sent and (self.cost is not None or self.tokens is not None):
            raise ValueError("a request that was never sent has no cost and no tokens")


type AccountTransition = AccountIntent | AccountOutcome


class CapResource(StrEnum):
    """What a run is capped in."""

    CALLS = "calls"
    TOKENS = "tokens"
    MONEY = "money"


def _contribution(allocation: int, observed: int | None, whole: bool) -> int:
    if observed is None:
        return allocation
    return observed if whole else max(allocation, observed)


@dataclass(frozen=True, slots=True)
class AccountLine:
    """One dispatch in the account: its authorization and its outcome, if one was recorded."""

    intent: AccountIntent
    outcome: AccountOutcome | None

    @property
    def tokens(self) -> int:
        """The tokens this dispatch holds against the token cap."""
        if self.outcome is None:
            return self.intent.allocation_tokens
        if not self.outcome.sent:
            return 0
        counted = self.outcome.tokens
        return _contribution(
            self.intent.allocation_tokens,
            None if counted is None else counted.tokens,
            counted is not None and counted.established,
        )

    @property
    def pico_usd(self) -> int:
        """The money this dispatch holds against the run's allowance."""
        if self.outcome is None:
            return self.intent.allocation_pico_usd
        if not self.outcome.sent:
            return 0
        cost = self.outcome.cost
        return _contribution(
            self.intent.allocation_pico_usd,
            None if cost is None else cost.pico_usd,
            cost is not None and cost.complete,
        )

    @property
    def breached(self) -> tuple[CapResource, ...]:
        """What was observed above its allocation, a part or the whole."""
        if self.outcome is None:
            return ()
        found: list[CapResource] = []
        counted = self.outcome.tokens
        if counted is not None and counted.tokens > self.intent.allocation_tokens:
            found.append(CapResource.TOKENS)
        cost = self.outcome.cost
        if cost is not None and cost.pico_usd > self.intent.allocation_pico_usd:
            found.append(CapResource.MONEY)
        return tuple(found)

    @property
    def priced_whole(self) -> bool:
        """Whether nothing of this dispatch's money is still an allocation: it was not sent,
        or its cost is complete."""
        if self.outcome is None:
            return False
        return not self.outcome.sent or (
            self.outcome.cost is not None and self.outcome.cost.complete
        )


@dataclass(frozen=True, slots=True)
class RunAccount:
    """The account after some prefix of a run's transitions: one line per dispatch, in the
    order the dispatches were authorized.

    >>> RunAccount().tokens, RunAccount().calls
    (0, 0)
    """

    lines: tuple[AccountLine, ...] = ()

    @property
    def tokens(self) -> int:
        return sum(line.tokens for line in self.lines)

    @property
    def pico_usd(self) -> int:
        return sum(line.pico_usd for line in self.lines)

    @property
    def calls(self) -> int:
        """The call-cap slots taken: the logical calls with at least one authorization."""
        return len({line.intent.call for line in self.lines})

    @property
    def breached(self) -> tuple[AccountLine, ...]:
        return tuple(line for line in self.lines if line.breached)

    @property
    def in_finalization(self) -> bool:
        return any(line.intent.purpose is CallPurpose.FINALIZATION for line in self.lines)

    def purpose_of(self, call: str) -> CallPurpose | None:
        """The purpose ``call`` was first authorized under, ``None`` for a call not yet seen."""
        for line in self.lines:
            if line.intent.call == call:
                return line.intent.purpose
        return None

    def dispatches_of(self, call: str) -> int:
        return sum(1 for line in self.lines if line.intent.call == call)

    def after(self, transition: AccountTransition) -> RunAccount:
        """The account with ``transition`` applied; ``ValueError`` for a sequence no log
        holds: a dispatch numbered out of turn, an outcome for a dispatch never authorized,
        a second outcome for one dispatch."""
        if isinstance(transition, AccountIntent):
            expected = self.dispatches_of(transition.call) + 1
            if transition.dispatch != expected:
                raise ValueError(
                    f"dispatch {transition.dispatch} of {transition.call} is authorized out "
                    f"of turn; its next dispatch is {expected}"
                )
            return RunAccount((*self.lines, AccountLine(transition, None)))
        for index, line in enumerate(self.lines):
            if (line.intent.call, line.intent.dispatch) != (transition.call, transition.dispatch):
                continue
            if line.outcome is not None:
                raise ValueError(
                    f"dispatch {transition.dispatch} of {transition.call} has one outcome; "
                    "a second was given"
                )
            settled = AccountLine(line.intent, transition)
            return RunAccount((*self.lines[:index], settled, *self.lines[index + 1 :]))
        raise ValueError(
            f"an outcome was given for dispatch {transition.dispatch} of {transition.call}, "
            "which was never authorized"
        )


def account_of(transitions: Iterable[AccountTransition]) -> RunAccount:
    """The account of ``transitions``, taken in the order the log holds them."""
    account = RunAccount()
    for transition in transitions:
        account = account.after(transition)
    return account


# --- Authorization -------------------------------------------------------------------------


class AuthorizationDecision(StrEnum):
    """What a requested dispatch meets in the account."""

    AUTHORIZED = "authorized"
    ENTER_FINALIZATION = "enter_finalization"
    """A loop allocation that does not fit below the finalization reserve: the run stops
    investigating and finalizes."""
    AT_CAP = "at_cap"
    """A finalization allocation that does not fit: the run ends at its cap."""
    BREACHED = "breached"
    """A dispatch was observed above its allocation, so nothing further is authorized."""
    LOOP_AFTER_FINALIZATION = "loop_after_finalization"
    """A loop dispatch was requested after the run entered finalization."""
    PURPOSE_CHANGED = "purpose_changed"
    """A later dispatch of a call was requested under another purpose than its first."""


@dataclass(frozen=True, slots=True)
class Authorization:
    """The decision on one requested dispatch, with what it did not fit in when the decision
    is one of the two that turn on room."""

    decision: AuthorizationDecision
    short_of: tuple[CapResource, ...] = ()

    @property
    def authorized(self) -> bool:
        return self.decision is AuthorizationDecision.AUTHORIZED


def authorize(
    account: RunAccount, caps: Caps, allowance_pico_usd: int, request: AccountIntent
) -> Authorization:
    """Whether ``request`` may be authorized over ``account``, the account as it stands
    before the request: under ``caps``, with ``allowance_pico_usd`` the run's reservation.

    The caller holds the attempt's lock, so the account cannot move between this decision
    and the append that records it. A request the decision does not authorize is never
    appended. The request's dispatch number is the account's to check when it is applied.

    >>> from leaveimpact.core.input_bound import RegisteredInputBound
    >>> rule = "input_plus_output_cached_included"
    >>> caps = Caps(4, 1_000, 1, 200, rule, RegisteredInputBound("provider_count", 1))
    >>> loop = AccountIntent("call_001", 1, CallPurpose.LOOP, 900, 50)
    >>> authorize(RunAccount(), caps, 1_000, loop).decision.value
    'enter_finalization'
    """
    require_integer(allowance_pico_usd, "the run's allowance in pico-dollars")
    if account.breached:
        return Authorization(AuthorizationDecision.BREACHED)
    held = account.purpose_of(request.call)
    if held is not None and held is not request.purpose:
        return Authorization(AuthorizationDecision.PURPOSE_CHANGED)
    loop = request.purpose is CallPurpose.LOOP
    if loop and account.in_finalization:
        return Authorization(AuthorizationDecision.LOOP_AFTER_FINALIZATION)
    call_room = caps.call_cap - (caps.finalization_call_reserve if loop else 0)
    token_room = caps.token_cap - (caps.finalization_token_reserve if loop else 0)
    short: list[CapResource] = []
    if held is None and account.calls + 1 > call_room:
        short.append(CapResource.CALLS)
    if account.tokens + request.allocation_tokens > token_room:
        short.append(CapResource.TOKENS)
    if account.pico_usd + request.allocation_pico_usd > allowance_pico_usd:
        short.append(CapResource.MONEY)
    if not short:
        return Authorization(AuthorizationDecision.AUTHORIZED)
    decision = AuthorizationDecision.ENTER_FINALIZATION if loop else AuthorizationDecision.AT_CAP
    return Authorization(decision, tuple(short))


# --- Settlement ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Settlement:
    """What a closed attempt's reservation is replaced by: the amount charged, and whether
    that amount is the run's cost or still holds an allocation, with the reason."""

    charged_pico_usd: int
    state: ReservationState
    kept_reason: KeptReason | None


def settle(account: RunAccount) -> Settlement:
    """The settlement of a closed attempt whose account is ``account``.

    >>> settle(RunAccount())
    Settlement(charged_pico_usd=0, state=<ReservationState.RECONCILED: 'reconciled'>, \
kept_reason=None)
    """
    charged = account.pico_usd
    if any(line.outcome is None for line in account.lines):
        return Settlement(charged, ReservationState.KEPT, KeptReason.UNRESOLVED_DISPATCH)
    if not all(line.priced_whole for line in account.lines):
        return Settlement(charged, ReservationState.KEPT, KeptReason.USAGE_INCOMPLETE)
    return Settlement(charged, ReservationState.RECONCILED, None)


__all__ = [
    "AccountIntent",
    "AccountLine",
    "AccountOutcome",
    "AccountTransition",
    "Authorization",
    "AuthorizationDecision",
    "CallPurpose",
    "CapResource",
    "RunAccount",
    "Settlement",
    "account_of",
    "authorize",
    "settle",
]
