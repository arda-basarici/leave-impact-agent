"""The provenance of one run attempt: what ran, under what, with what, how it ended, what it cost.

The record is the block of a run export that identifies the execution rather than
replaying it (the investigator milestone's second build step, rulings 4 and 5). A
result is regenerable only from its recorded inputs, and a comparison between systems
is sound only when what was held fixed is on record, so the record states each of
those as a fact the evaluator can read without the harness: the condition the run
observed and the outage it was assigned, the harness revision and the preregistration
it ran under, the model each role called and the prompts and tool surface each role
saw, which of the three systems produced the export and with which retrieval and
prefetch rule, the cap it ran under, how the attempt ended, and the usage and cost the
provider reported with the pricing that priced it.

Two kinds of statement sit here and are kept apart in the reader's mind. Some fields
are *inputs* the harness set and nobody can derive (the assignment, the caps, the
revision); others are *claims over the trace* that the evaluator re-derives and
verifies (the observed condition from the failed reads, the usage aggregate from the
model calls, the cumulative cost from the per-call costs). A claim is stored rather
than left to derivation because a mismatch between the harness's reading and the
replay's is a finding, and only a stored value can mismatch. The constructors here
enforce each block's own shape; the cross-trace checks are the evaluator's.

Absent is a different statement from zero: a usage counter the provider did not report
is unavailable, an aggregate says how many calls reported each counter, and a cost
whose counters were incomplete says so.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from leaveimpact.core.enums import Source
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.provenance import ModelConfiguration
from leaveimpact.core.run_trace import (
    USAGE_COUNTER_NAMES,
    Cost,
    require_digest,
    require_integer,
    require_opaque_id,
)

GIT_SHA_LENGTH = 40


def require_commit(value: str, what: str) -> str:
    """``value`` if it is a full lower-case git commit SHA."""
    if len(value) != GIT_SHA_LENGTH or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{what} is a forty-hex git commit, got {value!r}")
    return value


def _non_negative(value: int, what: str) -> int:
    return require_integer(value, what)


# --- How the attempt ended ---------------------------------------------------------------


class TerminalStatus(StrEnum):
    """How the investigation ended; the job's later approval state is not an export status.

    ``COMPLETED`` means the system produced its final claims, the same for all three
    systems, a refusal or a claimless completion included (graded with its omissions);
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
    """The normalized fault of a failed attempt: its category, where in the trace, and why.

    ``at`` names the operation (a malformed record) or the model call (a provider
    fault) that failed, so the fault is recorded and not merely counted.
    """

    category: FailureCategory
    at: str
    reason: str

    def __post_init__(self) -> None:
        require_opaque_id(self.at, "the failing operation or model call id")


# --- What ran ----------------------------------------------------------------------------


class SystemKind(StrEnum):
    """The three systems the evaluator grades from one export shape."""

    AGENT = "agent"
    RULES_ONLY = "rules_only"
    SINGLE_SHOT = "single_shot"


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


class TreeState(StrEnum):
    """Whether the harness ran from the commit it names or from uncommitted changes over it."""

    CLEAN = "clean"
    DIRTY = "dirty"


@dataclass(frozen=True, slots=True)
class HarnessRevision:
    """The harness commit and the state of the tree it ran from; dirty is refused at reporting."""

    commit: str
    tree: TreeState

    def __post_init__(self) -> None:
        require_commit(self.commit, "the harness commit")


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
    """The per-run cap as it ran, with the finalization reserves inside the totals.

    The loop stops before the reserve, finalization may spend it, and the total never
    extends; ``counting_rule`` names which token classes count, a preregistered rule.

    >>> Caps(20, 100_000, 20, 5_000, "input_output")
    Traceback (most recent call last):
    ...
    ValueError: the finalization call reserve sits inside the call cap, got 20 of 20
    """

    call_cap: int
    token_cap: int
    finalization_call_reserve: int
    finalization_token_reserve: int
    counting_rule: str

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
        require_opaque_id(self.counting_rule, "the counting rule")


