"""The preregistration as plain data: what a measurement declares before it is made.

One committed file fixes the experiment (the contract step's rulings on the registration,
replacing the format the sixth build step wrote): the world it is measured on, the systems
with their roles and caps, the corpus levels, the conditions, the cells, how runs are
counted and re-dispatched, how a dispatch's observation is read, the stated-fact contract,
the statistics, the supporting comparisons, the frozen prefetch and the budget. Two parties
read it and may not import each other, the harness that executes under it and the evaluator
that reports under it, so the type sits here with its codec beside it
(``registration_json``). Names live in the registration and behaviour in code: a check, a
measure, an interval method or a composing policy is named here by a stable identifier or a
digest, the package that owns the behaviour resolves it against its own code, and each
consumer compares what it uses with what its own code computes and refuses a mismatch.
Nothing here substitutes a current value for a registered one.

*The lifecycle* has three statuses. A ``draft`` may hold values not yet chosen. ``frozen``
says the procedure is fixed, and it is fixed before the world it will be measured on
exists: a frozen registration has exactly one value pending, the world's version. ``bound``
holds that version and names the commit of the frozen registration it binds. Binding
changes nothing else, and ``registration_json.procedure_projection`` is what a reader
compares to hold it to that: the registration without its status, its world's version and
the frozen commit it names. Only a bound registration precedes a reported measurement.

A value not yet chosen is ``Pending``, a typed statement that says what will resolve it;
only the fields declared pendable accept one. A pending value blocks only an execution that
needs it, and ``blocking`` is the one reading of what a system's execution needs, shared by
the harness that refuses to run, the evaluator's projection that leaves a cell out, and the
eligibility check that finds nothing to compare a run with. The caps of each system and the
budget carry a ``Basis``: ``unmeasured`` marks numbers nobody has measured a run against,
development settings and placeholders and never a planned spend, and a frozen registration
refuses them, since its caps come from calibration runs.

*A cell* is one system under one assigned condition at one corpus level. A cell may belong
to a conditional group, which holds its rule in words and one decision for all its cells,
so "all of them or none" is a property of the type. Nobody executes or reports a cell whose
group is not decided as run.

The outage schedule is identified by a digest a run's record carries. It covers what the
schedule means and nothing about how the file spells it: the protocol the injection
follows, the injection semantics, and the registered source sets. A condition's reporting
scope is not in it, being how results are shown and not what was injected. A condition is
named by what it cannot reach, in the sources' own names, so its identifier is derived from
its source set and cannot disagree with it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.attribution import AttributionTable, RedispatchPolicy
from leaveimpact.core.call_settings import CallConfiguration
from leaveimpact.core.enums import Source
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.run_ending import ComposingPolicy
from leaveimpact.core.run_record import (
    BASE_CORPUS_LEVEL,
    Caps,
    FailureCategory,
    Retrieval,
    RetrievalKind,
    SystemKind,
    require_commit,
)
from leaveimpact.core.run_trace import require_digest, require_integer, require_opaque_id
from leaveimpact.core.tools import SEARCH_LIMIT

REGISTRATION_FORMAT_VERSION = 2
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
    """Where the registration stands in its lifecycle; a member is the wire form."""

    DRAFT = "draft"
    FROZEN = "frozen"
    BOUND = "bound"


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


@dataclass(frozen=True, slots=True)
class MeasuredWorld:
    """The world the registration is measured on.

    ``version`` is pending until the world exists and has been accepted. ``frozen_commit``
    is the commit of the frozen registration a bound one binds, and ``None`` otherwise.
    ``tuned_scenarios`` declares how many of the world's scenarios any prompt or setting
    was tuned on; a frozen registration requires zero, development happening on other
    worlds, so the statement is in the registered bytes and not only in prose.
    """

    version: str | Pending
    frozen_commit: str | None
    tuned_scenarios: int

    def __post_init__(self) -> None:
        if not isinstance(self.version, Pending):
            require_digest(self.version, "the world's version")
        if self.frozen_commit is not None:
            require_commit(self.frozen_commit, "the frozen registration's commit")
        require_integer(self.tuned_scenarios, "tuned_scenarios")


# --- The systems ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RegisteredCaps:
    """The per-run caps a system runs under, and what stands behind the numbers."""

    basis: Basis
    caps: Caps


@dataclass(frozen=True, slots=True)
class RegisteredRole:
    """One role of a system that calls a model, by name: the configuration its calls run
    under, its prompts by name and digest, and the digest of the tool surface it is shown.
    A run records all three of every role, and the two are compared role by role."""

    name: str
    configuration: CallConfiguration
    prompt_digests: tuple[tuple[str, str], ...]
    tool_surface_digest: str

    def __post_init__(self) -> None:
        require_opaque_id(self.name, "a role")
        names = [name for name, _ in self.prompt_digests]
        if len(set(names)) != len(names):
            raise ValueError(f"a prompt is digested once per name, got {names}")
        for name, digest in self.prompt_digests:
            require_opaque_id(name, "a prompt name")
            require_digest(digest, f"the {name} prompt digest")
        require_digest(self.tool_surface_digest, f"the {self.name} tool surface digest")
        object.__setattr__(self, "prompt_digests", tuple(sorted(self.prompt_digests)))


Roles = tuple[RegisteredRole, ...]


@dataclass(frozen=True, slots=True)
class AgentSystem:
    """The investigator: its variant, retrieval, roles and caps. The roles are pending as a
    whole until the system is built."""

    variant: str | Pending
    retrieval: Retrieval
    roles: Roles | Pending
    caps: RegisteredCaps

    def __post_init__(self) -> None:
        _require_variant(self.variant)
        _require_roles(self, self.roles)

    @property
    def kind(self) -> SystemKind:
        return SystemKind.AGENT


@dataclass(frozen=True, slots=True)
class RulesOnlySystem:
    """The rules-only baseline: no model, no retrieval and so no role. Its claims are composed
    under the composing policy every rules-composed system shares, registered once."""

    variant: str | Pending
    retrieval: Retrieval
    caps: RegisteredCaps

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
    roles: Roles | Pending
    query_protocol: Pending
    search_limit: int | Pending
    caps: RegisteredCaps

    def __post_init__(self) -> None:
        _require_variant(self.variant)
        _require_roles(self, self.roles)
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


@dataclass(frozen=True, slots=True)
class FullContextSystem:
    """The full-context baseline: the single-shot path with the search replaced by every
    document of the level. It searches nothing, so its retrieval is none; what it was shown
    is each dispatch's input."""

    variant: str | Pending
    retrieval: Retrieval
    roles: Roles | Pending
    caps: RegisteredCaps

    def __post_init__(self) -> None:
        _require_variant(self.variant)
        _require_roles(self, self.roles)
        if self.retrieval.kind is not RetrievalKind.NONE:
            raise ValueError("full context searches nothing, so its retrieval is none")

    @property
    def kind(self) -> SystemKind:
        return SystemKind.FULL_CONTEXT


