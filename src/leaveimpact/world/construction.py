"""Scenario construction: a class selects and plants, modifiers amend, the framework verifies.

Constructive selection, never rejection sampling (the selection ruling at the
scenario-framework step). A scenario class states what it needs from the static
organization as a query — ``admissible`` returns every construction the org affords, in
a canonical order the class guarantees — and the RNG only chooses among them. The
chosen construction plants the scenario's owned entities and authors its expectations:
the impacts with the outcome each expects and the ``must_assess`` candidates with their
verdicts. Modifiers have the same shape minus an outcome: each returns the amendments it
admits over the draft so far, and a chosen amendment plants more and declares its
effect on the expectations. The framework then composes the class's expectations with
every declared effect, derives the stable interval from what was planted, and only then
runs ``core``'s rules over the truth base as an independent check: every authored
verdict must equal the rule's, and every declared outcome must equal the truth outcome
over the whole candidate universe. A mismatch is a named construction error, never a
retry and never a silent reclassification.

Two properties this protects. The rules verify the construction and do not generate the
expected answer, so a shared rule bug cannot manufacture a world and a key that agree
with each other by construction. And a query is weaker than the rule on purpose — it
filters static affordances, the rule judges the planted scenario — because a query that
grew to mirror the rule in reverse would make the invariant's independence a fiction.

A modifier may amend a candidate's verdict and may not change the class's declared
outcome; that is the definition of "orthogonal" made testable, and the outcome check
after composition is where it fails.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from random import Random
from typing import Protocol

from leaveimpact.core.claims import ConstraintKey, ImpactKey
from leaveimpact.core.closure import Unresolved
from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.facts import Fact, FactBase, FactView, RunCondition
from leaveimpact.core.ids import (
    ClauseId,
    CommentId,
    DocumentId,
    EmployeeId,
    EventId,
    LeaveId,
    ScenarioId,
    WorkItemId,
    clause_id,
    comment_id,
    document_id,
    event_id,
    leave_id,
    work_item_id,
)
from leaveimpact.core.plans import expected_action, required_count
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.viability import (
    ResolvedRequirement,
    applicable_requirements,
    assess_impact,
    need_of,
)
from leaveimpact.core.worldtime import DateSpan, local_date
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import (
    ExpectedImpact,
    ModifierEffect,
    ModifierName,
    NamedDistractor,
    OwnedEntities,
    Scenario,
    ScenarioClassName,
    ScenarioKey,
    ScenarioSpec,
    Tier,
)
from leaveimpact.world.slices import place_leave, place_now, stable_interval
from leaveimpact.world.truth_facts import truth_fact_base

# --- Errors ---------------------------------------------------------------------------


class ConstructionError(Exception):
    """A scenario could not be constructed as declared; generation stops here, named."""


class MissingAffordance(ConstructionError):
    """The organization (or the draft) affords no construction of what was asked."""

    def __init__(self, who: str, requirement: str) -> None:
        super().__init__(f"{who} found no admissible construction: needs {requirement}")
        self.who = who
        self.requirement = requirement


class ConflictingEffects(ConstructionError):
    """Two declared effects, or an effect and the class, claim the same expectation."""


class ScenarioInvariantFailed(ConstructionError):
    """The composed expectations disagree with the rules over the planted world."""

    def __init__(self, scenario_id: ScenarioId, problems: Sequence[str]) -> None:
        super().__init__(f"{scenario_id}: " + "; ".join(problems))
        self.scenario_id = scenario_id
        self.problems = tuple(problems)


# --- The frame a construction plants into ---------------------------------------------


class Minting:
    """The world's id book: world-wide numbering for the records scenarios plant.

    Ids are world-wide (``ticket_042`` names one ticket in every system), so one book
    serves every scenario of a world and is threaded through each frame. Deterministic
    because construction is sequential and draws nothing.
    """

    def __init__(self) -> None:
        self._next: dict[EntityKind, int] = {}

    def _take(self, kind: EntityKind) -> int:
        number = self._next.get(kind, 1)
        self._next[kind] = number + 1
        return number

    def leave(self) -> LeaveId:
        return leave_id(self._take(EntityKind.LEAVE))

    def work_item(self) -> WorkItemId:
        return work_item_id(self._take(EntityKind.WORK_ITEM))

    def comment(self) -> CommentId:
        return comment_id(self._take(EntityKind.COMMENT))

    def event(self) -> EventId:
        return event_id(self._take(EntityKind.EVENT))

    def document(self) -> DocumentId:
        return document_id(self._take(EntityKind.DOCUMENT))

    def clause(self) -> ClauseId:
        return clause_id(self._take(EntityKind.CLAUSE))


@dataclass(frozen=True, slots=True)
class Frame:
    """What the framework fixes before anything is planted: the scenario's identity and time.

    The leave span and ``now`` are placed by the framework so that every class inherits
    the same placement rules; a class plants relative to them and never chooses them.
    """

    scenario_id: ScenarioId
    window: DateSpan
    leave: DateSpan
    now: datetime
    reference_timezone: str
    world_start: date
    ids: Minting = field(compare=False)

    @property
    def today(self) -> date:
        """The calendar day ``now`` reads as in the reference timezone."""
        return local_date(self.now, self.reference_timezone)


# --- What a class and a modifier produce ----------------------------------------------


@dataclass(frozen=True, slots=True)
class Draft:
    """A scenario under construction: what has been planted and what is expected of it so far.

    ``investigated`` names the owned leave the run is about — the class says which, since
    a modifier may plant another leave over the same days. ``impacts`` carry the class's
    authored verdicts and declared outcomes; modifiers add to ``owned``, ``distractors``
    and ``authored_facts`` through ``extended`` and declare verdict changes through their
    effect, never by editing ``impacts`` in place.
    """

    owned: OwnedEntities
    investigated: LeaveId
    impacts: tuple[ExpectedImpact, ...]
    constraints: tuple[ConstraintKey, ...] = ()
    distractors: tuple[NamedDistractor, ...] = ()
    authored_facts: tuple[Fact, ...] = ()

    def __post_init__(self) -> None:
        # Refused here, before composition indexes impacts by key: a dict would keep the
        # last of two expectations for one impact and the key's own check would never
        # see the first — a silent normalization this module otherwise forbids.
        keys = [expected.key for expected in self.impacts]
        if len(set(keys)) != len(keys):
            raise ValueError(f"a draft states each impact once, got {keys}")

    def extended(
        self,
        *,
        owned: OwnedEntities | None = None,
        distractors: tuple[NamedDistractor, ...] = (),
        authored_facts: tuple[Fact, ...] = (),
    ) -> Draft:
        """This draft with more planted: owned entities merged, distractors and facts appended."""
        merged = self.owned
        if owned is not None:
            merged = OwnedEntities(
                leaves=self.owned.leaves + owned.leaves,
                work_items=self.owned.work_items + owned.work_items,
                events=self.owned.events + owned.events,
                documents=self.owned.documents + owned.documents,
            )
        return replace(
            self,
            owned=merged,
            distractors=self.distractors + distractors,
            authored_facts=self.authored_facts + authored_facts,
        )


Construction = Callable[[Frame, Random], Draft]
"""One admissible way to plant a class's scenario, ready to run inside a frame."""

