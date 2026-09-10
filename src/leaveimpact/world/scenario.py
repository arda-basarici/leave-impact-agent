"""The scenario vocabulary: what a run is asked, what the evaluator expects, what the world planted.

Three records with three audiences (DESIGN, "Benchmark state is split by audience and
authority"). ``ScenarioSpec`` is the agent-visible half — which scenario, which leave,
``now`` in its reference timezone, the owned window — and holds nothing that changes an
answer. ``ScenarioKey`` is evaluator-only: the planted impacts each with the coverage
outcome truth expects, the constraints that apply, the bounded ``must_assess`` set with
authored verdicts, the named distractors with the reason each is wrong, the stable-now
interval, the sources a complete investigation needs, and the tags a result is reported
under. ``Scenario`` is the construction record that carries both beside the entities the
scenario owns and the facts only a world can plant; the world milestone's later step
decides how these become sealed artifacts, which is why nothing here serializes.

Two contract rules shape the key. The expected answer is an outcome per impact —
``assign``, ``uncovered`` or ``unknown`` — never a reference plan: the assessment is
relational and no optimization rule declares a best person, so an expected assignee set
would be a preference smuggled in as truth. And verdicts under a tool-failure run are
not stored: the evaluator derives them per run condition from the fact base and the
closure declarations, so the key authors verdicts for the normal condition only, where
a modifier may amend a candidate's verdict but never the class's outcome (the modifier
ruling at the scenario-framework step).

``Planted`` is the world's counterpart of ``Observed``: an entity with the world date it
became visible. Derivation takes that date as a parameter because when a fact became
observable is the caller's knowledge, not the record's, and here the caller is the
world that planted it.
"""

# No deferred annotations here: pdoc resolves a PEP 695 type parameter only when the
# signature evaluates it, and nothing in this module needs a forward reference.
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from leaveimpact.core.claims import (
    AssessmentReason,
    ConstraintKey,
    CoverageActionKind,
    ImpactKey,
    Verdict,
)
from leaveimpact.core.entities import CalendarEvent, Document, Leave, WorkItem
from leaveimpact.core.enums import Source
from leaveimpact.core.facts import Fact
from leaveimpact.core.ids import EmployeeId, LeaveId, ScenarioId
from leaveimpact.core.ports.observed import Entity
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.worldtime import DateSpan, local_date, require_aware


class Tier(StrEnum):
    """How far the reasoning has to reach (DESIGN, "The first golden set")."""

    STRUCTURED = "structured"
    FRAGMENTED = "fragmented"
    ADVERSARIAL = "adversarial"


class ScenarioClassName(StrEnum):
    """What a scenario is about — the second reporting axis under the tiers."""

    STRUCTURED_DEADLINE = "structured_deadline"
    STRUCTURED_MEETING = "structured_meeting"
    STRUCTURED_MIXED = "structured_mixed"
    FREE_TEXT_QUALIFICATION = "free_text_qualification"
    FREE_TEXT_RESPONSIBILITY = "free_text_responsibility"
    RELEASE_CARDINALITY_CONSTRAINT = "release_cardinality_constraint"
    FRAGMENTED_COMPOSITE = "fragmented_composite"
    STALE_SOURCE_CONFLICT = "stale_source_conflict"
    MISSING_INFORMATION = "missing_information"
    UNCOVERED = "uncovered"
    ADVERSARIAL_COMPOSITE = "adversarial_composite"


class ModifierName(StrEnum):
    """Orthogonal tags on a scenario: distractors and candidate pressure, never classes."""

    WRONG_TEAM = "wrong_team"
    ALREADY_RESOLVED = "already_resolved"
    OUTSIDE_WINDOW = "outside_window"
    TIMEZONE_BOUNDARY = "timezone_boundary"
    CONCURRENT_LEAVE = "concurrent_leave"


class DistractorReason(StrEnum):
    """Why a planted near-miss is not an impact — the bucket a false positive is graded into."""

    OUTSIDE_WINDOW = "outside_window"
    WRONG_TEAM = "wrong_team"
    ALREADY_RESOLVED = "already_resolved"
    STALE_DOCUMENT = "stale_document"
    TIMEZONE_BOUNDARY = "timezone_boundary"