RegisteredSystem = AgentSystem | RulesOnlySystem | SingleShotSystem | FullContextSystem


def _require_variant(variant: str | Pending) -> None:
    if not isinstance(variant, Pending):
        require_opaque_id(variant, "an orchestration variant")


def _require_roles(
    system: AgentSystem | SingleShotSystem | FullContextSystem, roles: Roles | Pending
) -> None:
    """Roles are at least one, unique by name, and held in name order."""
    if isinstance(roles, Pending):
        return
    names = [role.name for role in roles]
    if not names:
        raise ValueError("a system that calls a model registers at least one role")
    if len(set(names)) != len(names):
        raise ValueError(f"a role is registered once per system, got {names}")
    object.__setattr__(system, "roles", tuple(sorted(roles, key=lambda role: role.name)))


def roles_of(system: RegisteredSystem) -> Roles | Pending:
    """The roles ``system`` registers: none for the system that calls no model."""
    return () if isinstance(system, RulesOnlySystem) else system.roles


def pending_in(system: RegisteredSystem) -> tuple[tuple[str, Pending], ...]:
    """The pending values of ``system`` by field name, in the file's order."""
    fields: tuple[tuple[str, object], ...]
    match system:
        case AgentSystem() | FullContextSystem():
            fields = (("variant", system.variant), ("roles", system.roles))
        case RulesOnlySystem():
            fields = (("variant", system.variant),)
        case SingleShotSystem():
            fields = (
                ("variant", system.variant),
                ("roles", system.roles),
                ("query_protocol", system.query_protocol),
                ("search_limit", system.search_limit),
            )
    return tuple((name, value) for name, value in fields if isinstance(value, Pending))


