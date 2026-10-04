"""How an attempt ended and what stood behind its claims: the failure's site, an abandonment,
the reservation, the approval, the composition.

These are the statements an export makes about its own ending that format 1 could not make
(the contract step's rulings on failures, the reservation, approval and authorship).

*Where a failure is.* Format 1 anchored a failure at an operation or at a model call the
provider failed, and a database outage, a checkpoint that will not resume or an abandoned
attempt had no truthful place. A site is now one of three: an operation; a model dispatch,
by its call, its number and the phase the fault was found in; or a harness site from a
closed list. Admission is not on the list: a refused admission creates no attempt and is
the ledger's record.

*Abandonment is a decision, not an absence.* A run paused at an approval or recoverable
from a checkpoint has no terminal event and is not abandoned. An attempt is abandoned by
an explicit event naming the authority that decided it and the ownership generation it
fenced, so a stale worker can neither dispatch nor append afterwards.

*The reservation.* A run is admitted against a reserved worst-case amount, allocated to
its dispatches. The export says what became of it: reconciled against the observed cost,
or kept with the reason, under the ledger revision it was settled at. Keeping and
reconciling are the ledger's; this is where the export states the result, so an auditor
can check that known consumption plus retained allocations stayed inside the allowance.

*The approval.* An export is terminal-only, so its approval is one of three states: not
requested; requested and unapproved at termination; approved, by the automatic policy or a
human. A run waiting for approval is a state of the log and never an export, and absent is
never an approval of an empty set: an abstention's empty payload is approved explicitly. A
requested approval holds the digest of the frozen review payload it was asked over. An
automatic approval is a registered policy's decision, not authorization.

*The composition.* The claims a run ends with were composed by the rules from the run's
view, or written by a model (the authoring arm only). The composition records which, under
which policy, what each admitted requirement's target span bound to, and which admitted
statements the view left out and why: the diagnostics a report shows beside its claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.enums import require_member
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.run_trace import (
    ModelCallId,
    OperationId,
    require_digest,
    require_integer,
    require_opaque_id,
)
from leaveimpact.core.stated import SpanPlacement, StatedFact
from leaveimpact.core.stated_view import Excluded

# --- Where a failure is --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OperationSite:
    """The fault was found at an operation: a record that could not be translated, or
    returned records the harness could not accept."""

    operation: OperationId

    def __post_init__(self) -> None:
        require_opaque_id(self.operation, "the failing operation's id")


class DispatchPhase(StrEnum):
    """Where in a dispatch's life the fault was found; a member is the wire format."""

    BUILD = "build"
    """Rendering or validating the request, before any send."""
    SEND = "send"
    """The send itself: what the dispatch's observation records."""
    PARSE = "parse"
    """Reading a response that had arrived; the response is preserved."""
    RECORD = "record"
    """Recording the outcome of a response that had arrived."""


@dataclass(frozen=True, slots=True)
class DispatchSite:
    """The fault was found at a model dispatch: the call, the dispatch's number, the phase."""

    model_call: ModelCallId
    dispatch: int
    phase: DispatchPhase

    def __post_init__(self) -> None:
        require_opaque_id(self.model_call, "the failing model call's id")
        require_integer(self.dispatch, "the failing dispatch's number", minimum=1)
        require_member(self.phase, DispatchPhase, "a dispatch phase")


class HarnessSiteName(StrEnum):
    """The harness's own failure sites, closed; a member is the wire format."""

    PREFETCH = "prefetch"
    EVENT_APPEND = "event_append"
    CHECKPOINT_RESUME = "checkpoint_resume"
    COMPOSITION = "composition"
    ABANDONED = "abandoned"


@dataclass(frozen=True, slots=True)
class HarnessSite:
    """The fault was the harness's own, at a site from the closed list."""

    site: HarnessSiteName

    def __post_init__(self) -> None:
        require_member(self.site, HarnessSiteName, "a harness site")


type FailureSite = OperationSite | DispatchSite | HarnessSite


@dataclass(frozen=True, slots=True)
class Abandonment:
    """The decision that ended an attempt nobody was going to finish: who decided, and the
    ownership generation the decision fenced."""

    authority: str
    ownership_generation: int

    def __post_init__(self) -> None:
        require_opaque_id(self.authority, "the abandoning authority")
        require_integer(self.ownership_generation, "an ownership generation")


# --- The reservation -----------------------------------------------------------------------


class ReservationState(StrEnum):
    """What became of a run's reservation; a member is the wire format."""

    RECONCILED = "reconciled"
    KEPT = "kept"


class KeptReason(StrEnum):
    """Why a reservation was not replaced by the observed cost; a member is the wire format."""

    USAGE_INCOMPLETE = "usage_incomplete"
    UNRESOLVED_DISPATCH = "unresolved_dispatch"


