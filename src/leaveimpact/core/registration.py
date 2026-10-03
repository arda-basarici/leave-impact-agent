"""The preregistration as plain data: what a measurement declares before it is made.

One committed file fixes the experiment (the investigator milestone's sixth build step,
ruling 1): the systems and the conditions they run under, the arms, how runs are counted,
the statistics, the frozen prefetch, the caps and the budget, and the scenario sets. Two
parties read it and may not import each other, the harness that executes under it and the
evaluator that reports under it, so the type sits here with its codec beside it
(``registration_json``). Names live in the registration and behaviour in code: a check, a
measure or a reporting policy is named here by a stable identifier, the package that owns
the behaviour resolves the name against its own registry, and each consumer compares the
digests it uses with what its own code computes and refuses a mismatch. Nothing here
substitutes a current value for a registered one.

The registration has a lifecycle. It is a ``draft`` until it is ``frozen``, and only a
frozen one precedes a reported measurement. A value not yet chosen is ``Pending``, a typed
statement that says what will resolve it; only the fields declared pendable accept one, a
pending value requires draft status, and a consumer refuses any execution that needs one.
A draft with nothing pending is still a draft. The caps and the budget each carry a
``Basis``: ``unmeasured`` marks numbers nobody has measured a run against, development
settings and placeholders and never a planned spend, and a frozen registration refuses
them, since its caps come from calibration runs.

The outage schedule is identified by a digest a run's record carries. It covers what the
schedule means and nothing about how the file spells it: the protocol the injection
follows, the injection semantics, and the registered source sets. A condition's reporting
scope is not in it, being how results are shown and not what was injected.

A condition is named by what it cannot reach, in the sources' own names, so its identifier
is derived from its source set and cannot disagree with it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.enums import Source
from leaveimpact.core.ids import ScenarioId, is_numbered_id
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.provenance import ModelConfiguration
from leaveimpact.core.run_record import (
    Caps,
    FailureCategory,
    Retrieval,
    RetrievalKind,
    SystemKind,
    require_commit,
)
from leaveimpact.core.run_trace import require_digest, require_integer, require_opaque_id
from leaveimpact.core.tools import SEARCH_LIMIT

REGISTRATION_FORMAT_VERSION = 1
"""The one format this code reads; a decoder refuses any other."""

OUTAGE_PROTOCOL = ("whole-run-read-port-outage", 1)
"""The injection behaviour and its version: raised on a semantic change to how an assigned
outage is applied, whether or not the registered source sets change."""

SCHEDULE_ENVELOPE_VERSION = 1
"""The shape of what the schedule digest hashes; bumped when the envelope's own shape changes."""

NORMAL_CONDITION = "normal"
"""The identifier of the condition under which every source answers."""


# --- Lifecycle and pending values ----------------------------------------------------------


class RegistrationStatus(StrEnum):
    """Whether the registration may still change; a member is the wire form."""

    DRAFT = "draft"
    FROZEN = "frozen"


@dataclass(frozen=True, slots=True)
class Pending:
    """A value not yet chosen, with what will resolve it in plain language.

    >>> Pending(" ")
    Traceback (most recent call last):
    ...
    ValueError: a pending value says what resolves it
    """

    awaiting: str

    def __post_init__(self) -> None:
        if not self.awaiting.strip():
            raise ValueError("a pending value says what resolves it")


class Basis(StrEnum):
    """What stands behind a section's numbers.

    ``UNMEASURED`` is a development setting or a placeholder no run has been measured
    against; ``CALIBRATED`` says the numbers were set from observed usage.
    """

    UNMEASURED = "unmeasured"
    CALIBRATED = "calibrated"


@dataclass(frozen=True, slots=True)
class Amendment:
    """What the registration's author declares about its history; nothing here is verified.

    ``amends`` is the commit of the registration this one changes, or ``None`` for a first
    one; ``prior_full_set_results`` says whether full-set results on this world existed
    when it was written. No job can read the evaluations to check either, so a reader
    labels both as declared.
    """

    amends: str | None
    prior_full_set_results: bool

    def __post_init__(self) -> None:
        if self.amends is not None:
            require_commit(self.amends, "the amended registration's commit")