# --- The corpus levels ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CorpusLevel:
    """One registered corpus level: its name, and how many tokens of answer-neutral filler
    it adds to the world's own documents. The base level adds none. Which documents a level
    holds is sealed with the world; this is the size the level was built to."""

    name: str
    filler_tokens: int | Pending

    def __post_init__(self) -> None:
        require_opaque_id(self.name, "a corpus level")
        if not isinstance(self.filler_tokens, Pending):
            require_integer(self.filler_tokens, "filler_tokens")
        if self.name == BASE_CORPUS_LEVEL and self.filler_tokens != 0:
            raise ValueError("the base level is the world with no filler added")


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


# --- The cells -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GroupDecision:
    """Whether the cells of a conditional group run, with the reason exactly when they do not.

    >>> GroupDecision(False, None)
    Traceback (most recent call last):
    ...
    ValueError: a group that is not run says why, and one that is run gives no reason
    """

    run: bool
    reason: str | None

    def __post_init__(self) -> None:
        stated = self.reason is not None and bool(self.reason.strip())
        if self.run == stated or (self.run and self.reason is not None):
            raise ValueError(
                "a group that is not run says why, and one that is run gives no reason"
            )


@dataclass(frozen=True, slots=True)
class ConditionalGroup:
    """Cells that run together or not at all: the rule that decides it, in words, and the
    one decision, pending until it is made."""

    name: str
    rule: str
    decision: GroupDecision | Pending

    def __post_init__(self) -> None:
        require_opaque_id(self.name, "a conditional group")
        if not self.rule.strip():
            raise ValueError(f"the conditional group {self.name} states its rule")

    @property
    def runs(self) -> bool:
        """Whether the group is decided as run; a pending decision is not."""
        return isinstance(self.decision, GroupDecision) and self.decision.run


@dataclass(frozen=True, slots=True)
class RegisteredCell:
    """One system under one assigned condition at one corpus level, each by its registered
    name, and the conditional group it belongs to, if any."""

    system: SystemKind
    condition: str
    level: str
    group: str | None

    @property
    def place(self) -> tuple[SystemKind, str, str]:
        """What identifies the cell: a system, a condition and a level are listed once."""
        return (self.system, self.condition, self.level)


# --- Run accounting ------------------------------------------------------------------------


class MissingRunRule(StrEnum):
    """How an intended run that was never made counts toward end-to-end success."""

    NOT_PASSED = "not_passed"
    LEFT_OUT = "left_out"


class CountedAttemptRule(StrEnum):
    """Which attempt of a retried run is the run, among the attempts numbered within the
    registered maximum.

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
    """How runs are repeated, retried and counted, the bound a logical call is re-dispatched
    under inside a run, and the estimand that follows in words."""

    repeats: int
    missing_run: MissingRunRule
    retry: RetryRule
    counted_attempt: CountedAttemptRule
    redispatch: RedispatchPolicy | Pending
    estimand: str

    def __post_init__(self) -> None:
        require_integer(self.repeats, "repeats", minimum=1)
        if not self.estimand.strip():
            raise ValueError("the estimand is stated")


# --- The stated-fact contract --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EntrySchema:
    """The parser a model's stated facts are read by and the digest of the schema it reads."""

    parser: str
    digest: str

    def __post_init__(self) -> None:
        require_opaque_id(self.parser, "a parser's identifier")
        require_digest(self.digest, "the entry schema's digest")