# --- Usage, cost and pricing -------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UsageAggregate:
    """The run's usage summed over the model calls that reported each counter, with the coverage.

    Each counter is ``(name, value, reported_calls)``: a sum over the calls that
    reported it and how many did, beside ``model_calls``, the number there were, so a
    reader can tell a total from a partial sum. A counter no call reported is not a row
    at all, so absence is never spelled as a zero sum over zero calls. ``duration_ms``
    is the run's own, from a monotonic clock, a different quantity from any provider
    latency.

    >>> UsageAggregate((("input_tokens", 500, 3),), 3, 12_000).value("input_tokens")
    (500, 3)
    """

    counters: tuple[tuple[str, int, int], ...]
    model_calls: int
    duration_ms: int

    def __post_init__(self) -> None:
        _non_negative(self.model_calls, "model_calls")
        _non_negative(self.duration_ms, "duration_ms")
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
            require_integer(reported, f"{name} reported_calls", minimum=1)
            if reported > self.model_calls:
                raise ValueError(f"{name}: reported by {reported} calls of {self.model_calls}")

    def value(self, name: str) -> tuple[int, int] | None:
        """``(sum, reported_calls)`` for ``name``, or ``None`` when no call reported it."""
        for held, value, reported in self.counters:
            if held == name:
                return value, reported
        return None


@dataclass(frozen=True, slots=True)
class PricingRow:
    """One rate: integer nano-dollars per token for a token class under a pricing key.

    The key, region and billing mode together name a Bedrock rate; a model id alone
    does not (the ``eu.`` profile and on-demand are priced as their own keys).
    """

    pricing_key: str
    region: str
    billing_mode: str
    token_class: str
    nano_usd_per_token: int

    def __post_init__(self) -> None:
        for name in ("pricing_key", "region", "billing_mode"):
            require_opaque_id(getattr(self, name), name)
        if self.token_class not in USAGE_COUNTER_NAMES:
            raise ValueError(f"a token class is a usage counter name, got {self.token_class!r}")
        _non_negative(self.nano_usd_per_token, "nano_usd_per_token")

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
                f"costs are nano-dollars, so the basis is in USD, got {self.currency!r}"
            )
        keys = [row.key for row in self.rows]
        if len(set(keys)) != len(keys):
            raise ValueError("a rate is given once per pricing key, region, billing mode and class")
        object.__setattr__(self, "rows", tuple(sorted(self.rows, key=lambda row: row.key)))

    def rate(
        self, pricing_key: str, region: str, billing_mode: str, token_class: str
    ) -> int | None:
        """The nano-dollars per token for the named rate, or ``None`` when the basis has none."""
        for row in self.rows:
            if row.key == (pricing_key, region, billing_mode, token_class):
                return row.nano_usd_per_token
        return None


@dataclass(frozen=True, slots=True)
class PricingSelection:
    """The rate a role's calls were priced under: the pricing key, region and billing mode.

    A role's configuration names a model id, and a model id alone does not fix a
    Bedrock rate, so the selection is recorded beside it; with the basis's rows it is
    what lets the evaluator reproduce every per-call cost.
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
    equal records are equal in bytes; every role that calls a model names both its
    configuration and the rate it was priced under. ``failure`` is present exactly when
    the status is failed. ``cost`` is ``None`` when no call was priced, never a zero.
    """

    observed_condition: RunCondition
    outage: OutageAssignment
    harness: HarnessRevision
    preregistration_commit: str
    model_configurations: tuple[tuple[str, ModelConfiguration], ...]
    pricing_selections: tuple[tuple[str, PricingSelection], ...]
    prompt_digests: tuple[tuple[str, str, str], ...]
    tool_surface_digests: tuple[tuple[str, str], ...]
    system: System
    retrieval: Retrieval
    prefetch_rule: PrefetchRule
    caps: Caps
    status: TerminalStatus
    failure: Failure | None
    usage: UsageAggregate
    cost: Cost | None
    pricing: PricingBasis

    def __post_init__(self) -> None:
        require_commit(self.preregistration_commit, "the preregistration commit")
        if (self.failure is not None) != (self.status is TerminalStatus.FAILED):
            raise ValueError("a failure is recorded exactly when the status is failed")
        roles = [role for role, _ in self.model_configurations]
        if len(set(roles)) != len(roles):
            raise ValueError(f"a role calls one model configuration, got {roles}")
        for role in roles:
            require_opaque_id(role, "a role")
        priced = [role for role, _ in self.pricing_selections]
        if len(set(priced)) != len(priced):
            raise ValueError(f"a role is priced under one selection, got {priced}")
        if set(priced) != set(roles):
            raise ValueError(
                "every role that calls a model names its pricing: configured "
                f"{sorted(roles)}, priced {sorted(priced)}"
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


def _role(item: tuple[str, object]) -> str:
    return item[0]


def _role_name(item: tuple[str, str, str]) -> tuple[str, str]:
    return item[0], item[1]