Amendment = Callable[[Draft, Frame, Random], tuple[Draft, ModifierEffect]]
"""One admissible way to apply a modifier to a draft: the extended draft and the declared effect."""


class ScenarioClass(Protocol):
    """What a scenario is about, as a selection query over the static org and a planting recipe.

    ``admissible`` returns every construction the organization affords, in an order that
    depends on nothing but the org — sorted by the ids involved is the usual form — so
    that the RNG's choice among them is reproducible. It is a query over static
    affordances and deliberately weaker than the rule: it never decides verdicts, the
    planted recipe authors them and the framework's invariant checks them. An empty
    tuple means the org lacks what the class needs, and ``affordance`` says what that is.
    """

    @property
    def name(self) -> ScenarioClassName: ...

    @property
    def tier(self) -> Tier: ...

    @property
    def affordance(self) -> str: ...

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]: ...


class Modifier(Protocol):
    """An orthogonal tag: what it needs from the org and the draft, and how it amends the draft.

    Same contract as a class for ``admissible`` — canonical order, empty when the draft
    lacks the structure the modifier works on (a work item to be already resolved, a
    meeting to sit on a timezone boundary). An amendment declares its effect on the
    expectations; the framework composes and the rules check.
    """

    @property
    def name(self) -> ModifierName: ...

    @property
    def affordance(self) -> str: ...

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]: ...


# --- Construction ---------------------------------------------------------------------