@dataclass(frozen=True, slots=True)
class StatedFactContract:
    """What the registration binds of how stated facts become claims.

    ``composing_policy`` is the one policy every rules-composed system composes under. Its
    specification is the harness's, so the harness compares the registered value with what
    it computes; an evaluator cannot, and holds each export's recorded policy to it. An
    equal digest there shows the export recorded the registered identity and verifies no
    implementation. ``anchor_table`` is the digest of the anchor guard's table: the
    composing digest covers it, and it is registered apart because it is the part an
    evaluator can compute and must refuse on. ``entry_schema`` is pending until the system
    that emits facts is built.
    """

    composing_policy: ComposingPolicy
    anchor_table: str
    entry_schema: EntrySchema | Pending

    def __post_init__(self) -> None:
        require_digest(self.anchor_table, "the anchor table's digest")


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


def _require_breakdowns(breakdowns: tuple[StratumLevel, ...]) -> None:
    _require_listed_once(breakdowns, "the breakdowns")
    if StratumLevel.OVERALL in breakdowns:
        raise ValueError("the overall contrast is the comparison itself, never a breakdown of it")


@dataclass(frozen=True, slots=True)
class Comparison:
    """One registered comparison between two systems: a check under a reading, at one
    condition and corpus level, the systems in the order the difference is taken.

    The overall contrast is the comparison. ``breakdowns`` are the cuts named in advance to
    be shown beside it, supporting results from which no claim is made.
    """

    check: str
    reading: CheckReading
    condition: str
    level: str
    systems: tuple[SystemKind, SystemKind]
    breakdowns: tuple[StratumLevel, ...]

    def __post_init__(self) -> None:
        if self.systems[0] is self.systems[1]:
            raise ValueError("a comparison is between two systems")
        _require_breakdowns(self.breakdowns)


@dataclass(frozen=True, slots=True)
class Place:
    """Where a comparison is made: one condition at one corpus level."""

    condition: str
    level: str


@dataclass(frozen=True, slots=True)
class DescriptiveComparisons:
    """The descriptive comparisons: every pair at every named place and stratum level, on
    every check in every reading and on every measure. The places are named outright and
    are no product of conditions and levels, since not every condition runs at every
    level. The measures are in the order they are shown, the leading one first."""

    places: tuple[Place, ...]
    pairs: tuple[tuple[SystemKind, SystemKind], ...]
    strata: tuple[StratumLevel, ...]
    checks: tuple[str, ...]
    readings: tuple[CheckReading, ...]
    measures: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("places", "pairs", "strata", "checks", "readings", "measures"):
            _require_listed_once(getattr(self, name), f"the descriptive {name}")
        if any(first is second for first, second in self.pairs):
            raise ValueError("a comparison is between two systems")
        if len({frozenset(pair) for pair in self.pairs}) != len(self.pairs):
            raise ValueError("a pair of systems is compared once, in one order")


@dataclass(frozen=True, slots=True)
class LevelContrast:
    """One system against itself across two corpus levels, the first less the second, under
    one condition, paired by scenario. It measures sensitivity to the registered padding
    and does not say why a system changed; the answers do not differ between levels, so it
    compares one question."""

    system: SystemKind
    check: str
    reading: CheckReading
    condition: str
    levels: tuple[str, str]
    breakdowns: tuple[StratumLevel, ...]

    def __post_init__(self) -> None:
        if self.levels[0] == self.levels[1]:
            raise ValueError("a level contrast is between two levels")
        _require_breakdowns(self.breakdowns)


