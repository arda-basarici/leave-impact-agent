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

Two conclusions the key seals are derived rather than authored (the 15.5 rulings): the
conflicts on the facts the investigation read and the unknowns its assessments seed. A
class does not write those lists, since a blank record asked a skill is unknown under any
clause and a stale document is visible to every run; it asserts the constituents its
construction exists to produce (``Draft.required_conflicts``, ``required_unknowns``), and
construction refuses a scenario whose rules do not derive them, so the independence
above holds for what the class claims while the sealed set stays complete.

A modifier may amend a candidate's verdict and may not change the class's declared
outcome; that is the definition of "orthogonal" made testable, and the outcome check
after composition is where it fails.

Scenarios compose into one world, and a standing fact composes further than its own
key: a note naming a person responsible is read by every run in the world, a prose fact
giving a person a skill is evidence every run reads. The world's reservation book
(``Reservations``) records what each admitted scenario binds and refuses a later
candidate whose claims cross it, in both directions; the class's candidates are tried in
the seed's order and the first the book admits is planted, a refused one unplanted, so
the choice is still constructive selection over the class's enumerated constructions and
a class whose every construction crosses the book fails by name. The claims are derived
from the planted draft, never declared by the class, the briefs' discipline: a value a
class could get wrong is not a value the class writes.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from random import Random
from typing import Protocol