# --- The systems ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ReportingPolicy:
    """The rules-only reporting policy by its declared identifier and version, with the
    tie-break among viable assignees by name. The version is a declared semantic version
    the harness compares with its own; nothing derives it."""

    identifier: str
    version: int
    tie_break: str

    def __post_init__(self) -> None:
        require_opaque_id(self.identifier, "a reporting policy identifier")
        require_integer(self.version, "a reporting policy version", minimum=1)
        require_opaque_id(self.tie_break, "a tie-break rule")


@dataclass(frozen=True, slots=True)
class AgentSystem:
    """The investigator: its variant, retrieval, model, prompts by name and tool surface."""

    variant: str | Pending
    retrieval: Retrieval
    model: ModelConfiguration | Pending
    prompt_digests: tuple[tuple[str, str], ...] | Pending
    tool_surface_digest: str | Pending

    def __post_init__(self) -> None:
        _require_variant(self.variant)
        _require_prompts(self, self.prompt_digests)
        if not isinstance(self.tool_surface_digest, Pending):
            require_digest(self.tool_surface_digest, "the agent's tool surface digest")

    @property
    def kind(self) -> SystemKind:
        return SystemKind.AGENT


@dataclass(frozen=True, slots=True)
class RulesOnlySystem:
    """The rules-only baseline: no model and no retrieval, its conclusions written as claims
    by the named reporting policy."""

    variant: str | Pending
    retrieval: Retrieval
    policy: ReportingPolicy

    def __post_init__(self) -> None:
        _require_variant(self.variant)
        if self.retrieval.kind is not RetrievalKind.NONE:
            raise ValueError("rules-only retrieves nothing, so its retrieval is none")

    @property
    def kind(self) -> SystemKind:
        return SystemKind.RULES_ONLY


@dataclass(frozen=True, slots=True)
class SingleShotSystem:
    """The single-shot baseline: one harness-issued search, one model call, no tools.

    ``query_protocol`` is only ever pending in this format: the protocol's shape (a
    literal, or a template with its inputs, rendering and fallback) is settled when the
    baseline is built, and arrives with a format change. ``search_limit`` lies within the
    search tool's declared range, which the tool-surface digest binds without choosing a
    value.
    """

    variant: str | Pending
    retrieval: Retrieval
    model: ModelConfiguration | Pending
    prompt_digests: tuple[tuple[str, str], ...] | Pending
    query_protocol: Pending
    search_limit: int | Pending

    def __post_init__(self) -> None:
        _require_variant(self.variant)
        _require_prompts(self, self.prompt_digests)
        if not isinstance(self.search_limit, Pending):
            require_integer(self.search_limit, "the search limit", minimum=None)
            if not SEARCH_LIMIT.minimum <= self.search_limit <= SEARCH_LIMIT.maximum:
                raise ValueError(
                    f"the search limit lies in {SEARCH_LIMIT.minimum}..{SEARCH_LIMIT.maximum}, "
                    f"got {self.search_limit}"
                )

    @property
    def kind(self) -> SystemKind:
        return SystemKind.SINGLE_SHOT


RegisteredSystem = AgentSystem | RulesOnlySystem | SingleShotSystem


def _require_variant(variant: str | Pending) -> None:
    if not isinstance(variant, Pending):
        require_opaque_id(variant, "an orchestration variant")


def _require_prompts(
    system: AgentSystem | SingleShotSystem, prompts: tuple[tuple[str, str], ...] | Pending
) -> None:
    """Prompts are unique by name, each a digest, and held in name order."""
    if isinstance(prompts, Pending):
        return
    names = [name for name, _ in prompts]
    if len(set(names)) != len(names):
        raise ValueError(f"a prompt is digested once per name, got {names}")
    for name, digest in prompts:
        require_opaque_id(name, "a prompt name")
        require_digest(digest, f"the {name} prompt digest")
    object.__setattr__(system, "prompt_digests", tuple(sorted(prompts)))


# --- The outage schedule -------------------------------------------------------------------


class Injection(StrEnum):
    """How an assigned outage is applied.

    ``WHOLE_RUN_AT_READ_PORT``: the source is unreachable from the run's first call to its
    last, at the read-port boundary. A fault that began mid-run would give a run mixed
    conditions, which the evaluator limits and cannot grade.
    """

    WHOLE_RUN_AT_READ_PORT = "whole_run_at_read_port"