@dataclass(frozen=True, slots=True)
class MechanismMeasure:
    """The measure that says where a system succeeded or failed on the way to its report:
    a name and its stages in order, each over the same denominator. It carries no headline
    claim."""

    name: str
    stages: tuple[str, ...]

    def __post_init__(self) -> None:
        require_opaque_id(self.name, "the mechanism measure")
        if not self.stages:
            raise ValueError("the mechanism measure names its stages")
        for stage in self.stages:
            require_opaque_id(stage, "a stage of the mechanism measure")
        _require_listed_once(self.stages, "the stages")


@dataclass(frozen=True, slots=True)
class HeadroomProcedure:
    """How a place's headroom is characterized: the scenarios the reference system does not
    already pass on the check, under the reading. A diagnostic computed after the procedure
    is frozen; it selects no scenario and no cell."""

    reference: SystemKind
    check: str
    reading: CheckReading


@dataclass(frozen=True, slots=True)
class Statistics:
    """The estimation settings, the named checks and measures, and what is compared.

    The names are identifiers the evaluator resolves against its own registry; a name it
    does not hold is its refusal, not this type's. ``primary`` is the one comparison a
    claim is made from. ``secondary`` and ``level_contrasts`` are named in advance and
    carry none.
    """

    confidence_percent: int
    seed: int
    resamples: int
    interval_method: str
    checks: tuple[str, ...]
    measures: tuple[str, ...]
    primary: Comparison
    secondary: tuple[Comparison, ...]
    descriptive: DescriptiveComparisons
    level_contrasts: tuple[LevelContrast, ...]
    mechanism: MechanismMeasure | Pending
    headroom: HeadroomProcedure

    def __post_init__(self) -> None:
        require_integer(self.confidence_percent, "confidence_percent", minimum=1)
        if self.confidence_percent > 99:
            raise ValueError(
                f"a confidence level lies strictly between 0 and 100 percent, "
                f"got {self.confidence_percent}"
            )
        require_integer(self.seed, "seed")
        require_integer(self.resamples, "resamples", minimum=1)
        require_opaque_id(self.interval_method, "the interval method")
        for names, what in ((self.checks, "a check"), (self.measures, "a measure")):
            for name in names:
                require_opaque_id(name, what)
        _require_listed_once(self.checks, "the checks")
        _require_listed_once(self.measures, "the measures")
        _require_listed_once(self.secondary, "the secondary comparisons")
        _require_listed_once(self.level_contrasts, "the level contrasts")
        if self.primary in self.secondary:
            raise ValueError("the primary comparison is not also a secondary one")
        used_checks = {self.primary.check, self.headroom.check, *self.descriptive.checks}
        used_checks.update(comparison.check for comparison in self.secondary)
        used_checks.update(contrast.check for contrast in self.level_contrasts)
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


# --- The supporting comparisons ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SupportingSystem:
    """One side of a supporting comparison: a system kind and the label of its variant."""

    kind: SystemKind
    variant: str

    def __post_init__(self) -> None:
        require_opaque_id(self.variant, "a supporting system's variant")


@dataclass(frozen=True, slots=True)
class NotBuilt:
    """A supporting comparison that is not built: why, and the development number the
    decision rests on where there is one."""

    reason: str
    development_number: str | None

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("a comparison that is not built says why")