def construct(
    scenario_class: ScenarioClass,
    modifiers: Sequence[Modifier],
    org: OrgSpec,
    *,
    scenario_id: ScenarioId,
    window: DateSpan,
    world_start: date,
    reference_timezone: str,
    ids: Minting,
    rng: Random,
) -> Scenario:
    """One scenario of ``scenario_class`` with ``modifiers`` applied, verified against the rules.

    Raises ``MissingAffordance`` when the class or a modifier admits nothing,
    ``ConflictingEffects`` when declared effects collide, ``ScenarioInvariantFailed``
    when an authored verdict or a declared outcome disagrees with the rules over the
    planted world. Same org, same inputs, same RNG state give an equal scenario.
    """
    leave = place_leave(rng, window)
    frame = Frame(
        scenario_id,
        window,
        leave,
        place_now(rng, leave, reference_timezone),
        reference_timezone,
        world_start,
        ids,
    )
    draft = _choose(scenario_class.admissible(org), scenario_class, rng)(frame, rng)
    effects: list[ModifierEffect] = []
    for modifier in modifiers:
        amendment = _choose(modifier.admissible(org, draft), modifier, rng)
        draft, effect = amendment(draft, frame, rng)
        effects.append(effect)

    impacts = _compose(draft.impacts, effects)
    distractors = draft.distractors + tuple(d for effect in effects for d in effect.distractors)
    observability = [
        *_planted_dates(draft.owned),
        *(fact.observable_from for fact in draft.authored_facts),
    ]
    spec = ScenarioSpec(scenario_id, draft.investigated, frame.now, reference_timezone, window)
    base = truth_fact_base(org, world_start, [draft.owned], draft.authored_facts)
    problems = _verify(base, spec.today, impacts, draft.constraints, frame, org)
    required = _required_sources(
        base, spec.today, impacts, draft.constraints, frame, org, spec.leave_id
    )
    key = ScenarioKey(
        scenario_id=scenario_id,
        tier=scenario_class.tier,
        scenario_class=scenario_class.name,
        modifiers=tuple(modifier.name for modifier in modifiers),
        impacts=impacts,
        constraints=draft.constraints,
        distractors=distractors,
        stable_interval=stable_interval(window, leave, frame.today, observability),
        required_sources=tuple(sorted(required, key=lambda source: source.value)),
    )
    scenario = Scenario(spec, key, draft.owned, draft.authored_facts)
    if problems:
        raise ScenarioInvariantFailed(scenario_id, problems)
    return scenario


def _choose[T](options: tuple[T, ...], who: ScenarioClass | Modifier, rng: Random) -> T:
    if not options:
        raise MissingAffordance(who.name.value, who.affordance)
    return options[rng.randrange(len(options))]


def _planted_dates(owned: OwnedEntities) -> list[date]:
    """When each owned record became observable — the dates the stable interval derives from."""
    return [
        *(p.observable_from for p in owned.leaves),
        *(p.observable_from for p in owned.work_items),
        *(p.observable_from for p in owned.events),
        *(p.observable_from for p in owned.documents),
    ]


def _compose(
    impacts: tuple[ExpectedImpact, ...], effects: Sequence[ModifierEffect]
) -> tuple[ExpectedImpact, ...]:
    """The class's expectations with every declared verdict override applied, collisions refused."""
    by_key = {expected.key: expected for expected in impacts}
    claimed: set[tuple[ImpactKey, EmployeeId]] = set()
    for effect in effects:
        for override in effect.verdict_overrides:
            if override.impact not in by_key:
                raise ConflictingEffects(
                    f"an effect amends {override.impact}, which the class did not plant"
                )
            slot = (override.impact, override.verdict.employee_id)
            if slot in claimed:
                raise ConflictingEffects(
                    f"two effects amend {override.verdict.employee_id} for {override.impact}"
                )
            claimed.add(slot)
            expected = by_key[override.impact]
            who = override.verdict.employee_id
            kept = tuple(a for a in expected.must_assess if a.employee_id != who)
            by_key[override.impact] = replace(expected, must_assess=(*kept, override.verdict))
    return tuple(by_key.values())