class ReportingScope(StrEnum):
    """What is reported for an assigned condition; it describes the assigned experiment,
    never the outcome the evaluator gives a run.

    ``ANSWER_QUALITY``: the full tables and the paired comparisons. ``DEGRADED_CONDITION``:
    the accounting, the cost and the degraded table, for an assignment under which the
    oracle has no claim-level answer.
    """

    ANSWER_QUALITY = "answer_quality"
    DEGRADED_CONDITION = "degraded_condition"


def condition_id(unreachable: Iterable[Source]) -> str:
    """The identifier of the condition under which ``unreachable`` cannot be reached.

    >>> condition_id([]), condition_id([Source.JIRA])
    ('normal', 'jira_down')
    """
    down = sorted(source.value for source in set(unreachable))
    return f"{'+'.join(down)}_down" if down else NORMAL_CONDITION


@dataclass(frozen=True, slots=True)
class RegisteredCondition:
    """One assigned condition: the sources scheduled unreachable and how it is reported."""

    unreachable: frozenset[Source]
    reporting: ReportingScope

    @property
    def id(self) -> str:
        return condition_id(self.unreachable)


@dataclass(frozen=True, slots=True)
class OutageSchedule:
    """The registered conditions with the protocol and the semantics of their injection."""

    protocol: tuple[str, int]
    injection: Injection
    conditions: tuple[RegisteredCondition, ...]

    def __post_init__(self) -> None:
        require_opaque_id(self.protocol[0], "the outage protocol")
        require_integer(self.protocol[1], "the outage protocol version", minimum=1)
        ids = [condition.id for condition in self.conditions]
        if len(set(ids)) != len(ids):
            raise ValueError(f"a condition is registered once, got {ids}")
        if NORMAL_CONDITION not in ids:
            raise ValueError("the normal condition is registered")

    def condition(self, identifier: str) -> RegisteredCondition | None:
        """The registered condition named ``identifier``, or ``None``."""
        for condition in self.conditions:
            if condition.id == identifier:
                return condition
        return None