@dataclass(frozen=True, slots=True)
class SupportingComparison:
    """One prespecified supporting comparison, declared and not executed from here.

    ``systems`` are in the order the difference is taken. ``other_model`` names a model
    other than the registered systems' for the comparison's two sides, and is ``None``
    when they run under the registered one. ``endpoint`` and ``analysis`` are names.
    ``inclusion`` is pending or not built: this format registers one system per kind, so
    it cannot state that a supporting system is included, and the format that registers
    one arrives with the first that is built.
    """

    identifier: str
    condition: str
    level: str
    systems: tuple[SupportingSystem, SupportingSystem]
    other_model: str | None | Pending
    endpoint: str
    analysis: str
    inclusion: NotBuilt | Pending

    def __post_init__(self) -> None:
        require_opaque_id(self.identifier, "a supporting comparison")
        if self.systems[0] == self.systems[1]:
            raise ValueError(f"the supporting comparison {self.identifier} is between two systems")
        if isinstance(self.other_model, str):
            require_opaque_id(self.other_model, "a model")
        require_opaque_id(self.endpoint, "an endpoint")
        require_opaque_id(self.analysis, "an analysis")


# --- The prefetch and the budget -----------------------------------------------------------


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


# --- The registration ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Registration:
    """The preregistration whole; see the module for its lifecycle and what each part fixes.

    Beyond each section's own shape it holds what only the whole can check. A system kind,
    a level, a group and a supporting comparison are each registered once, and the base
    level is. A cell names a registered system, condition, level and group, and is listed
    once; a group holds a cell. A comparison is between cells that are registered, under
    an answer-quality condition. The headroom's reference is a registered system. And the
    lifecycle: a draft names no frozen commit; a frozen registration has nothing pending
    but its world's version, which is pending, with calibrated numbers and no scenario
    tuned on; a bound one has nothing pending at all and names the frozen commit it binds.
    """

    format_version: int
    status: RegistrationStatus
    amendment: Amendment
    world: MeasuredWorld
    systems: tuple[RegisteredSystem, ...]
    corpus_levels: tuple[CorpusLevel, ...]
    outage: OutageSchedule
    cell_groups: tuple[ConditionalGroup, ...]
    cells: tuple[RegisteredCell, ...]
    run_accounting: RunAccounting
    attribution: AttributionTable | Pending
    stated_facts: StatedFactContract
    statistics: Statistics
    supporting: tuple[SupportingComparison, ...]
    prefetch: RegisteredPrefetch
    budget: Budget

    def __post_init__(self) -> None:
        if self.format_version != REGISTRATION_FORMAT_VERSION:
            raise ValueError(
                f"this code reads registration format {REGISTRATION_FORMAT_VERSION}, "
                f"got {self.format_version}"
            )
        self._require_each_registered_once()
        self._require_cells()
        self._require_comparisons()
        self._require_lifecycle()

    def system(self, kind: SystemKind) -> RegisteredSystem | None:
        """The registered system of ``kind``, or ``None``."""
        for system in self.systems:
            if system.kind is kind:
                return system
        return None

    def level(self, name: str) -> CorpusLevel | None:
        """The registered corpus level named ``name``, or ``None``."""
        for level in self.corpus_levels:
            if level.name == name:
                return level
        return None

    def group(self, name: str) -> ConditionalGroup | None:
        """The conditional group named ``name``, or ``None``."""
        for group in self.cell_groups:
            if group.name == name:
                return group
        return None

    def cell(self, system: SystemKind, condition: str, level: str) -> RegisteredCell | None:
        """The registered cell of ``system`` under ``condition`` at ``level``, or ``None``."""
        for cell in self.cells:
            if cell.place == (system, condition, level):
                return cell
        return None

    def runs(self, cell: RegisteredCell) -> bool:
        """Whether ``cell`` is to be executed and reported: it belongs to no conditional
        group, or to one decided as run."""
        if cell.group is None:
            return True
        group = self.group(cell.group)
        return group is not None and group.runs

    def _require_each_registered_once(self) -> None:
        for names, what in (
            ([system.kind.value for system in self.systems], "a system kind"),
            ([level.name for level in self.corpus_levels], "a corpus level"),
            ([group.name for group in self.cell_groups], "a conditional group"),
            ([entry.identifier for entry in self.supporting], "a supporting comparison"),
        ):
            if len(set(names)) != len(names):
                raise ValueError(f"{what} is registered once, got {names}")
        if self.level(BASE_CORPUS_LEVEL) is None:
            raise ValueError(f"the {BASE_CORPUS_LEVEL} corpus level is registered")

    def _require_cells(self) -> None:
        if not self.cells:
            raise ValueError(
                "at least one cell is registered: a system under an assigned condition at a level"
            )
        places = [cell.place for cell in self.cells]
        if len(set(places)) != len(places):
            raise ValueError("a cell is registered once")
        for cell in self.cells:
            self._require_registered(cell.system, cell.condition, cell.level, "a cell")
            if cell.group is not None and self.group(cell.group) is None:
                raise ValueError(f"a cell names a registered group, got {cell.group!r}")
        held = {cell.group for cell in self.cells}
        empty = [group.name for group in self.cell_groups if group.name not in held]
        if empty:
            raise ValueError(f"a conditional group holds at least one cell, got {empty}")

    def _require_comparisons(self) -> None:
        statistics = self.statistics
        for comparison in (statistics.primary, *statistics.secondary):
            for system in comparison.systems:
                self._require_compared(system, comparison.condition, comparison.level)
        for place in statistics.descriptive.places:
            for pair in statistics.descriptive.pairs:
                for system in pair:
                    self._require_compared(system, place.condition, place.level)
        for contrast in statistics.level_contrasts:
            for level in contrast.levels:
                self._require_compared(contrast.system, contrast.condition, level)
        if self.system(statistics.headroom.reference) is None:
            raise ValueError(
                "the headroom's reference is a registered system, got "
                f"{statistics.headroom.reference.value}"
            )
        for entry in self.supporting:
            if self.outage.condition(entry.condition) is None:
                raise ValueError(
                    f"a supporting comparison names a registered condition, got {entry.condition!r}"
                )
            if self.level(entry.level) is None:
                raise ValueError(
                    f"a supporting comparison names a registered level, got {entry.level!r}"
                )

    def _require_registered(
        self, system: SystemKind, condition: str, level: str, what: str
    ) -> None:
        if self.system(system) is None:
            raise ValueError(f"{what} names a registered system, got {system.value}")
        if self.outage.condition(condition) is None:
            raise ValueError(f"{what} names a registered condition, got {condition!r}")
        if self.level(level) is None:
            raise ValueError(f"{what} names a registered level, got {level!r}")

    def _require_compared(self, system: SystemKind, condition: str, level: str) -> None:
        self._require_registered(system, condition, level, "a comparison")
        registered = self.outage.condition(condition)
        assert registered is not None
        if registered.reporting is not ReportingScope.ANSWER_QUALITY:
            raise ValueError(
                f"a comparison is made under an answer-quality condition, got {condition!r}"
            )
        if self.cell(system, condition, level) is None:
            raise ValueError(
                f"a comparison is between registered cells, got {system.value} under "
                f"{condition!r} at {level!r}"
            )

    def _require_lifecycle(self) -> None:
        status = self.status
        world = self.world
        if (world.frozen_commit is not None) != (status is RegistrationStatus.BOUND):
            raise ValueError(
                "the frozen registration's commit is named exactly by a bound registration, "
                f"got {world.frozen_commit!r} under {status.value}"
            )
        if status is RegistrationStatus.DRAFT:
            return
        pending = list(pending_fields(self))
        if status is RegistrationStatus.FROZEN:
            if not isinstance(world.version, Pending):
                raise ValueError(
                    "a frozen registration fixes the procedure before its world exists, so "
                    "the world's version is pending; binding the world makes it bound"
                )
            pending.remove("world.version")
        if pending:
            raise ValueError(
                f"a {status.value} registration has nothing pending"
                f"{' but its world' if status is RegistrationStatus.FROZEN else ''}, "
                f"got {', '.join(pending)}"
            )
        unmeasured = [
            f"{system.kind.value} caps"
            for system in self.systems
            if system.caps.basis is Basis.UNMEASURED
        ]
        if self.budget.basis is Basis.UNMEASURED:
            unmeasured.append("budget")
        if unmeasured:
            raise ValueError(
                f"a {status.value} registration's numbers are calibrated, got unmeasured "
                f"{', '.join(unmeasured)}"
            )
        if world.tuned_scenarios:
            raise ValueError(
                f"a {status.value} registration is tuned on no scenario of its world, got "
                f"{world.tuned_scenarios}"
            )