@dataclass(frozen=True, slots=True)
class Reservation:
    """The amount reserved at admission, in pico-dollars, and what became of it.

    >>> Reservation(5_000_000, ReservationState.KEPT, None, 12)
    Traceback (most recent call last):
    ...
    ValueError: a reason is given exactly for a kept reservation
    """

    pico_usd: int
    state: ReservationState
    kept_reason: KeptReason | None
    ledger_revision: int

    def __post_init__(self) -> None:
        require_integer(self.pico_usd, "a reservation in pico-dollars")
        require_member(self.state, ReservationState, "a reservation's state")
        if (self.kept_reason is not None) != (self.state is ReservationState.KEPT):
            raise ValueError("a reason is given exactly for a kept reservation")
        if self.kept_reason is not None:
            require_member(self.kept_reason, KeptReason, "a kept reservation's reason")
        require_integer(self.ledger_revision, "a ledger revision")


# --- The approval --------------------------------------------------------------------------


class ApprovalState(StrEnum):
    """Where an attempt's approval stood when it terminalized; a member is the wire format."""

    NOT_REQUESTED = "not_requested"
    REQUESTED_UNAPPROVED = "requested_unapproved"
    APPROVED = "approved"


class Approver(StrEnum):
    """Who approved; a member is the wire format."""

    AUTOMATIC = "automatic"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class Approval:
    """The approval of an attempt's review payload, as it stood at termination.

    ``payload_digest`` is the digest of the frozen review payload, held exactly when an
    approval was requested; ``approver`` exactly when it was given.

    >>> Approval(ApprovalState.NOT_REQUESTED, None, None).state.value
    'not_requested'
    >>> Approval(ApprovalState.APPROVED, None, "0" * 64)
    Traceback (most recent call last):
    ...
    ValueError: an approver is named exactly for an approval that was given
    """

    state: ApprovalState
    approver: Approver | None
    payload_digest: str | None

    def __post_init__(self) -> None:
        require_member(self.state, ApprovalState, "an approval's state")
        if (self.approver is not None) != (self.state is ApprovalState.APPROVED):
            raise ValueError("an approver is named exactly for an approval that was given")
        if self.approver is not None:
            require_member(self.approver, Approver, "an approver")
        if (self.payload_digest is not None) != (self.state is not ApprovalState.NOT_REQUESTED):
            raise ValueError("a payload digest is held exactly when an approval was requested")
        if self.payload_digest is not None:
            require_digest(self.payload_digest, "the review payload's digest")


# --- The composition -----------------------------------------------------------------------


class ClaimAuthor(StrEnum):
    """Who composed a claim set; a member is the wire format."""

    RULES = "rules"
    MODEL = "model"


@dataclass(frozen=True, slots=True)
class ComposingPolicy:
    """The policy that composed the claims, by a stable identifier and the digest of its
    canonical specification."""

    identifier: str
    digest: str

    def __post_init__(self) -> None:
        require_opaque_id(self.identifier, "a composing policy identifier")
        require_digest(self.digest, "a composing policy digest")


@dataclass(frozen=True, slots=True)
class RequirementPlacement:
    """What one admitted requirement's target span bound to over what the run read."""

    fact: StatedFact
    placement: SpanPlacement

    def __post_init__(self) -> None:
        if self.fact.predicate is not PredicateName.REQUIRES:
            raise ValueError(
                f"only a requirement has a span to place, got {self.fact.predicate.value}"
            )


@dataclass(frozen=True, slots=True)
class Composition:
    """Who composed the claims and under which policy, with the placements and exclusions
    the composing made. A requirement stated with two target spans is two placements; one
    statement, carrier and span is placed once.
    """

    author: ClaimAuthor
    policy: ComposingPolicy
    placements: tuple[RequirementPlacement, ...]
    exclusions: tuple[Excluded, ...]

    def __post_init__(self) -> None:
        require_member(self.author, ClaimAuthor, "a claim set's author")
        placed = [
            (entry.fact.statement, entry.fact.carrier, entry.fact.target_span)
            for entry in self.placements
        ]
        if len(set(placed)) != len(placed):
            raise ValueError("a requirement's span is placed once")


__all__ = [
    "Abandonment",
    "Approval",
    "ApprovalState",
    "Approver",
    "ClaimAuthor",
    "ComposingPolicy",
    "Composition",
    "DispatchPhase",
    "DispatchSite",
    "FailureSite",
    "HarnessSite",
    "HarnessSiteName",
    "KeptReason",
    "OperationSite",
    "RequirementPlacement",
    "Reservation",
    "ReservationState",
]