@dataclass(frozen=True, slots=True)
class Planted[T: Entity]:
    """``entity`` as the world planted it, visible from ``observable_from`` in world time.

    The date is the world's knowledge, distinct from any date the entity itself carries: a
    ticket due in October planted in March is observable from March.
    """

    entity: T
    observable_from: date


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """What a run is asked: the scenario, the leave under investigation, ``now``, the window.

    ``now`` is an aware instant and ``reference_timezone`` the zone a human reads it in;
    ``today`` is that reading. The window is the slice of world state the scenario owns,
    and ``now`` falls inside it.

    >>> from datetime import UTC
    >>> from leaveimpact.core.ids import leave_id, scenario_id
    >>> spec = ScenarioSpec(scenario_id(1), leave_id(1), datetime(2026, 3, 5, 6, 0, tzinfo=UTC),
    ...                     "Europe/Istanbul", DateSpan(date(2026, 3, 1), date(2026, 3, 14)))
    >>> spec.today
    datetime.date(2026, 3, 5)
    """

    id: ScenarioId
    leave_id: LeaveId
    now: datetime
    reference_timezone: str
    window: DateSpan

    def __post_init__(self) -> None:
        require_aware(self.now, "now")
        if not self.window.contains(self.today):
            raise ValueError(
                f"a scenario's now falls inside its window, got {self.today} outside "
                f"{self.window.start}..{self.window.end}"
            )

    @property
    def today(self) -> date:
        """The calendar day ``now`` reads as in the reference timezone."""
        return local_date(self.now, self.reference_timezone)


@dataclass(frozen=True, slots=True)
class AuthoredVerdict:
    """A ``must_assess`` candidate's expected verdict, with the failing criteria when non-viable.

    Reasons accompany exactly the non-viable verdict: a viable candidate fails nothing,
    and an unknown one derives from unknown claims rather than from a reason class.

    >>> from leaveimpact.core.ids import employee_id
    >>> AuthoredVerdict(employee_id(3), Verdict.VIABLE, (AssessmentReason.SKILL,))
    Traceback (most recent call last):
    ...
    ValueError: reasons accompany a non-viable verdict only, got viable with ('skill',)
    """

    employee_id: EmployeeId
    verdict: Verdict
    reasons: tuple[AssessmentReason, ...] = ()

    def __post_init__(self) -> None:
        non_viable = self.verdict is Verdict.NON_VIABLE
        if non_viable and not self.reasons:
            raise ValueError(
                f"a non-viable verdict names its reasons, got none for {self.employee_id}"
            )
        if not non_viable and self.reasons:
            raise ValueError(
                f"reasons accompany a non-viable verdict only, got {self.verdict.value} with "
                f"{tuple(reason.value for reason in self.reasons)}"
            )


@dataclass(frozen=True, slots=True)
class NamedDistractor:
    """A planted near-miss and why it is not an impact, so a false positive reads as a sentence."""

    entity: EntityRef
    reason: DistractorReason


@dataclass(frozen=True, slots=True)
class ExpectedImpact:
    """A planted impact, the outcome truth expects for it, and the candidates the key authors.

    ``must_assess`` is bounded and per impact because an assessment keys on the impact:
    the same person can be viable for a deadline and busy for a meeting in one scenario.
    """

    key: ImpactKey
    outcome: CoverageActionKind
    must_assess: tuple[AuthoredVerdict, ...]

    def __post_init__(self) -> None:
        candidates = [authored.employee_id for authored in self.must_assess]
        if len(set(candidates)) != len(candidates):
            raise ValueError(f"a candidate is authored once per impact, got {candidates}")


@dataclass(frozen=True, slots=True)
class VerdictOverride:
    """A modifier's declared effect on one candidate's verdict for one impact."""

    impact: ImpactKey
    verdict: AuthoredVerdict


@dataclass(frozen=True, slots=True)
class ModifierEffect:
    """What a modifier declares it did to the expectations: verdicts amended, distractors added.

    Declarative on purpose: the framework composes the class's expectations with every
    modifier's effect and only then compares the composition with the rules, so the rules
    verify the construction and never generate the expected answer.
    """

    verdict_overrides: tuple[VerdictOverride, ...] = ()
    distractors: tuple[NamedDistractor, ...] = ()


