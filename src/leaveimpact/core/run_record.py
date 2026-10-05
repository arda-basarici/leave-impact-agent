"""The provenance of one run attempt: what ran, under what, with what, how it ended, what it cost.

The record is the block of a run export that identifies the execution rather than
replaying it (the investigator milestone's second build step, rulings 4 and 5; the
contract step's rulings for format 2). A result is regenerable only from its recorded
inputs, and a comparison between systems is sound only when what was held fixed is on
record, so the record states each of those as a fact the evaluator can read without the
harness: the condition the run observed, the outage and the corpus level it was assigned,
the preregistration it ran under and the attribution table its dispatches were read by,
the model each role called and the prompts and tool surface each role saw, which of the
four systems produced the export and with which retrieval and prefetch rule, the cap it
ran under, how the attempt ended and where it failed, the segments it ran in with their
harness revisions, what became of its reservation and of its approval, and the usage and
cost the provider reported with the pricing that priced it.

Two kinds of statement sit here and are kept apart in the reader's mind. Some fields
are *inputs* the harness set and nobody can derive (the assignment, the caps, the
segments' revisions); others are *claims over the trace* that the evaluator re-derives and
verifies (the observed condition from the failed reads, the usage aggregate from the
dispatches, the cumulative cost from the per-dispatch costs). A claim is stored rather
than left to derivation because a mismatch between the harness's reading and the
replay's is a finding, and only a stored value can mismatch. The constructors here
enforce each block's own shape; the cross-trace checks are the evaluator's.

Absent is a different statement from zero: a usage counter the provider did not report
is unavailable, an aggregate says how many dispatches reported each counter, and a cost
whose counters were incomplete says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from leaveimpact.core.call_settings import CallConfiguration
from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.input_bound import RegisteredInputBound
from leaveimpact.core.run_ending import (
    Abandonment,
    Approval,
    ApprovalState,
    FailureSite,
    HarnessSite,
    HarnessSiteName,
    Reservation,
)
from leaveimpact.core.run_timing import Timing, require_commit
from leaveimpact.core.run_trace import (
    USAGE_COUNTER_NAMES,
    Cost,
    require_digest,
    require_integer,
    require_opaque_id,
)
from leaveimpact.core.token_counting import require_counting_rule

BILLED_ON_EVERY_CALL: tuple[str, ...] = ("input_tokens", "output_tokens")
"""The token classes every answered call is billed for, so a selection's basis must price
them; a cache class is priced only where the table has a rate for it."""

BASE_CORPUS_LEVEL = "base"
"""The corpus level of a world with no filler added. The levels a run may be assigned are
the registration's; this one exists before any registration names them, and a system that
reads no document is recorded under it."""


def _non_negative(value: int, what: str) -> int:
    return require_integer(value, what)


# --- How the attempt ended ---------------------------------------------------------------


class TerminalStatus(StrEnum):
    """How the investigation ended.

    ``COMPLETED`` means the system produced its final claims, the same for every system,
    a refusal or a claimless completion included (graded with its omissions);
    ``CAP_EXHAUSTED`` that it reported what it had at the cap; ``FAILED`` that a defect
    or an infrastructure fault ended it, recorded with the fault.
    """

    COMPLETED = "completed"
    CAP_EXHAUSTED = "cap_exhausted"
    FAILED = "failed"


class FailureCategory(StrEnum):
    """Why a failed attempt failed: the two categories ruling 3d counts apart."""

    DEFECT = "defect"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True, slots=True)
class Failure:
    """The normalized fault of a failed attempt: its category, where it was found, and why.

    ``site`` is an operation, a model dispatch or a harness site, so the fault is recorded
    and not merely counted, and a fault that is no read and no model call still has a
    truthful place.
    """

    category: FailureCategory
    site: FailureSite
    reason: str


# --- What ran ----------------------------------------------------------------------------


class SystemKind(StrEnum):
    """The four systems the evaluator grades from one export shape."""

    AGENT = "agent"
    RULES_ONLY = "rules_only"
    SINGLE_SHOT = "single_shot"
    FULL_CONTEXT = "full_context"


@dataclass(frozen=True, slots=True)
class System:
    """Which system produced the export, and its orchestration variant by a stable identifier."""

    kind: SystemKind
    variant: str

    def __post_init__(self) -> None:
        require_opaque_id(self.variant, "an orchestration variant")


class RetrievalKind(StrEnum):
    """The retrieval implementation behind the document search, held fixed across a comparison."""

    NONE = "none"
    FULL_TEXT = "full_text"
    VECTOR = "vector"


@dataclass(frozen=True, slots=True)
class Retrieval:
    """The retrieval implementation, with its embedding model exactly when it is vector.

    >>> Retrieval(RetrievalKind.FULL_TEXT, "some-embedder")
    Traceback (most recent call last):
    ...
    ValueError: an embedding model is named exactly for vector retrieval
    """

    kind: RetrievalKind
    embedding_model: str | None

    def __post_init__(self) -> None:
        if (self.embedding_model is not None) != (self.kind is RetrievalKind.VECTOR):
            raise ValueError("an embedding model is named exactly for vector retrieval")
        if self.embedding_model is not None:
            require_opaque_id(self.embedding_model, "an embedding model")


@dataclass(frozen=True, slots=True)
class PrefetchRule:
    """The frozen prefetch by a stable identifier and the digest of its canonical specification."""

    identifier: str
    digest: str

    def __post_init__(self) -> None:
        require_opaque_id(self.identifier, "a prefetch rule identifier")
        require_digest(self.digest, "a prefetch rule digest")


@dataclass(frozen=True, slots=True)
class OutageAssignment:
    """The sources scheduled to be unreachable, and the digest of the registered schedule.

    An assignment the run never exercised is not an observed failure: the observed
    condition is derived from the reads that failed, and this is what was scheduled.
    """

    scheduled_unreachable: frozenset[Source]
    schedule_digest: str

    def __post_init__(self) -> None:
        require_digest(self.schedule_digest, "the schedule digest")


@dataclass(frozen=True, slots=True)
class Caps:
    """The per-run cap as it ran, with the finalization reserves inside the totals, and the
    two registered rules the run was held to them by.

    The loop stops before the reserve, finalization may spend it, and the total never
    extends. ``counting_rule`` names which token classes count, a preregistered rule from
    the closed registry (``token_counting.COUNTING_RULES``); ``input_bound`` the method a
    dispatch's input was bounded by before it was authorized, at its registered version
    (``input_bound.INPUT_BOUND_METHODS``). How a worst case is computed changes when a run
    stops at its cap, which is graded, so the method is recorded beside the rule; any name
    the registries lack is refused.

    >>> from leaveimpact.core.input_bound import RegisteredInputBound
    >>> method = RegisteredInputBound("provider_count", 1)
    >>> Caps(20, 100_000, 20, 5_000, "input_plus_output_cached_included", method)
    Traceback (most recent call last):
    ...
    ValueError: the finalization call reserve sits inside the call cap, got 20 of 20
    """

    call_cap: int
    token_cap: int
    finalization_call_reserve: int
    finalization_token_reserve: int
    counting_rule: str
    input_bound: RegisteredInputBound

    def __post_init__(self) -> None:
        for name in ("call_cap", "token_cap"):
            if _non_negative(getattr(self, name), name) == 0:
                raise ValueError(f"{name} is positive")
        _non_negative(self.finalization_call_reserve, "finalization_call_reserve")
        _non_negative(self.finalization_token_reserve, "finalization_token_reserve")
        if self.finalization_call_reserve >= self.call_cap:
            raise ValueError(
                "the finalization call reserve sits inside the call cap, got "
                f"{self.finalization_call_reserve} of {self.call_cap}"
            )
        if self.finalization_token_reserve >= self.token_cap:
            raise ValueError(
                "the finalization token reserve sits inside the token cap, got "
                f"{self.finalization_token_reserve} of {self.token_cap}"
            )
        require_counting_rule(self.counting_rule, "the counting rule")


# --- Usage, cost and pricing -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UsageAggregate:
    """The run's usage summed over the dispatches that reported each counter, with the coverage.

    Each counter is ``(name, value, reported)``: a sum over the dispatches that reported
    it and how many did, beside ``dispatches``, the number there were, and ``model_calls``,
    the logical calls they belong to, so a reader can tell a total from a partial sum. A
    counter no dispatch reported is not a row at all, so absence is never spelled as a
    zero sum over zero dispatches. A run's duration is not usage and sits in its timing.

    >>> UsageAggregate((("input_tokens", 500, 3),), 3, 4).value("input_tokens")
    (500, 3)
    """

    counters: tuple[tuple[str, int, int], ...]
    model_calls: int
    dispatches: int

    def __post_init__(self) -> None:
        _non_negative(self.model_calls, "model_calls")
        _non_negative(self.dispatches, "dispatches")
        if self.dispatches < self.model_calls:
            raise ValueError(
                f"every call holds a dispatch: {self.model_calls} calls, "
                f"{self.dispatches} dispatches"
            )
        names = [name for name, _, _ in self.counters]
        unknown = [name for name in names if name not in USAGE_COUNTER_NAMES]
        if unknown:
            raise ValueError(f"not a usage counter a provider reports: {', '.join(unknown)}")
        if len(set(names)) != len(names):
            raise ValueError("a usage counter is aggregated once")
        declared = [name for name in USAGE_COUNTER_NAMES if name in names]
        if names != declared:
            raise ValueError(f"usage counters are held in the declared order, got {names}")
        for name, value, reported in self.counters:
            _non_negative(value, name)
            require_integer(reported, f"{name} reported", minimum=1)
            if reported > self.dispatches:
                raise ValueError(
                    f"{name}: reported by {reported} dispatches of {self.dispatches}"
                )

    def value(self, name: str) -> tuple[int, int] | None:
        """``(sum, reported)`` for ``name``, or ``None`` when no dispatch reported it."""
        for held, value, reported in self.counters:
            if held == name:
                return value, reported
        return None


class AbsentMeaning(StrEnum):
    """What an unreported counter of this class means under this rate's configuration.

    ``UNKNOWN`` makes the cost incomplete, the default for every rate until a probe
    shows otherwise; ``ZERO`` records that the provider omits the counter exactly when
    the call had no token of that class, a fact proven per model configuration (the
    acceptance spike, build step 7) and written into the table, never assumed in code.
    The fact is about the counter and not about the price, which is why a token count
    reads it too (``pricing.absent_as_zero``): no token of a class means nothing billed
    for it and nothing counted for it, whereas a zero rate would say only the first.
    """

    UNKNOWN = "unknown"
    ZERO = "zero"


@dataclass(frozen=True, slots=True)
class PricingRow:
    """One rate: integer pico-dollars per token for a token class under a pricing key.

    The key, region and billing mode together name a Bedrock rate; a model id alone
    does not (the ``eu.`` profile and on-demand are priced as their own keys).
    ``when_absent`` is the row's policy for a call that did not report this class,
    unknown unless the table says zero.
    """

    pricing_key: str
    region: str
    billing_mode: str
    token_class: str
    pico_usd_per_token: int
    when_absent: AbsentMeaning = AbsentMeaning.UNKNOWN

    def __post_init__(self) -> None:
        for name in ("pricing_key", "region", "billing_mode"):
            require_opaque_id(getattr(self, name), name)
        if self.token_class not in USAGE_COUNTER_NAMES:
            raise ValueError(f"a token class is a usage counter name, got {self.token_class!r}")
        _non_negative(self.pico_usd_per_token, "pico_usd_per_token")

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.pricing_key, self.region, self.billing_mode, self.token_class)


@dataclass(frozen=True, slots=True)
class PricingBasis:
    """The rows of the price table a run's costs were computed from, with the table's identity.

    Embedded rather than referenced so the evaluator verifies the arithmetic from the
    record alone; the digest names the committed table the rows came from. Rows are
    unique by rate and held in key order.
    """

    table_digest: str
    currency: str
    effective_from: date
    rows: tuple[PricingRow, ...]

    def __post_init__(self) -> None:
        require_digest(self.table_digest, "the price table digest")
        if self.currency != "USD":
            raise ValueError(
                f"costs are pico-dollars, so the basis is in USD, got {self.currency!r}"
            )
        keys = [row.key for row in self.rows]
        if len(set(keys)) != len(keys):
            raise ValueError("a rate is given once per pricing key, region, billing mode and class")
        object.__setattr__(self, "rows", tuple(sorted(self.rows, key=lambda row: row.key)))

    def rate(
        self, pricing_key: str, region: str, billing_mode: str, token_class: str
    ) -> int | None:
        """The pico-dollars per token for the named rate, or ``None`` when the basis has none."""
        for row in self.rows:
            if row.key == (pricing_key, region, billing_mode, token_class):
                return row.pico_usd_per_token
        return None


@dataclass(frozen=True, slots=True)
class PricingSelection:
    """The rate a role's calls were priced under: the pricing key, region and billing mode.

    A role's configuration names a model id, and a model id alone does not fix a
    Bedrock rate, so the selection is recorded beside it; with the basis's rows it is
    what lets the evaluator reproduce every per-dispatch cost.
    """

    pricing_key: str
    region: str
    billing_mode: str

    def __post_init__(self) -> None:
        for name in ("pricing_key", "region", "billing_mode"):
            require_opaque_id(getattr(self, name), name)


# --- The record --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunRecord:
    """The provenance block of one run attempt; see the module for what each field states.

    Role-indexed collections are unique by their key and held in key order, so two
    equal records are equal in bytes; the roles that call a model are one set across the
    configurations, the pricing selections, the prompt digests and the tool surfaces.

    How the attempt ended is held together by these ties. ``failure`` is present exactly
    when the status is failed. ``abandonment`` is the abandon command that closed the
    attempt, when one did: a failure at the abandoned site always holds one and is by
    infrastructure, and beside any other site an abandonment is held only for a failure by
    defect, the command having finalized a recorded defect and abandoned nothing (the event
    log step's ruling on recovery and endings). A failure at the ``unhandled`` site is a
    defect. An attempt with no segment was never claimed: it failed at the abandoned site,
    the command fenced generation 0, and no approval was requested. The approval follows
    the status and not the claims, one way: a completed or cap-exhausted attempt holds an
    approval of its frozen review payload, an abstention's empty one included. A failed
    attempt states the approval as it stood, whatever that was: usually none, and a given
    one when the attempt failed after it, at the terminal append or by an abandonment,
    since an export that had to deny an approval the log holds would also have to drop the
    worker's resume and misstate its active time. A worker's approval stamps in the timing
    exist only where the approval says one was requested, or given; an attempt that did not
    fail ended at a terminal event its worker wrote, so its last segment's end was recorded
    and a stamped request has its stamped resume.

    ``attribution_table`` is the digest of the registered table the dispatches' rules are
    identifiers into, and ``reservation`` what became of the amount reserved at admission;
    both are held exactly when a role calls a model. ``cost`` is ``None`` when no dispatch
    was priced, never a zero.
    """

    observed_condition: RunCondition
    outage: OutageAssignment
    corpus_level: str
    preregistration_commit: str
    attribution_table: str | None
    model_configurations: tuple[tuple[str, CallConfiguration], ...]
    pricing_selections: tuple[tuple[str, PricingSelection], ...]
    prompt_digests: tuple[tuple[str, str, str], ...]
    tool_surface_digests: tuple[tuple[str, str], ...]
    system: System
    retrieval: Retrieval
    prefetch_rule: PrefetchRule
    caps: Caps
    status: TerminalStatus
    failure: Failure | None
    abandonment: Abandonment | None
    timing: Timing
    usage: UsageAggregate
    cost: Cost | None
    reservation: Reservation | None
    approval: Approval
    pricing: PricingBasis

    def __post_init__(self) -> None:
        require_opaque_id(self.corpus_level, "the assigned corpus level")
        require_commit(self.preregistration_commit, "the preregistration commit")
        self._require_a_coherent_ending()
        roles = [role for role, _ in self.model_configurations]
        if len(set(roles)) != len(roles):
            raise ValueError(f"a role calls one model configuration, got {roles}")
        for role in roles:
            require_opaque_id(role, "a role")
        if (self.attribution_table is not None) != bool(roles):
            raise ValueError("an attribution table is named exactly when a role calls a model")
        if self.attribution_table is not None:
            require_digest(self.attribution_table, "the attribution table digest")
        if (self.reservation is not None) != bool(roles):
            raise ValueError("a reservation is recorded exactly when a role calls a model")
        priced = [role for role, _ in self.pricing_selections]
        if len(set(priced)) != len(priced):
            raise ValueError(f"a role is priced under one selection, got {priced}")
        if set(priced) != set(roles):
            raise ValueError(
                "every role that calls a model names its pricing: configured "
                f"{sorted(roles)}, priced {sorted(priced)}"
            )
        for role, selection in self.pricing_selections:
            for token_class in BILLED_ON_EVERY_CALL:
                rate = self.pricing.rate(
                    selection.pricing_key, selection.region, selection.billing_mode, token_class
                )
                if rate is None:
                    raise ValueError(
                        f"the basis holds no {token_class} rate for {role}'s selection "
                        f"{selection.pricing_key} in {selection.region} {selection.billing_mode}"
                    )
        prompts = [(role, name) for role, name, _ in self.prompt_digests]
        if len(set(prompts)) != len(prompts):
            raise ValueError(f"a prompt is digested once per role and name, got {prompts}")
        for role, name, digest in self.prompt_digests:
            require_opaque_id(role, "a role")
            require_opaque_id(name, "a prompt name")
            require_digest(digest, f"the {role} {name} prompt digest")
        surfaces = [role for role, _ in self.tool_surface_digests]
        if len(set(surfaces)) != len(surfaces):
            raise ValueError(f"a role sees one tool surface, got {surfaces}")
        for role, digest in self.tool_surface_digests:
            require_opaque_id(role, "a role")
            require_digest(digest, f"the {role} tool surface digest")
        prompted = {role for role, _, _ in self.prompt_digests}
        if prompted != set(roles):
            raise ValueError(
                "every role that calls a model has its prompts digested: configured "
                f"{sorted(roles)}, prompted {sorted(prompted)}"
            )
        if set(surfaces) != set(roles):
            raise ValueError(
                "every role that calls a model has its tool surface digested: configured "
                f"{sorted(roles)}, surfaced {sorted(surfaces)}"
            )
        if self.system.kind is SystemKind.RULES_ONLY:
            if self.model_configurations:
                raise ValueError("rules-only calls no model, so it records no model configuration")
            if self.retrieval.kind is not RetrievalKind.NONE:
                raise ValueError("rules-only retrieves nothing, so its retrieval is none")
        object.__setattr__(
            self, "model_configurations", tuple(sorted(self.model_configurations, key=_role))
        )
        object.__setattr__(
            self, "pricing_selections", tuple(sorted(self.pricing_selections, key=_role))
        )
        object.__setattr__(
            self, "prompt_digests", tuple(sorted(self.prompt_digests, key=_role_name))
        )
        object.__setattr__(
            self, "tool_surface_digests", tuple(sorted(self.tool_surface_digests, key=_role))
        )

    def _require_a_coherent_ending(self) -> None:
        failed = self.status is TerminalStatus.FAILED
        if (self.failure is not None) != failed:
            raise ValueError("a failure is recorded exactly when the status is failed")
        self._require_the_abandonment_to_fit_the_failure()
        if not self.timing.segments:
            self._require_the_never_claimed_ending()
        approved = self.approval.state is ApprovalState.APPROVED
        if not failed and not approved:
            raise ValueError(
                "an attempt that completed or reported at its cap holds an approval of its "
                f"review payload: status {self.status.value}, approval "
                f"{self.approval.state.value}"
            )
        requested = self.approval.state is not ApprovalState.NOT_REQUESTED
        if self.timing.approval_requested is not None and not requested:
            raise ValueError("the timing stamps an approval request the approval does not hold")
        if self.timing.approval_resumed is not None and not approved:
            raise ValueError("the timing stamps a resume from an approval that was not given")
        if failed:
            return
        # A terminal event a worker wrote is that worker's recorded end, and it wrote it
        # after resuming from the approval it had stamped a request for.
        if not self.timing.segments[-1].end_recorded:
            raise ValueError(
                "an attempt that did not fail ended at its terminal event, so its last "
                "segment's end was recorded"
            )
        if self.timing.approval_requested is not None and self.timing.approval_resumed is None:
            raise ValueError(
                "an approved attempt whose worker stamped the request also stamped its resume"
            )

    def _require_the_abandonment_to_fit_the_failure(self) -> None:
        failure = self.failure
        abandoned = failure is not None and failure.site == HarnessSite(HarnessSiteName.ABANDONED)
        if abandoned and self.abandonment is None:
            raise ValueError(
                "a failure at the abandoned site holds the abandon command that closed it"
            )
        if abandoned and failure is not None:
            if failure.category is not FailureCategory.INFRASTRUCTURE:
                raise ValueError("an abandoned attempt failed by infrastructure")
        elif self.abandonment is not None and (
            failure is None or failure.category is not FailureCategory.DEFECT
        ):
            raise ValueError(
                "an abandon command beside a failure at another site finalized a recorded "
                "defect; the failure is by defect"
            )
        if (
            failure is not None
            and failure.site == HarnessSite(HarnessSiteName.UNHANDLED)
            and failure.category is not FailureCategory.DEFECT
        ):
            raise ValueError("a failure at the unhandled site is a defect")

    def _require_the_never_claimed_ending(self) -> None:
        """No segment means no claim: closed by an abandon command before any worker, the
        command fencing generation 0, nothing requested of anyone."""
        if self.failure is None or self.failure.site != HarnessSite(HarnessSiteName.ABANDONED):
            raise ValueError(
                "an attempt with no segment was never claimed and was closed by an abandon "
                "command: its failure is at the abandoned site"
            )
        if self.abandonment is not None and self.abandonment.ownership_generation != 0:
            raise ValueError(
                "an attempt with no segment was never claimed, so its abandonment fenced "
                f"generation 0, got {self.abandonment.ownership_generation}"
            )
        if self.approval.state is not ApprovalState.NOT_REQUESTED:
            raise ValueError("an attempt with no segment requested no approval")


def _role(item: tuple[str, object]) -> str:
    return item[0]


def _role_name(item: tuple[str, str, str]) -> tuple[str, str]:
    return item[0], item[1]