def schedule_digest(schedule: OutageSchedule) -> str:
    """SHA-256 over the versioned envelope of the schedule: the protocol, the injection and
    the registered source sets in identifier order.

    The order the conditions are listed in and each one's reporting scope are not in it:
    neither changes what is injected.
    """
    envelope: JsonObject = {
        "envelope_version": SCHEDULE_ENVELOPE_VERSION,
        "protocol": {"id": schedule.protocol[0], "version": schedule.protocol[1]},
        "injection": schedule.injection.value,
        "conditions": [
            sorted(source.value for source in condition.unreachable)
            for condition in sorted(schedule.conditions, key=lambda condition: condition.id)
        ],
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


@dataclass(frozen=True, slots=True)
class RegisteredArm:
    """One system under one assigned condition, each by its registered name."""

    system: SystemKind
    condition: str


# --- Run accounting ------------------------------------------------------------------------


class MissingRunRule(StrEnum):
    """How an intended run that was never made counts toward end-to-end success."""

    NOT_PASSED = "not_passed"
    LEFT_OUT = "left_out"


class CountedAttemptRule(StrEnum):
    """Which attempt of a retried run is the run.

    ``EARLIEST_NOT_INFRASTRUCTURE``: the earliest attempt whose outcome is not an
    infrastructure failure, else the last.
    """

    FIRST = "first"
    LAST = "last"
    EARLIEST_NOT_INFRASTRUCTURE = "earliest_not_infrastructure"


@dataclass(frozen=True, slots=True)
class RetryRule:
    """The one failure category an attempt is retried after, and the most attempts a run has,
    the first execution included."""

    after: FailureCategory
    max_attempts: int

    def __post_init__(self) -> None:
        require_integer(self.max_attempts, "max_attempts", minimum=1)


@dataclass(frozen=True, slots=True)
class RunAccounting:
    """How runs are repeated, retried and counted, with the estimand that follows in words."""

    repeats: int
    missing_run: MissingRunRule
    retry: RetryRule
    counted_attempt: CountedAttemptRule
    estimand: str

    def __post_init__(self) -> None:
        require_integer(self.repeats, "repeats", minimum=1)
        if not self.estimand.strip():
            raise ValueError("the estimand is stated")


# --- Statistics ----------------------------------------------------------------------------


class CheckReading(StrEnum):
    """The two readings of a check: over every intended run, or over the applicable,
    observed results."""

    END_TO_END = "end_to_end"
    CONDITIONAL = "conditional"


class StratumLevel(StrEnum):
    """The levels a comparison is cut at; a class carries raw counts and no comparison."""

    OVERALL = "overall"
    TIER = "tier"


class ScenarioSetName(StrEnum):
    """The scenario sets a result is reported over: the scenarios held out from
    scenario-specific tuning, and the whole world."""

    PRIMARY = "primary"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class PrimaryComparison:
    """One primary comparison: a check under a reading, on one condition, stratum and
    scenario set, between two systems in the order the difference is taken."""

    check: str
    reading: CheckReading
    condition: str
    stratum: StratumLevel
    scenario_set: ScenarioSetName
    systems: tuple[SystemKind, SystemKind]

    def __post_init__(self) -> None:
        if self.systems[0] is self.systems[1]:
            raise ValueError("a comparison is between two systems")


@dataclass(frozen=True, slots=True)
class DescriptiveComparisons:
    """The descriptive comparisons as a product: every pair under every condition at every
    stratum level over every scenario set, on every check in every reading and on every
    measure. The measures are in the order they are shown, the leading one first."""

    pairs: tuple[tuple[SystemKind, SystemKind], ...]
    conditions: tuple[str, ...]
    strata: tuple[StratumLevel, ...]
    scenario_sets: tuple[ScenarioSetName, ...]
    checks: tuple[str, ...]
    readings: tuple[CheckReading, ...]
    measures: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("pairs", "conditions", "strata", "scenario_sets", "checks", "readings"):
            _require_listed_once(getattr(self, name), f"the descriptive {name}")
        _require_listed_once(self.measures, "the descriptive measures")
        if any(first is second for first, second in self.pairs):
            raise ValueError("a comparison is between two systems")
        if len({frozenset(pair) for pair in self.pairs}) != len(self.pairs):
            raise ValueError("a pair of systems is compared once, in one order")


@dataclass(frozen=True, slots=True)
class Statistics:
    """The estimation settings, the named checks and measures, and what is compared.

    The names are identifiers the evaluator resolves against its own registry; a name it
    does not hold is its refusal, not this type's.
    """

    confidence_percent: int
    seed: int
    resamples: int
    checks: tuple[str, ...]
    measures: tuple[str, ...]
    primary: tuple[PrimaryComparison, ...]
    descriptive: DescriptiveComparisons

    def __post_init__(self) -> None:
        require_integer(self.confidence_percent, "confidence_percent", minimum=1)
        if self.confidence_percent > 99:
            raise ValueError(
                f"a confidence level lies strictly between 0 and 100 percent, "
                f"got {self.confidence_percent}"
            )
        require_integer(self.seed, "seed")
        require_integer(self.resamples, "resamples", minimum=1)
        for names, what in ((self.checks, "a check"), (self.measures, "a measure")):
            for name in names:
                require_opaque_id(name, what)
        _require_listed_once(self.checks, "the checks")
        _require_listed_once(self.measures, "the measures")
        _require_listed_once(self.primary, "the primary comparisons")
        used_checks = {comparison.check for comparison in self.primary}
        used_checks.update(self.descriptive.checks)
        if not used_checks <= set(self.checks):
            raise ValueError(
                f"a comparison names a registered check, got {sorted(used_checks)} "
                f"of {list(self.checks)}"
            )
        if not set(self.descriptive.measures) <= set(self.measures):
            raise ValueError(
                f"a comparison names a registered measure, got "
                f"{list(self.descriptive.measures)} of {list(self.measures)}"
            )


def _require_listed_once(items: tuple[object, ...], what: str) -> None:
    if len(set(items)) != len(items):
        raise ValueError(f"{what} are each listed once, got {list(items)}")


# --- The prefetch, the caps, the budget, the scenario sets ---------------------------------


@dataclass(frozen=True, slots=True)
class RegisteredPrefetch:
    """The frozen prefetch as registered: its identifier, planner-protocol version and digest.
    A consumer compares all three with what its own code computes."""

    identifier: str
    protocol_version: int
    digest: str

    def __post_init__(self) -> None:
        require_opaque_id(self.identifier, "a prefetch rule identifier")
        require_integer(self.protocol_version, "the prefetch protocol version", minimum=1)
        require_digest(self.digest, "a prefetch rule digest")


@dataclass(frozen=True, slots=True)
class RegisteredCaps:
    """The per-run caps every arm runs under, and what stands behind the numbers."""

    basis: Basis
    caps: Caps


@dataclass(frozen=True, slots=True)
class Budget:
    """The milestone's model spend bounds in whole dollars, cumulative over the milestone and
    never a rate per period, with what stands behind them.

    ``expected_usd`` and ``ceiling_usd`` are upper bounds; a reforecast is mandatory after
    ``reforecast_after_runs`` calibration runs; the spend ledger admits a run only below
    ``admission_threshold_usd``, which a reforecast may raise to at most
    ``admission_threshold_limit_usd``.

    >>> Budget(Basis.UNMEASURED, 150, 300, 10, 280, 270)
    Traceback (most recent call last):
    ...
    ValueError: the admission threshold stays at or below its limit, got 280 over 270
    """

    basis: Basis
    expected_usd: int
    ceiling_usd: int
    reforecast_after_runs: int
    admission_threshold_usd: int
    admission_threshold_limit_usd: int

    def __post_init__(self) -> None:
        for name in (
            "expected_usd",
            "ceiling_usd",
            "reforecast_after_runs",
            "admission_threshold_usd",
            "admission_threshold_limit_usd",
        ):
            require_integer(getattr(self, name), name, minimum=1)
        if self.expected_usd > self.ceiling_usd:
            raise ValueError(
                f"the expected spend stays at or below the ceiling, got {self.expected_usd} "
                f"over {self.ceiling_usd}"
            )
        if self.admission_threshold_usd > self.admission_threshold_limit_usd:
            raise ValueError(
                "the admission threshold stays at or below its limit, got "
                f"{self.admission_threshold_usd} over {self.admission_threshold_limit_usd}"
            )
        if self.admission_threshold_limit_usd > self.ceiling_usd:
            raise ValueError(
                "the admission threshold's limit stays at or below the ceiling, got "
                f"{self.admission_threshold_limit_usd} over {self.ceiling_usd}"
            )


@dataclass(frozen=True, slots=True)
class ScenarioSets:
    """The development scenarios, and with them the primary set: every scenario of the world
    that is not a development one.

    The development scenarios are ``development_per_tier`` from each tier, selected by tier
    alone, and listed as bare ids in id order with no tier beside them, a scenario's tier
    being sealed. The ids are pending until that selection has been made.
    """

    development_size: int
    development_per_tier: int
    development: tuple[ScenarioId, ...] | Pending

    def __post_init__(self) -> None:
        require_integer(self.development_size, "development_size", minimum=1)
        require_integer(self.development_per_tier, "development_per_tier", minimum=1)
        if self.development_size % self.development_per_tier:
            raise ValueError(
                f"the development scenarios are {self.development_per_tier} per tier, "
                f"got {self.development_size} in all"
            )
        if isinstance(self.development, Pending):
            return
        for scenario in self.development:
            if not is_numbered_id(scenario) or not scenario.startswith("scenario_"):
                raise ValueError(f"a scenario id has the form scenario_NNN, got {scenario!r}")
        if len(set(self.development)) != len(self.development):
            raise ValueError("a development scenario is listed once")
        if len(self.development) != self.development_size:
            raise ValueError(
                f"{self.development_size} development scenarios are listed, "
                f"got {len(self.development)}"
            )
        object.__setattr__(self, "development", tuple(sorted(self.development)))


# --- The registration ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Registration:
    """The preregistration whole; see the module for its lifecycle and what each part fixes.

    Beyond each section's own shape it holds what only the whole can check: a system kind
    is registered once; every arm and every comparison names a registered system and a
    registered condition, an arm once; a comparison is made under an answer-quality
    condition; a pending value requires draft status; a frozen registration's caps and
    budget are calibrated.
    """

    format_version: int
    status: RegistrationStatus
    amendment: Amendment
    systems: tuple[RegisteredSystem, ...]
    outage: OutageSchedule
    arms: tuple[RegisteredArm, ...]
    run_accounting: RunAccounting
    statistics: Statistics
    prefetch: RegisteredPrefetch
    caps: RegisteredCaps
    budget: Budget
    scenario_sets: ScenarioSets

    def __post_init__(self) -> None:
        if self.format_version != REGISTRATION_FORMAT_VERSION:
            raise ValueError(
                f"this code reads registration format {REGISTRATION_FORMAT_VERSION}, "
                f"got {self.format_version}"
            )
        kinds = [system.kind for system in self.systems]
        if len(set(kinds)) != len(kinds):
            raise ValueError(f"a system kind is registered once, got {[k.value for k in kinds]}")
        if not self.arms:
            raise ValueError("at least one arm is registered: a system under an assigned condition")
        if len(set(self.arms)) != len(self.arms):
            raise ValueError("an arm is registered once")
        for arm in self.arms:
            self._require_registered(arm.system, arm.condition, "an arm")
        statistics = self.statistics
        for comparison in statistics.primary:
            for system in comparison.systems:
                self._require_compared(system, comparison.condition)
        for pair in statistics.descriptive.pairs:
            for system in pair:
                for condition in statistics.descriptive.conditions:
                    self._require_compared(system, condition)
        if self.status is RegistrationStatus.FROZEN:
            pending = pending_fields(self)
            if pending:
                raise ValueError(
                    f"a frozen registration has nothing pending, got {', '.join(pending)}"
                )
            unmeasured = [
                name
                for name, basis in (("caps", self.caps.basis), ("budget", self.budget.basis))
                if basis is Basis.UNMEASURED
            ]
            if unmeasured:
                raise ValueError(
                    "a frozen registration's numbers are calibrated, got unmeasured "
                    f"{' and '.join(unmeasured)}"
                )

    def system(self, kind: SystemKind) -> RegisteredSystem | None:
        """The registered system of ``kind``, or ``None``."""
        for system in self.systems:
            if system.kind is kind:
                return system
        return None

    def _require_registered(self, system: SystemKind, condition: str, what: str) -> None:
        if self.system(system) is None:
            raise ValueError(f"{what} names a registered system, got {system.value}")
        if self.outage.condition(condition) is None:
            raise ValueError(f"{what} names a registered condition, got {condition!r}")

    def _require_compared(self, system: SystemKind, condition: str) -> None:
        self._require_registered(system, condition, "a comparison")
        registered = self.outage.condition(condition)
        assert registered is not None
        if registered.reporting is not ReportingScope.ANSWER_QUALITY:
            raise ValueError(
                f"a comparison is made under an answer-quality condition, got {condition!r}"
            )
        if RegisteredArm(system, condition) not in self.arms:
            raise ValueError(
                f"a comparison is between registered arms, got {system.value} under {condition!r}"
            )


def pending_fields(registration: Registration) -> tuple[str, ...]:
    """The registration's pending values by dotted name, in the file's order; empty when
    every choice is made. A consumer refuses an execution that needs one of these."""
    found: list[str] = []
    for system in registration.systems:
        fields: tuple[tuple[str, object], ...]
        match system:
            case AgentSystem():
                fields = (
                    ("variant", system.variant),
                    ("model", system.model),
                    ("prompt_digests", system.prompt_digests),
                    ("tool_surface_digest", system.tool_surface_digest),
                )
            case RulesOnlySystem():
                fields = (("variant", system.variant),)
            case SingleShotSystem():
                fields = (
                    ("variant", system.variant),
                    ("model", system.model),
                    ("prompt_digests", system.prompt_digests),
                    ("query_protocol", system.query_protocol),
                    ("search_limit", system.search_limit),
                )
        found.extend(
            f"systems.{system.kind.value}.{name}"
            for name, value in fields
            if isinstance(value, Pending)
        )
    if isinstance(registration.scenario_sets.development, Pending):
        found.append("scenario_sets.development")
    return tuple(found)


__all__ = [
    "NORMAL_CONDITION",
    "OUTAGE_PROTOCOL",
    "REGISTRATION_FORMAT_VERSION",
    "SCHEDULE_ENVELOPE_VERSION",
    "AgentSystem",
    "Amendment",
    "Basis",
    "Budget",
    "CheckReading",
    "CountedAttemptRule",
    "DescriptiveComparisons",
    "Injection",
    "MissingRunRule",
    "OutageSchedule",
    "Pending",
    "PrimaryComparison",
    "RegisteredArm",
    "RegisteredCaps",
    "RegisteredCondition",
    "RegisteredPrefetch",
    "RegisteredSystem",
    "Registration",
    "RegistrationStatus",
    "ReportingPolicy",
    "ReportingScope",
    "RetryRule",
    "RulesOnlySystem",
    "RunAccounting",
    "ScenarioSetName",
    "ScenarioSets",
    "SingleShotSystem",
    "Statistics",
    "StratumLevel",
    "condition_id",
    "pending_fields",
    "schedule_digest",
]