@dataclass(frozen=True, slots=True)
class ScenarioKey:
    """The evaluator's half: what truth expects of a run over this scenario.

    ``required_sources`` are the systems a complete investigation must have read;
    ``stable_interval`` is the run of days over which any ``now`` yields this same key.
    """

    scenario_id: ScenarioId
    tier: Tier
    scenario_class: ScenarioClassName
    modifiers: tuple[ModifierName, ...]
    impacts: tuple[ExpectedImpact, ...]
    constraints: tuple[ConstraintKey, ...]
    distractors: tuple[NamedDistractor, ...]
    stable_interval: DateSpan
    required_sources: tuple[Source, ...]

    def __post_init__(self) -> None:
        if not self.impacts:
            raise ValueError(f"a scenario plants at least one impact, {self.scenario_id} has none")
        keys = [expected.key for expected in self.impacts]
        if len(set(keys)) != len(keys):
            raise ValueError(f"impact keys are unique within a scenario, got {keys}")
        for name, values in (
            ("modifiers", self.modifiers),
            ("constraints", self.constraints),
            ("required_sources", self.required_sources),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{name} are listed once each, got {values}")
        # A distractor is one entity with one planted reason: a false positive is graded
        # into the bucket of that reason, and an entity in two buckets would count one
        # mistake twice. An entity wrong for two reasons becomes a tuple of reasons on
        # the record when a class needs it, never a second entry.
        distracting = [distractor.entity for distractor in self.distractors]
        if len(set(distracting)) != len(distracting):
            raise ValueError(f"a distractor entity is listed once, got {distracting}")
        artifacts = {expected.key.artifact for expected in self.impacts}
        both = sorted(ref.id for ref in artifacts & set(distracting))
        if both:
            raise ValueError(
                f"an expected impact's artifact is never also a near-miss, got {both} as both"
            )


@dataclass(frozen=True, slots=True)
class OwnedEntities:
    """The mutable entities one scenario owns and no other scenario touches.

    Policies are world-owned and selected; a runbook or client note planted for this
    scenario is owned by it (the ownership ruling at the scenario-framework step).
    """

    leaves: tuple[Planted[Leave], ...] = ()
    work_items: tuple[Planted[WorkItem], ...] = ()
    events: tuple[Planted[CalendarEvent], ...] = ()
    documents: tuple[Planted[Document], ...] = ()


@dataclass(frozen=True, slots=True)
class Scenario:
    """The construction record: spec and key together, the owned entities, the authored facts.

    ``authored_facts`` are the facts only a world can plant — a skill evidenced in a
    comment, an owner a runbook asserts, what a clause requires — stated as facts beside
    the prose that will carry them; the prose is a rendering of the fact, never its source.
    """

    spec: ScenarioSpec
    key: ScenarioKey
    owned: OwnedEntities
    authored_facts: tuple[Fact, ...] = ()

    def __post_init__(self) -> None:
        """Refuse three records that cannot describe one scenario.

        Structural coherence only — the same scenario id, impacts of the investigated
        leave, that leave owned and inside the window, ``today`` before it, the stable
        interval inside the window around ``today`` and ending before the leave. Whether
        the interval is the *maximal* one for the planted facts is the framework's
        derivation and the validator's check, never re-run here.
        """
        if self.spec.id != self.key.scenario_id:
            raise ValueError(
                f"spec and key name one scenario, got {self.spec.id} and {self.key.scenario_id}"
            )
        leave = self.investigated_leave.span
        foreign = [e.key for e in self.key.impacts if e.key.leave_id != self.spec.leave_id]
        if foreign:
            raise ValueError(
                f"every impact is the investigated leave's ({self.spec.leave_id}), got impacts "
                f"of {sorted({key.leave_id for key in foreign})}"
            )
        window, today, stable = self.spec.window, self.spec.today, self.key.stable_interval
        if not (window.contains(leave.start) and window.contains(leave.end)):
            raise ValueError(
                f"the investigated leave lies inside the owned window, got {leave.start}.."
                f"{leave.end} against {window.start}..{window.end}"
            )
        if today >= leave.start:
            raise ValueError(
                f"now precedes the leave, got today {today} and leave from {leave.start}"
            )
        if not (window.contains(stable.start) and stable.end < leave.start):
            raise ValueError(
                f"the stable interval lies inside the window and ends before the leave, got "
                f"{stable.start}..{stable.end} against window {window.start}..{window.end} and "
                f"leave from {leave.start}"
            )
        if not stable.contains(today):
            raise ValueError(
                f"the stable interval contains today, got {stable.start}..{stable.end} and {today}"
            )

    @property
    def investigated_leave(self) -> Leave:
        """The owned leave the spec names."""
        for planted in self.owned.leaves:
            if planted.entity.id == self.spec.leave_id:
                return planted.entity
        owned = sorted(planted.entity.id for planted in self.owned.leaves)
        raise ValueError(
            f"the investigated leave is one the scenario owns, {self.spec.leave_id} is not "
            f"among {owned}"
        )