def pending_fields(registration: Registration) -> tuple[str, ...]:
    """The registration's pending values by dotted name, in the file's order; empty when
    every choice is made."""
    found: list[str] = []
    if isinstance(registration.world.version, Pending):
        found.append("world.version")
    for system in registration.systems:
        found.extend(f"systems.{system.kind.value}.{name}" for name, _ in pending_in(system))
    found.extend(
        f"corpus_levels.{level.name}.filler_tokens"
        for level in registration.corpus_levels
        if isinstance(level.filler_tokens, Pending)
    )
    found.extend(
        f"cell_groups.{group.name}.decision"
        for group in registration.cell_groups
        if isinstance(group.decision, Pending)
    )
    if isinstance(registration.run_accounting.redispatch, Pending):
        found.append("run_accounting.redispatch")
    if isinstance(registration.attribution, Pending):
        found.append("attribution")
    if isinstance(registration.stated_facts.entry_schema, Pending):
        found.append("stated_facts.entry_schema")
    if isinstance(registration.statistics.mechanism, Pending):
        found.append("statistics.mechanism")
    for entry in registration.supporting:
        found.extend(
            f"supporting.{entry.identifier}.{name}"
            for name, value in (("other_model", entry.other_model), ("inclusion", entry.inclusion))
            if isinstance(value, Pending)
        )
    return tuple(found)