def _verify(
    base: FactBase,
    today: date,
    impacts: Sequence[ExpectedImpact],
    constraints: Sequence[ConstraintKey],
    frame: Frame,
    org: OrgSpec,
) -> list[str]:
    """The rules' disagreements with the composed expectations under the normal run condition.

    Verdicts are checked per authored candidate; the outcome is the truth outcome over the
    whole organization, never over ``must_assess`` alone (the contract's rule). A
    candidate authored from outside the organization is a problem too, named rather
    than a lookup failure.
    """
    problems: list[str] = []
    view = base.at(today, RunCondition.all_reachable())
    universe = [employee.id for employee in org.employees]
    for expected in impacts:
        assessments = assess_impact(
            view, expected.key, universe, constraints, frame.leave, frame.reference_timezone
        )
        by_employee = {assessment.employee_id: assessment for assessment in assessments}
        for authored in expected.must_assess:
            actual = by_employee.get(authored.employee_id)
            if actual is None:
                problems.append(
                    f"{authored.employee_id} is authored for {expected.key.artifact.id} but is "
                    "not in the organization"
                )
                continue
            if (actual.verdict, actual.reasons) != (authored.verdict, authored.reasons):
                problems.append(
                    f"{authored.employee_id} for {expected.key.artifact.id}: authored "
                    f"{authored.verdict.value} {[r.value for r in authored.reasons]}, "
                    f"the rule says "
                    f"{actual.verdict.value} {[r.value for r in actual.reasons]}"
                )
        outcome = expected_action(
            (assessment.verdict for assessment in assessments),
            _required(view, expected.key, constraints, frame),
        )
        if outcome is not expected.outcome:
            problems.append(
                f"{expected.key.artifact.id}: declared {expected.outcome.value}, the truth outcome "
                f"is {outcome.value}"
            )
    return problems


def _required_sources(
    base: FactBase,
    today: date,
    impacts: Sequence[ExpectedImpact],
    constraints: Sequence[ConstraintKey],
    frame: Frame,
    org: OrgSpec,
    investigated: LeaveId,
) -> set[Source]:
    """The sources the key's rule-level conclusions depend on.

    Two kinds, and nothing else — a source hosting a named distractor is not one, since
    losing it changes no conclusion and distractor rejection is graded on its own list.
    The sources that establish what the run is about — the facts about each
    impact's artifact and the leave under investigation — read off the base. And the
    sources the rules depend on, found by asking, for each source in turn, whether the
    rules conclude anything different with that source unreachable: a verdict or an
    outcome that moves means the source was required. Provenance alone under-counts
    here, because a negative conclusion carries no evidence fact yet depends on every
    source of the predicate's declared domain — a candidate known not to hold a skill
    needs both the HR record and the tracker to have answered. Asking the rules under
    each outage captures that without the framework knowing what the rules read, and it
    is the tool-failure condition's own definition of dependence.
    """
    normal = base.at(today, RunCondition.all_reachable())
    sources: set[Source] = set()
    for expected in impacts:
        sources.update(f.source for f in normal.facts if f.subject == expected.key.artifact)
    sources.update(
        fact.source
        for fact in normal.facts_of(PredicateName.ON_LEAVE)
        if fact.evidence.target.id == investigated
    )
    baseline = _conclusions(normal, impacts, constraints, frame, org)
    for source in Source:
        outage = base.at(today, RunCondition.all_reachable().without(source))
        if _conclusions(outage, impacts, constraints, frame, org) != baseline:
            sources.add(source)
    return sources


def _conclusions(
    view: FactView,
    impacts: Sequence[ExpectedImpact],
    constraints: Sequence[ConstraintKey],
    frame: Frame,
    org: OrgSpec,
) -> tuple[object, ...]:
    """Everything the rules conclude in ``view``: verdicts, reasons, open questions, outcomes."""
    universe = [employee.id for employee in org.employees]
    concluded: list[object] = []
    for expected in impacts:
        assessments = assess_impact(
            view, expected.key, universe, constraints, frame.leave, frame.reference_timezone
        )
        # The unresolved questions travel too: an unknown for absence and an unknown for
        # an unreachable source are different conclusions with one verdict, and the
        # source that separates them was required.
        verdicts = tuple(
            (a.employee_id, a.verdict, a.reasons, a.unresolved) for a in assessments
        )
        outcome = expected_action(
            (a.verdict for a in assessments), _required(view, expected.key, constraints, frame)
        )
        concluded.append((verdicts, outcome))
    return tuple(concluded)


def _required(
    view: FactView, impact: ImpactKey, constraints: Sequence[ConstraintKey], frame: Frame
) -> int:
    need = need_of(view, impact, frame.leave, frame.reference_timezone)
    if isinstance(need, Unresolved):
        return 1
    resolved = [
        item
        for item in applicable_requirements(view, need, constraints)
        if isinstance(item, ResolvedRequirement)
    ]
    return required_count(resolved)