from leaveimpact.core.authority import conflicts_on
from leaveimpact.core.claims import AssessmentReason, ConstraintKey, ImpactKey, Verdict
from leaveimpact.core.closure import Unresolved
from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.facts import Fact, FactBase, FactView, RunCondition
from leaveimpact.core.grounding import Grounded, Grounding, derive_impacts, ground_impact
from leaveimpact.core.ids import (
    ClauseId,
    CommentId,
    DocumentId,
    EmployeeId,
    EventId,
    LeaveId,
    ScenarioId,
    SkillId,
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
from leaveimpact.core.refs import EntityRef, clause_ref, component_ref
from leaveimpact.core.values import Requirement, SkillCriterion
from leaveimpact.core.viability import (
    Assessment,
    ResolvedRequirement,
    applicable_requirements,
    assess_impact,
    need_of,
)
from leaveimpact.core.worldtime import DateSpan, local_date
from leaveimpact.world.briefs import (
    Brief,
    PendingProse,
    brief_for,
    check_allowed,
    check_pending,
    lexicon_of,
)
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.prose import FactRole
from leaveimpact.world.scenario import (
    ExpectedConflict,
    ExpectedImpact,
    ExpectedUnknown,
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
from leaveimpact.world.vocabulary import (
    LOOK_ALIKE_MEETING_PHRASES,
    LOOK_ALIKE_TICKET_PHRASES,
    MEETING_PHRASES,
    MEETING_QUALIFIERS,
    TICKET_PHRASES,
    TICKET_QUALIFIERS,
    titles,
)

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


MintingCheckpoint = tuple[dict[EntityKind, int], dict[tuple[str, str], list[str]]]
"""A copy of the id and title book's state, taken before a candidate plants."""


class Minting:
    """The world's id and title book: world-wide numbering for the records scenarios plant, and
    the titles a component's tickets and a team's meetings carry, each handed out once.

    Ids are world-wide (``ticket_042`` names one ticket in every system), so one book
    serves every scenario of a world and is threaded through each frame; numbering is
    deterministic because construction is sequential and draws nothing. Titles are minted
    here too, without replacement per context (the 15.3 rulings): a policy scopes itself by
    the title of the artifact it names, so a title naming two tickets or two meetings is a
    scope the prose cannot resolve even while the structured constraint stays exact. The
    supply for a context is the vocabulary's product of phrases and qualifiers, drawn from
    what remains with the scenario's own generator, so the choice is seeded and the
    capacity is finite and stated; an exhausted context is a generator invariant failing
    loud, never a retry. Look-alike titles are minted from their own phrases, disjoint from
    the real ones, so a distractor never shares a real artifact's title.
    """

    def __init__(self) -> None:
        self._next: dict[EntityKind, int] = {}
        self._remaining: dict[tuple[str, str], list[str]] = {}

    def _take(self, kind: EntityKind) -> int:
        number = self._next.get(kind, 1)
        self._next[kind] = number + 1
        return number

    def _mint_title(
        self,
        rng: Random,
        book: str,
        context: str,
        phrases: tuple[str, ...],
        qualifiers: tuple[str, ...],
    ) -> str:
        key = (book, context)
        if key not in self._remaining:
            self._remaining[key] = list(titles(context, phrases, qualifiers))
        remaining = self._remaining[key]
        if not remaining:
            raise ValueError(
                f"the {book} title supply for {context!r} is exhausted after "
                f"{len(phrases) * len(qualifiers)} titles"
            )
        title = rng.choice(remaining)
        remaining.remove(title)
        return title

    def checkpoint(self) -> MintingCheckpoint:
        """The book's state, to rewind to when a planted candidate is refused by the world's
        reservation book: what the candidate took goes back, so the admitted one numbers
        and titles as if the refused one never was."""
        return (
            dict(self._next),
            {key: list(remaining) for key, remaining in self._remaining.items()},
        )

    def rewind(self, checkpoint: MintingCheckpoint) -> None:
        taken, remaining = checkpoint
        self._next = dict(taken)
        self._remaining = {key: list(titles) for key, titles in remaining.items()}

    def ticket_title(self, rng: Random, component: str) -> str:
        """A title no other ticket of ``component`` carries in this world."""
        return self._mint_title(rng, "ticket", component, TICKET_PHRASES, TICKET_QUALIFIERS)

    def meeting_title(self, rng: Random, team: str) -> str:
        """A title no other meeting of ``team`` carries in this world."""
        return self._mint_title(rng, "meeting", team, MEETING_PHRASES, MEETING_QUALIFIERS)

    def look_alike_ticket_title(self, rng: Random, component: str) -> str:
        """A distractor ticket's title, unique among ``component``'s look-alikes and never a
        real ticket's."""
        return self._mint_title(
            rng, "look-alike ticket", component, LOOK_ALIKE_TICKET_PHRASES, TICKET_QUALIFIERS
        )

    def look_alike_meeting_title(self, rng: Random, team: str) -> str:
        """A distractor meeting's title, unique among ``team``'s look-alikes and never a real
        meeting's."""
        return self._mint_title(
            rng, "look-alike meeting", team, LOOK_ALIKE_MEETING_PHRASES, MEETING_QUALIFIERS
        )

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
    authored verdicts and declared outcomes; modifiers add to ``owned``, ``distractors``,
    ``authored_facts`` and ``pending`` through ``extended`` and declare verdict changes
    through their effect, never by editing ``impacts`` in place. ``pending`` is the prose
    the class leaves for a model: a target and the facts it must and may carry, which the
    framework completes into briefs. ``required_conflicts`` and ``required_unknowns`` are
    the constituents a class asserts its construction derives (the 15.5 rulings): the
    conflicts must be exactly these, since only a class that plants one declares it; the
    unknowns must include these, since a blank record asked a skill is unknown under any
    clause. The key seals what the rules derive, never these declarations.
    """

    owned: OwnedEntities
    investigated: LeaveId
    impacts: tuple[ExpectedImpact, ...]
    constraints: tuple[ConstraintKey, ...] = ()
    distractors: tuple[NamedDistractor, ...] = ()
    authored_facts: tuple[Fact, ...] = ()
    pending: tuple[PendingProse, ...] = ()
    required_conflicts: tuple[ExpectedConflict, ...] = ()
    required_unknowns: tuple[ExpectedUnknown, ...] = ()

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
        pending: tuple[PendingProse, ...] = (),
    ) -> Draft:
        """This draft with more planted: owned entities merged, the other tuples appended."""
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
            pending=self.pending + pending,
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


# --- The reservation book: what a scenario binds in the world beyond its own key -------


@dataclass(frozen=True, slots=True)
class Claims:
    """What a planted draft binds in the world beyond its own key: the standing facts and the
    absence-based conclusions another scenario's construction could contradict.

    Read off the draft, never declared (the 15.4 ruling on the reservation book).
    ``leave_subject`` is the investigated leave's person. ``standing_contacts`` are the
    people an authored fact names responsible: a document every run in the world reads,
    so any other leave of that person acquires a responsibility impact its key never
    declared. ``skills_provided`` are the (person, skill) pairs an authored fact evidences
    positive, prose every run reads. ``skills_required_absent`` are the (person, skill)
    pairs a conclusion assumes no positive fact exists for: an authored non-viable verdict
    by skill, where the record lacks the skills the applicable requirements ask, and a
    derived unknown by absence, where the record is blank (the 15.5 rulings); a positive
    fact elsewhere would turn either into a known true and move the verdict, and the sealed
    key with it. The names are the construction's terms, not any class's; what a class may
    share with another, a candidate, a viable person, is not here, since it contradicts
    nothing.
    """

    leave_subject: EmployeeId
    standing_contacts: frozenset[EmployeeId] = frozenset()
    skills_provided: frozenset[tuple[EmployeeId, SkillId]] = frozenset()
    skills_required_absent: frozenset[tuple[EmployeeId, SkillId]] = frozenset()


def claims_of(
    draft: Draft, org: OrgSpec, unknown_skills: Iterable[tuple[EmployeeId, SkillId]] = ()
) -> Claims:
    """The claims ``draft`` makes on the world, read off what it planted and authored, plus the
    (person, skill) pairs its derived unknowns assume no positive fact for."""
    by_id = {employee.id: employee for employee in org.employees}
    contacts: set[EmployeeId] = set()
    provided: set[tuple[EmployeeId, SkillId]] = set()
    absent: set[tuple[EmployeeId, SkillId]] = set()
    for fact in draft.authored_facts:
        if fact.predicate is PredicateName.NAMES_RESPONSIBLE and isinstance(fact.value, EntityRef):
            contacts.add(EmployeeId(fact.value.id))
        elif fact.predicate is PredicateName.HAS_SKILL and isinstance(fact.value, str):
            provided.add((EmployeeId(fact.subject.id), SkillId(fact.value)))
    for expected in draft.impacts:
        skills = _required_skills(draft, expected.key.artifact)
        for authored in expected.must_assess:
            if authored.verdict is not Verdict.NON_VIABLE:
                continue
            if AssessmentReason.SKILL not in authored.reasons:
                continue
            held = by_id[authored.employee_id].skills or ()
            absent.update((authored.employee_id, skill) for skill in skills if skill not in held)
    absent.update(unknown_skills)
    return Claims(_leaver_of(draft), frozenset(contacts), frozenset(provided), frozenset(absent))


def unknown_skill_pairs(
    draft: Draft, org: OrgSpec, world_start: date, frame: Frame
) -> frozenset[tuple[EmployeeId, SkillId]]:
    """The (person, skill) pairs the draft's derived unknowns rest on: every candidate the rules
    leave unknown on a skill question, paired with each skill the impact's requirements ask.

    Read off the planted draft before any modifier, as the other claims are; the sealed key
    derives its unknowns after the modifiers, so a pair reserved here for an unknown a
    modifier later turns into a known failure is a reservation with nothing to protect,
    never a missing one.
    """
    base = truth_fact_base(org, world_start, [draft.owned], draft.authored_facts)
    view = base.at(frame.today, RunCondition.all_reachable())
    universe = [employee.id for employee in org.employees]
    pairs: set[tuple[EmployeeId, SkillId]] = set()
    for expected in draft.impacts:
        skills = _required_skills(draft, expected.key.artifact)
        assessments = assess_impact(
            view, expected.key, universe, draft.constraints, frame.leave, frame.reference_timezone
        )
        for assessment in assessments:
            if any(u.predicate is PredicateName.HAS_SKILL for u in assessment.unresolved):
                pairs.update((assessment.employee_id, skill) for skill in skills)
    return frozenset(pairs)


def _required_skills(draft: Draft, artifact: EntityRef) -> tuple[SkillId, ...]:
    """The skills the draft's own clauses require of ``artifact``, or of a ticket's component."""
    targets = {artifact}
    for planted in draft.owned.work_items:
        if planted.entity.id == artifact.id:
            targets.add(component_ref(planted.entity.component_id))
    stated = {
        fact.subject: fact.value
        for fact in draft.authored_facts
        if fact.predicate is PredicateName.REQUIRES and isinstance(fact.value, Requirement)
    }
    skills: list[SkillId] = []
    for constraint in draft.constraints:
        if constraint.applies_to not in targets:
            continue
        requirement = stated.get(clause_ref(constraint.clause_id))
        if requirement is None:
            continue
        skills.extend(c.skill for c in requirement.criteria if isinstance(c, SkillCriterion))
    return tuple(skills)


class Reservations:
    """The world's reservation book: what earlier scenarios bound, and the two rules a later
    scenario's claims must not cross (the 15.4 ruling on the reservation book).

    Standing facts compose across scenarios. A note naming a person responsible is a
    document every run in the world reads, so a leave of that person in any other
    scenario acquires a responsibility impact its key never declared; a prose fact giving
    a person a skill is evidence every run reads, so a verdict elsewhere that assumes the
    person known to lack that skill moves. The whole-world re-verification refused twenty
    of twenty seeds of the first plan that seated the responsibility class beside other
    rows, on exactly those two interactions. The book is the constructive side: each
    admitted scenario's claims are recorded, and a later candidate whose claims cross an
    earlier one's is refused in both directions, so construction order never decides
    correctness. It encodes the interactions proven so far and nothing more: candidates
    shared between scenarios, the same person viable twice, are harmless and not
    reserved. The re-verification stays the oracle for any interaction the book does not
    know; a new one is evidence for a new rule, never for the oracle being wrong.
    """

    def __init__(self) -> None:
        self._leave_subjects: dict[EmployeeId, ScenarioId] = {}
        self._standing_contacts: dict[EmployeeId, ScenarioId] = {}
        self._skills_provided: dict[tuple[EmployeeId, SkillId], ScenarioId] = {}
        self._skills_required_absent: dict[tuple[EmployeeId, SkillId], ScenarioId] = {}

    def conflicts(self, claims: Claims) -> tuple[str, ...]:
        """Every rule ``claims`` would cross, each naming the scenario holding the reservation;
        empty when the book admits them."""
        found: list[str] = []
        holder = self._standing_contacts.get(claims.leave_subject)
        if holder is not None:
            found.append(f"leave subject {claims.leave_subject} is a standing contact of {holder}")
        for person in sorted(claims.standing_contacts):
            holder = self._leave_subjects.get(person)
            if holder is not None:
                found.append(f"standing contact {person} is a leave subject of {holder}")
        for person, skill in sorted(claims.skills_provided):
            holder = self._skills_required_absent.get((person, skill))
            if holder is not None:
                found.append(f"{skill} provided to {person} is assumed absent by {holder}")
        for person, skill in sorted(claims.skills_required_absent):
            holder = self._skills_provided.get((person, skill))
            if holder is not None:
                found.append(f"{skill} assumed absent of {person} is provided by {holder}")
        return tuple(found)

    def reserve(self, scenario_id: ScenarioId, claims: Claims) -> None:
        """Record ``claims`` as ``scenario_id``'s; the first holder of a term keeps its name."""
        self._leave_subjects.setdefault(claims.leave_subject, scenario_id)
        for person in claims.standing_contacts:
            self._standing_contacts.setdefault(person, scenario_id)
        for pair in claims.skills_provided:
            self._skills_provided.setdefault(pair, scenario_id)
        for pair in claims.skills_required_absent:
            self._skills_required_absent.setdefault(pair, scenario_id)


class ReservationExhausted(ConstructionError):
    """Every construction the organization affords crosses the world's reservation book: the
    class, how many candidates it had, and how many each rule refused, by name."""

    def __init__(
        self, scenario_id: ScenarioId, who: str, universe: int, eliminated: Mapping[str, int]
    ) -> None:
        rules = "; ".join(f"{count} by: {rule}" for rule, count in eliminated.items())
        super().__init__(
            f"{scenario_id}: {who} affords {universe} constructions and the reservation book "
            f"admits none — {rules}"
        )
        self.scenario_id = scenario_id
        self.who = who
        self.universe = universe
        self.eliminated = dict(eliminated)


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
    reservations: Reservations | None = None,
) -> Scenario:
    """One scenario of ``scenario_class`` with ``modifiers`` applied, verified against the rules.

    ``reservations`` is the world's book, shared by every scenario of a world the way
    ``ids`` is; a scenario constructed alone gets a fresh one, which admits everything.
    Raises ``MissingAffordance`` when the class or a modifier admits nothing,
    ``ReservationExhausted`` when every construction of the class crosses the book,
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
    book = Reservations() if reservations is None else reservations
    draft, claims = _admit(scenario_class, org, frame, rng, book)
    book.reserve(scenario_id, claims)
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
    leaver = _leaver_of(draft)
    problems = _verify(base, spec.today, impacts, draft.constraints, frame, org, leaver)
    expectations = derive_expectations(
        base.at(spec.today, RunCondition.all_reachable()),
        impacts,
        draft.constraints,
        leaver,
        frame.leave,
        reference_timezone,
        [employee.id for employee in org.employees],
    )
    problems.extend(_expectation_problems(expectations, draft))
    required = required_sources_for(
        base,
        spec.today,
        impacts,
        draft.constraints,
        frame.leave,
        reference_timezone,
        org,
        spec.leave_id,
        leaver,
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
        expected_conflicts=expectations.conflicts,
        expected_unknowns=expectations.unknowns,
    )
    briefs = _briefs_for(draft, impacts, base, spec.today, frame, org)
    scenario = Scenario(spec, key, draft.owned, draft.authored_facts, briefs)
    if problems:
        raise ScenarioInvariantFailed(scenario_id, problems)
    return scenario


def _briefs_for(
    draft: Draft,
    impacts: Sequence[ExpectedImpact],
    base: FactBase,
    today: date,
    frame: Frame,
    org: OrgSpec,
) -> tuple[Brief, ...]:
    """The scenario's briefs, completed from the class's pending prose, under the contract.

    A required fact's role is found by asking the rules with that one fact removed from
    the base: a conclusion that moves — an impact's grounding, a verdict, its reasons, an
    open question, an outcome, a planted conflict — makes the fact answer-changing,
    nothing moving makes it context. The same
    conclusions the required-sources derivation compares, so "answer-changing" means
    what "required" means there. The contract runs even with no pending prose, because
    it is also what refuses an authored fact evidenced by a part nobody planted.
    """
    normal = RunCondition.all_reachable()
    leaver = _leaver_of(draft)

    def concluded(facts: FactBase) -> tuple[object, ...]:
        return _conclusions(
            facts.at(today, normal),
            impacts,
            draft.constraints,
            draft.investigated,
            leaver,
            frame.leave,
            frame.reference_timezone,
            org,
        )

    baseline = concluded(base)
    roles: dict[Fact, FactRole] = {}
    for pending in draft.pending:
        for fact in pending.required:
            remaining = tuple(f for f in draft.authored_facts if f != fact)
            without = truth_fact_base(org, frame.world_start, [draft.owned], remaining)
            moved = concluded(without) != baseline
            roles[fact] = FactRole.ANSWER_CHANGING if moved else FactRole.CONTEXT
    work_items = [planted.entity for planted in draft.owned.work_items]
    documents = [planted.entity for planted in draft.owned.documents]
    events = [planted.entity for planted in draft.owned.events]
    lexicon = lexicon_of(org, work_items, documents, events)
    briefs = tuple(
        brief_for(pending, work_items, documents, lexicon, roles) for pending in draft.pending
    )
    check_pending(work_items, documents, briefs, draft.authored_facts)
    check_allowed(briefs, base)
    return briefs


def _admit(
    scenario_class: ScenarioClass, org: OrgSpec, frame: Frame, rng: Random, book: Reservations
) -> tuple[Draft, Claims]:
    """The first construction in the seed's order whose planted draft the book admits.

    Each candidate is chosen by the RNG among those left, planted, its claims read off the
    draft and checked; a refused candidate is unplanted by rewinding the id and title
    book and dropped from the choice. The first choice is the same draw the unfiltered
    selection makes, so a world the book never refuses anything in is the world it was
    before the book existed.
    """
    options = list(scenario_class.admissible(org))
    if not options:
        raise MissingAffordance(scenario_class.name.value, scenario_class.affordance)
    universe = len(options)
    eliminated: Counter[str] = Counter()
    while options:
        index = rng.randrange(len(options))
        checkpoint = frame.ids.checkpoint()
        draft = options[index](frame, rng)
        claims = claims_of(draft, org, unknown_skill_pairs(draft, org, frame.world_start, frame))
        crossed = book.conflicts(claims)
        if not crossed:
            return draft, claims
        frame.ids.rewind(checkpoint)
        eliminated.update(crossed)
        del options[index]
    raise ReservationExhausted(frame.scenario_id, scenario_class.name.value, universe, eliminated)


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
    leaver: EmployeeId,
) -> list[str]:
    """The rules' disagreements with the composed expectations under the normal run condition.

    Every expected impact must ground — the leaver holds it in the fact base — and the
    impacts the truth grounds for the leaver must be exactly the declared ones, so a
    distractor that lands inside the leave unannounced is a construction error (the step
    15 rulings). Verdicts are checked per authored candidate; the outcome is the truth
    outcome over the whole organization, never over ``must_assess`` alone (the
    contract's rule). A candidate authored from outside the organization is a problem
    too, named rather than a lookup failure.
    """
    problems: list[str] = []
    view = base.at(today, RunCondition.all_reachable())
    universe = [employee.id for employee in org.employees]
    problems.extend(_grounding_problems(view, impacts, frame, leaver))
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


def required_sources_for(
    base: FactBase,
    today: date,
    impacts: Sequence[ExpectedImpact],
    constraints: Sequence[ConstraintKey],
    leave_span: DateSpan,
    reference_timezone: str,
    org: OrgSpec,
    investigated: LeaveId,
    leaver: EmployeeId,
) -> set[Source]:
    """The sources the key's rule-level conclusions depend on, in ``base`` as of ``today``.

    Two kinds, and nothing else — a source hosting a named distractor is not one, since
    losing it changes no conclusion and distractor rejection is graded on its own list.
    The sources that establish what the run is about — the facts about each
    impact's artifact and the leave under investigation — read off the base. And the
    sources the rules depend on, found by asking, for each source in turn, whether the
    rules conclude anything different with that source unreachable: a grounding, a
    verdict, an outcome or a conflict that moves means the source was required.
    Provenance alone under-counts
    here, because a negative conclusion carries no evidence fact yet depends on every
    source of the predicate's declared domain — a candidate known not to hold a skill
    needs both the HR record and the tracker to have answered. Asking the rules under
    each outage captures that without the framework knowing what the rules read, and it
    is the tool-failure condition's own definition of dependence.

    One rule, two callers: construction asks it over the scenario's own facts, world
    assembly over the assembled world, so a foreign fact that changes dependence without
    moving a verdict is caught as contamination rather than left as a stale key.
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
    baseline = _conclusions(
        normal, impacts, constraints, investigated, leaver, leave_span, reference_timezone, org
    )
    for source in Source:
        outage = base.at(today, RunCondition.all_reachable().without(source))
        concluded = _conclusions(
            outage, impacts, constraints, investigated, leaver, leave_span, reference_timezone, org
        )
        if concluded != baseline:
            sources.add(source)
    return sources


def _leaver_of(draft: Draft) -> EmployeeId:
    for planted in draft.owned.leaves:
        if planted.entity.id == draft.investigated:
            return planted.entity.employee_id
    raise ValueError(f"the investigated leave {draft.investigated} is not one the draft owns")


def _grounding_problems(
    view: FactView, impacts: Sequence[ExpectedImpact], frame: Frame, leaver: EmployeeId
) -> list[str]:
    """Declared impacts the truth does not ground, and grounded impacts the key does not declare."""
    problems: list[str] = []
    for expected in impacts:
        grounding = ground_impact(
            view, expected.key, leaver, frame.leave, frame.reference_timezone
        )
        if not isinstance(grounding, Grounded):
            problems.append(
                f"{expected.key.artifact.id}: the declared {expected.key.subtype.value} impact "
                f"{grounding_text(grounding)}"
            )
    declared = {expected.key for expected in impacts}
    derived = derive_impacts(
        view, frame_leave_id(impacts), leaver, frame.leave, frame.reference_timezone
    )
    for key in derived.grounded:
        if key not in declared:
            problems.append(
                f"{key.artifact.id}: the truth grounds a {key.subtype.value} impact of the leaver "
                "that the key does not declare"
            )
    for key, open_question in derived.unresolved:
        problems.append(
            f"{key.artifact.id}: whether the leaver holds a {key.subtype.value} impact is "
            f"{grounding_text(open_question)}"
        )
    return problems


def frame_leave_id(impacts: Sequence[ExpectedImpact]) -> LeaveId:
    """The investigated leave every expected impact keys on; the draft refused a mix."""
    return impacts[0].key.leave_id


def grounding_text(grounding: Grounding) -> str:
    """A grounding that is not ``Grounded``, as a problem reads it."""
    match grounding:
        case Grounded():
            return "is grounded"
        case Unresolved(subject=subject, predicate=predicate, reason=reason):
            return f"unresolved: {reason.value} on {predicate.value} of {subject.id}"
        case _:
            return "is not the leaver's in the fact base"


@dataclass(frozen=True, slots=True)
class Expectations:
    """What the rules conclude of the third kind for one investigation: the conflicts on the
    facts it read and the unknowns its assessments seed, in the key's order."""

    conflicts: tuple[ExpectedConflict, ...]
    unknowns: tuple[ExpectedUnknown, ...]


@dataclass(frozen=True, slots=True)
class _Reading:
    grounding: Grounding
    assessments: tuple[Assessment, ...]


def _read(
    view: FactView,
    impacts: Sequence[ExpectedImpact],
    constraints: Sequence[ConstraintKey],
    leaver: EmployeeId,
    leave_span: DateSpan,
    reference_timezone: str,
    universe: Sequence[EmployeeId],
) -> tuple[_Reading, ...]:
    """Each impact's grounding and its assessments over ``universe``, the one pass every
    derivation below shares, so no consumer reads the rules a second way."""
    return tuple(
        _Reading(
            ground_impact(view, expected.key, leaver, leave_span, reference_timezone),
            assess_impact(
                view, expected.key, universe, constraints, leave_span, reference_timezone
            ),
        )
        for expected in impacts
    )


def _evidence(readings: Sequence[_Reading]) -> list[Fact]:
    facts: list[Fact] = []
    for reading in readings:
        if isinstance(reading.grounding, Grounded):
            facts.extend(reading.grounding.facts)
        facts.extend(fact for a in reading.assessments for fact in a.evidence)
    return facts


def derive_expectations(
    view: FactView,
    impacts: Sequence[ExpectedImpact],
    constraints: Sequence[ConstraintKey],
    leaver: EmployeeId,
    leave_span: DateSpan,
    reference_timezone: str,
    universe: Sequence[EmployeeId],
) -> Expectations:
    """The expected conflicts and unknowns of an investigation in ``view`` (the 15.5 rulings).

    Conflicts are the view's conflicts on a fact the groundings or the assessments returned
    as evidence, so a standing document another scenario planted is expected here only if
    this investigation read the fact it contradicts. Unknowns are the unresolved entries of
    every assessment over ``universe``, one per candidate, subject, fact and reason. Both in
    a stable order. Construction seals them into the key and world assembly re-derives them
    against every key, the same pass both times.
    """
    readings = _read(view, impacts, constraints, leaver, leave_span, reference_timezone, universe)
    conflicts = tuple(
        ExpectedConflict(
            finding.subject, finding.predicate, finding.resolution.value, finding.resolution.rule
        )
        for finding in conflicts_on(view, _evidence(readings))
    )
    unknowns = {
        ExpectedUnknown(a.employee_id, u.subject, u.predicate, u.reason)
        for reading in readings
        for a in reading.assessments
        for u in a.unresolved
    }
    return Expectations(
        conflicts,
        tuple(
            sorted(
                unknowns,
                key=lambda u: (
                    u.employee_id,
                    u.subject.kind,
                    u.subject.id,
                    u.required_fact,
                    u.reason,
                ),
            )
        ),
    )


def _expectation_problems(expectations: Expectations, draft: Draft) -> list[str]:
    """A required conflict or unknown the rules do not derive, and a derived conflict no class
    declared: conflicts are exact, unknowns a superset (the draft's docstring says why)."""
    problems: list[str] = []
    derived_conflicts = set(expectations.conflicts)
    for required in draft.required_conflicts:
        if required not in derived_conflicts:
            problems.append(
                f"the class requires a conflict on {required.predicate.value} of "
                f"{required.entity.id} that the rules do not derive"
            )
    for derived in expectations.conflicts:
        if derived not in set(draft.required_conflicts):
            problems.append(
                f"the rules derive a conflict on {derived.predicate.value} of {derived.entity.id} "
                "that the class does not declare"
            )
    derived_unknowns = set(expectations.unknowns)
    for required in draft.required_unknowns:
        if required not in derived_unknowns:
            problems.append(
                f"the class requires {required.employee_id} unknown on "
                f"{required.required_fact.value} ({required.reason.value}) and the rules do not "
                "derive it"
            )
    return problems


def _conclusions(
    view: FactView,
    impacts: Sequence[ExpectedImpact],
    constraints: Sequence[ConstraintKey],
    leave_id: LeaveId,
    leaver: EmployeeId,
    leave_span: DateSpan,
    reference_timezone: str,
    org: OrgSpec,
) -> tuple[object, ...]:
    """Everything the rules conclude in ``view``: each impact's grounding, verdicts, reasons,
    open questions and outcome; the impacts the leaver holds; the conflicts on the facts
    the investigation read.

    Grounding and conflicts joined the tuple at step 15: a fact whose only role is to make
    an impact exist, or to contradict the record, moves no verdict, and both the role
    derivation and the required-sources derivation would have called it context. The
    conflicts are scoped to the evidence the groundings and assessments returned (the 15.5
    rulings): a world's documents stand for every run, so an unscoped derivation would
    conclude another scenario's stale runbook here.
    """
    universe = [employee.id for employee in org.employees]
    concluded: list[object] = []
    readings = _read(view, impacts, constraints, leaver, leave_span, reference_timezone, universe)
    for expected, reading in zip(impacts, readings, strict=True):
        # The unresolved questions travel too: an unknown for absence and an unknown for
        # an unreachable source are different conclusions with one verdict, and the
        # source that separates them was required.
        verdicts = tuple(
            (a.employee_id, a.verdict, a.reasons, a.unresolved) for a in reading.assessments
        )
        required = required_count_for(
            view, expected.key, constraints, leave_span, reference_timezone
        )
        outcome = expected_action((a.verdict for a in reading.assessments), required)
        concluded.append((reading.grounding, verdicts, outcome))
    concluded.append(derive_impacts(view, leave_id, leaver, leave_span, reference_timezone))
    concluded.append(conflicts_on(view, _evidence(readings)))
    return tuple(concluded)


def _required(
    view: FactView, impact: ImpactKey, constraints: Sequence[ConstraintKey], frame: Frame
) -> int:
    return required_count_for(view, impact, constraints, frame.leave, frame.reference_timezone)


def required_count_for(
    view: FactView,
    impact: ImpactKey,
    constraints: Sequence[ConstraintKey],
    leave_span: DateSpan,
    reference_timezone: str,
) -> int:
    """How many viable candidates the outcome needs for ``impact`` in ``view``: one, or what the
    resolved requirements ask; an unreadable need counts as one, since no clause can apply."""
    need = need_of(view, impact, leave_span, reference_timezone)
    if isinstance(need, Unresolved):
        return 1
    resolved = [
        item
        for item in applicable_requirements(view, need, constraints)
        if isinstance(item, ResolvedRequirement)
    ]
    return required_count(resolved)