def blocking(registration: Registration, kind: SystemKind) -> tuple[str, ...]:
    """The pending values an execution of the registered system of ``kind`` needs, by dotted
    name: its own, and for a system that calls a model the three every dispatch and every
    stated fact is read under, the attribution table, the re-dispatch policy and the entry
    schema. Empty when the system can be executed and compared as registered.

    A system the registration does not hold blocks nothing; that it is absent is the
    caller's to say. A level's pending size blocks no system: which documents a level holds
    is the world's, and a system that reads none runs the same at each.
    """
    system = registration.system(kind)
    if system is None:
        return ()
    found = [f"systems.{kind.value}.{name}" for name, _ in pending_in(system)]
    if isinstance(system, RulesOnlySystem):
        return tuple(found)
    for name, value in (
        ("run_accounting.redispatch", registration.run_accounting.redispatch),
        ("attribution", registration.attribution),
        ("stated_facts.entry_schema", registration.stated_facts.entry_schema),
    ):
        if isinstance(value, Pending):
            found.append(name)
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
    "Comparison",
    "ConditionalGroup",
    "CorpusLevel",
    "CountedAttemptRule",
    "DescriptiveComparisons",
    "EntrySchema",
    "FullContextSystem",
    "GroupDecision",
    "HeadroomProcedure",
    "Injection",
    "LevelContrast",
    "MeasuredWorld",
    "MechanismMeasure",
    "MissingRunRule",
    "NotBuilt",
    "OutageSchedule",
    "Pending",
    "Place",
    "RegisteredCaps",
    "RegisteredCell",
    "RegisteredCondition",
    "RegisteredPrefetch",
    "RegisteredRole",
    "RegisteredSystem",
    "Registration",
    "RegistrationStatus",
    "RetryRule",
    "Roles",
    "RulesOnlySystem",
    "RunAccounting",
    "SingleShotSystem",
    "StatedFactContract",
    "Statistics",
    "StratumLevel",
    "SupportingComparison",
    "SupportingSystem",
    "blocking",
    "condition_id",
    "pending_fields",
    "pending_in",
    "roles_of",
    "schedule_digest",
]
