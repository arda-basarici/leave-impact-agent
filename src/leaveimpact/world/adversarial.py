"""The adversarial tier's scenario classes: the correct output depends on reasoning about the
evidence itself.

Tier 3 tests whether an investigator resolves what the sources say against each other, and
concludes a limit where the world holds one (DESIGN, "The first golden set"; the class shapes
under the step 15 rulings, the 15.5 interview). ``stale_source_conflict`` is the first: the
tracker gives the leaver a release ticket due inside the leave, and a runbook section a model
writes names the leaver's teammate outside the component as the ticket's owner. The cast is
the structured deadline class's, unchanged: the same viable cover inside the component, the
same outsider authored non-viable by component. What the section adds is one fact of the
corpus contradicting the tracker on a single-valued predicate, so the rules derive a conflict
resolved to the system of record, the impact stays grounded on the tracker's owner, and the
key seals the conflict as expected (``ScenarioKey.expected_conflicts``). The failure the class
catches is an investigator who believes the document: one that drops the impact, or hands
cover to the named owner, whose component verdict the key already grades, without assessing
them. The outsider is the stale owner and not a component member on purpose, since a viable
stale owner would let a believing agent produce a correct-looking plan and leave the
conflict claim as the only separation.

The section carries the one required fact and nothing else the benchmark could read: the
contract already refuses a cross-source fact as context, and this class allows none, so the
section narrates the on-call routine and asserts one proposition. The required fact is
answer-changing through the conflict alone (the fact moves no verdict and no outcome), which
is what the key's expected conflicts made derivable; without them the ablation would have
called the section context, a construction error for a prose class. Required sources are the
record for the leave, the tracker for the impact and the corpus for the conflict, since the
conflict vanishes under a corpus outage and a tracker outage leaves ownership unknown with the
document not promoted (the authority ruling).

The runbook is titled by the release ticket it is about, a title the world's book mints once
per component, so two conflict rows in one component never share a runbook title and the
checker's entity list holds one document per name. The stale owner is a standing fact the
reservation book reserves (``Claims.standing_owners``): the interview read no rule was needed,
since the resolved owner is the leaver and the evidence scope keeps the conflict off other
rows' keys, and the golden sweep refused seventy-three of two hundred worlds on the path the
reading missed, a tracker outage during another leave of the named person, under which the
document's claim cannot be resolved away and that key's required sources move. The sweep is
the oracle for any interaction the book does not know, and a new one is a new rule (the 15.4
ruling's own sentence, applied).

``missing_information`` and ``uncovered`` are one shape a single placement apart. Both plant
the release ticket the leaver owns, due inside the leave, under a scenario-owned policy
clause requiring the skill nobody in the organization holds (the vocabulary sets one aside on
every seed), template-written, no prose. Every recorded employee then fails the skill
criterion; a blank-record employee is asked the skill and cannot answer, and the verdict rule
lets any known failure dominate that open question. The missing-information class puts the
release in the component holding exactly one blank-record member (an org guarantee, so the
unknown is one graded person and never a count the seed decides): that member passes the
component criterion, is available, and derives unknown with reason absent, since every
source in the skill predicate's domain answered and none holds the fact; the outcome is
unknown. The uncovered class puts the release in a component holding no blank-record
member: every member fails by skill, everyone outside by component, and two outsiders are
authored on purpose: the leaver's recorded teammate outside the component fails by component
and by skill, both criteria answered, while a blank-record employee outside fails by component
alone, since the known failure dominates the skill question their record cannot answer. That
one-reason difference is the dominance rule made visible, so the pair is a one-variable
experiment and not two rows that happen to end at different labels. The leaver is a recorded
member either way, since the leaver's own verdict is a known availability failure and a blank
leaver would leave no unknown. Both keys require the record, the tracker and the corpus: a
skill known false needs every source in the domain answered, and under a tracker or corpus
outage both become unknown by inaccessibility, the run-condition axis and not the key's. The
missing-information class asserts its one unknown (``Draft.required_unknowns``), and the sealed
key holds every unknown the rules derive, which here is exactly that one: the other blank
records fail by component.

``adversarial_composite`` is the two fixed together (DESIGN's sentence: resolve what obligation
exists, then conclude unknown rather than uncovered under incomplete candidate information):
the conflict class's runbook section naming the leaver's recorded teammate outside the
component as the ticket's owner, with the ticket seated in the missing-information component
under the unheld-skill clause. Authored: the stale outsider non-viable by component and by
skill, the blank-record member unknown by absence, a recorded member non-viable by skill, the
outcome unknown; the class asserts the conflict and the unknown, and construction verifies
every conclusion exactly, the conflict resolved to the tracker, the impact grounded, the
unresolved skill reason, the three verdicts and the outcome, so the composite is a conjunction
of the proven primitives and never a looser row that ends at the same label. The cast is
distinct and record-clean by construction, the outsider outside the component with a record,
the blank member inside, so each graded person carries one role and no two share it. The section is
the conflict class's section with a different ticket title, so the runbook register probe
covers it, one composite realization included as a no-interaction check with the clause-bearing
world. Modifiers are the parents' intersection, no concurrent leave; the claims are the
parents' union, the leave subject and the blank member's absence-dependent pair.
"""

from __future__ import annotations

from collections.abc import Mapping
from random import Random
from types import MappingProxyType

from leaveimpact.core.claims import (
    AssessmentReason,
    AuthorityRule,
    ConstraintKey,
    CoverageActionKind,
    ImpactKey,
    ImpactSubtype,
    UnknownReason,
    Verdict,
)
from leaveimpact.core.entities import Component, Document, DocumentSection, Employee
from leaveimpact.core.enums import DocumentKind, Source
from leaveimpact.core.facts import Fact
from leaveimpact.core.ids import ClauseId, EmployeeId, SkillId
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.refs import EvidenceRef, clause_ref, employee_ref, work_item_ref
from leaveimpact.core.values import Requirement, SkillCriterion
from leaveimpact.world.briefs import PendingProse, SectionTarget
from leaveimpact.world.construction import Construction, Draft, Frame, ScenarioClass
from leaveimpact.world.fragmented import RELEASE_POLICY_TITLE, SKILL_NAMES
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import (
    AuthoredVerdict,
    ExpectedConflict,
    ExpectedImpact,
    ExpectedUnknown,
    OwnedEntities,
    Planted,
    ScenarioClassName,
    Tier,
)
from leaveimpact.world.structured import (
    StructuredDeadline,
    deadline_impact,
    deadline_roles,
    plant_leave,
    plant_ticket,
)

RUNBOOK_TITLE = "Release runbook: {release}"
"""The stale runbook's title, scoped to the release ticket it names an owner for."""

RELEASE_SKILL_CLAUSE = "The {release} release needs an engineer with {skill} experience."
"""The pair's scenario-owned clause, template-written: one engineer with the unheld skill, so
every recorded employee fails it and only a blank record is left to ask."""


# --- stale_source_conflict ---------------------------------------------------------------


class StaleSourceConflict:
    """A runbook names a stale owner for the leaver's release ticket; the tracker is the record.

    The deadline cast (a component, its leaver, a viable cover inside it, a teammate outside
    it) plus one runbook section a model writes, stating that the outsider owns the ticket.
    Authored: the cover viable, the outsider non-viable by component, the outcome assign; the
    class asserts the one conflict its section plants, resolved to the leaver under the
    system-of-record rule, and construction refuses the scenario if the rules derive
    anything else. Admissible wherever the deadline class is, in the same canonical order.
    """

    name = ScenarioClassName.STALE_SOURCE_CONFLICT
    tier = Tier.ADVERSARIAL
    affordance = StructuredDeadline.affordance

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        # The deadline cast with every teammate outside the component as the stale owner in
        # turn, not the first alone: the owner is a reservation the book may refuse, and a
        # class offering one owner per leaver exhausted on a golden seed (the 15.5 sweep).
        return tuple(
            _conflict_construction(component, leaver, cover, outsider)
            for component, leaver, cover, outsider in deadline_roles(org, every_outsider=True)
        )


def _conflict_construction(
    component: Component, leaver: Employee, cover: Employee, outsider: Employee
) -> Construction:
    def plant(frame: Frame, rng: Random) -> Draft:
        visible = frame.window.start
        leave = plant_leave(frame, leaver)
        ticket = plant_ticket(frame, rng, component, leaver)
        section = frame.ids.clause()
        # The runbook's sections are empty here: the section is the model's, filled in at
        # materialization at the pending target's position (as the account note's is).
        runbook = Document(
            frame.ids.document(),
            RUNBOOK_TITLE.format(release=ticket.entity.title),
            DocumentKind.RUNBOOK,
            visible,
            (),
        )
        stale = Fact(
            work_item_ref(ticket.entity.id),
            PredicateName.OWNS_WORK_ITEM,
            employee_ref(outsider.id),
            EvidenceRef(Source.CORPUS, clause_ref(section)),
            visible,
        )
        owned = OwnedEntities(
            leaves=(leave,), work_items=(ticket,), documents=(Planted(runbook, visible),)
        )
        return Draft(
            owned,
            leave.entity.id,
            (deadline_impact(leave, ticket, cover, outsider),),
            authored_facts=(stale,),
            pending=(PendingProse(SectionTarget(section, runbook.id, 0), (stale,)),),
            required_conflicts=(
                ExpectedConflict(
                    work_item_ref(ticket.entity.id),
                    PredicateName.OWNS_WORK_ITEM,
                    employee_ref(leaver.id),
                    AuthorityRule.SYSTEM_OF_RECORD_WINS,
                ),
            ),
        )

    return plant


# --- missing_information and uncovered -----------------------------------------------------


class MissingInformation:
    """The release sits in the component holding exactly one blank-record member, under a clause
    requiring the unheld skill: that member is unknown by absence, the outcome unknown.

    Authored: the blank-record member unknown, one recorded member non-viable by skill; the
    class asserts the unknown and the key seals it as the only one, since every other blank
    record fails by component. Admissible for every recorded member of every such component
    as the leaver, in canonical order.
    """

    name = ScenarioClassName.MISSING_INFORMATION
    tier = Tier.ADVERSARIAL
    affordance = (
        "a component holding exactly one blank-record member and at least two recorded members"
    )

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        skill = unheld_skill(org)
        constructions: list[Construction] = []
        for component, members in _components_by_record(org):
            blank = [e for e in members if e.skills is None]
            recorded = [e for e in members if e.skills is not None]
            if len(blank) != 1 or len(recorded) < 2:
                continue
            for leaver in recorded:
                failing = next(e for e in recorded if e.id != leaver.id)
                constructions.append(
                    _missing_construction(component, leaver, failing, blank[0], skill)
                )
        return tuple(constructions)


class Uncovered:
    """The release sits in a component holding no blank-record member, under a clause requiring
    the unheld skill: everyone fails for a known reason, the outcome uncovered.

    Authored: one recorded member non-viable by skill, the leaver's recorded teammate outside
    the component non-viable by component and by skill, and a blank-record employee outside
    the component non-viable by component alone, the known failure dominating the open skill
    question. Admissible
    for every member of every such component whose team has a recorded member outside it.
    """

    name = ScenarioClassName.UNCOVERED
    tier = Tier.ADVERSARIAL
    affordance = (
        "a component with no blank-record member and two members, one with a recorded teammate "
        "outside the component, and a blank-record employee in the organization"
    )

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        skill = unheld_skill(org)
        blank_outsiders = [e for e in org.employees if e.skills is None]
        if not blank_outsiders:
            return ()
        constructions: list[Construction] = []
        for component, members in _components_by_record(org):
            if any(e.skills is None for e in members) or len(members) < 2:
                continue
            member_ids = {e.id for e in members}
            for leaver in members:
                failing = next(e for e in members if e.id != leaver.id)
                outsider = next(
                    (
                        e
                        for e in org.members_of(leaver.team_id)
                        if e.id not in member_ids and e.skills is not None
                    ),
                    None,
                )
                if outsider is None:
                    continue
                constructions.append(
                    _uncovered_construction(
                        component, leaver, failing, outsider, blank_outsiders[0], skill
                    )
                )
        return tuple(constructions)


def unheld_skill(org: OrgSpec) -> SkillId:
    """The skill no employee's record lists, which the organization sets aside on every seed."""
    for skill in org.skills:
        if not org.holders_of(skill):
            return skill
    raise ValueError("the organization holds every skill in its vocabulary; one is set aside")


def _components_by_record(org: OrgSpec) -> list[tuple[Component, list[Employee]]]:
    by_id = {employee.id: employee for employee in org.employees}
    return [
        (component, [by_id[member] for member in component.member_ids])
        for component in org.components
    ]


def _release_clause(
    frame: Frame, ticket_title: str, skill: SkillId
) -> tuple[Planted[Document], Fact, ClauseId]:
    """The pair's policy, its requirement fact and the clause id, scoped to the release by title."""
    visible = frame.window.start
    clause = frame.ids.clause()
    policy = Document(
        frame.ids.document(),
        RELEASE_POLICY_TITLE.format(release=ticket_title),
        DocumentKind.POLICY,
        visible,
        (
            DocumentSection(
                clause, RELEASE_SKILL_CLAUSE.format(release=ticket_title, skill=SKILL_NAMES[skill])
            ),
        ),
    )
    requires = Fact(
        clause_ref(clause),
        PredicateName.REQUIRES,
        Requirement(1, (SkillCriterion(skill),)),
        EvidenceRef(Source.CORPUS, clause_ref(clause)),
        visible,
    )
    return Planted(policy, visible), requires, clause


def _missing_construction(
    component: Component, leaver: Employee, failing: Employee, blank: Employee, skill: SkillId
) -> Construction:
    def plant(frame: Frame, rng: Random) -> Draft:
        leave = plant_leave(frame, leaver)
        ticket = plant_ticket(frame, rng, component, leaver)
        policy, requires, clause = _release_clause(frame, ticket.entity.title, skill)
        impact = ImpactKey(leave.entity.id, ImpactSubtype.DEADLINE, work_item_ref(ticket.entity.id))
        expected = ExpectedImpact(
            impact,
            CoverageActionKind.UNKNOWN,
            (
                AuthoredVerdict(blank.id, Verdict.UNKNOWN),
                AuthoredVerdict(failing.id, Verdict.NON_VIABLE, (AssessmentReason.SKILL,)),
            ),
        )
        return Draft(
            OwnedEntities(leaves=(leave,), work_items=(ticket,), documents=(policy,)),
            leave.entity.id,
            (expected,),
            constraints=(ConstraintKey(clause, work_item_ref(ticket.entity.id)),),
            authored_facts=(requires,),
            required_unknowns=(
                ExpectedUnknown(
                    blank.id, employee_ref(blank.id), PredicateName.HAS_SKILL, UnknownReason.ABSENT
                ),
            ),
        )

    return plant


def _uncovered_construction(
    component: Component,
    leaver: Employee,
    failing: Employee,
    outsider: Employee,
    blank_outsider: Employee,
    skill: SkillId,
) -> Construction:
    def plant(frame: Frame, rng: Random) -> Draft:
        leave = plant_leave(frame, leaver)
        ticket = plant_ticket(frame, rng, component, leaver)
        policy, requires, clause = _release_clause(frame, ticket.entity.title, skill)
        impact = ImpactKey(leave.entity.id, ImpactSubtype.DEADLINE, work_item_ref(ticket.entity.id))
        expected = ExpectedImpact(
            impact,
            CoverageActionKind.UNCOVERED,
            (
                AuthoredVerdict(failing.id, Verdict.NON_VIABLE, (AssessmentReason.SKILL,)),
                AuthoredVerdict(
                    outsider.id,
                    Verdict.NON_VIABLE,
                    (AssessmentReason.COMPONENT, AssessmentReason.SKILL),
                ),
                AuthoredVerdict(
                    blank_outsider.id, Verdict.NON_VIABLE, (AssessmentReason.COMPONENT,)
                ),
            ),
        )
        return Draft(
            OwnedEntities(leaves=(leave,), work_items=(ticket,), documents=(policy,)),
            leave.entity.id,
            (expected,),
            constraints=(ConstraintKey(clause, work_item_ref(ticket.entity.id)),),
            authored_facts=(requires,),
        )

    return plant


# --- adversarial_composite ----------------------------------------------------------------


class AdversarialComposite:
    """The stale conflict on the impact with the missing-information candidates around it.

    The release in the component holding exactly one blank-record member, under the clause
    requiring the unheld skill, with a runbook section naming the leaver's recorded teammate
    outside the component as the ticket's owner. Authored: the outsider non-viable by
    component and skill, the blank member unknown, a recorded member non-viable by skill, the
    outcome unknown; asserted: the one conflict and the one unknown. Admissible for every
    recorded member of every such component whose team has a recorded member outside it.
    """

    name = ScenarioClassName.ADVERSARIAL_COMPOSITE
    tier = Tier.ADVERSARIAL
    affordance = (
        "a component holding exactly one blank-record member and a recorded member with a "
        "recorded teammate outside the component"
    )

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        skill = unheld_skill(org)
        constructions: list[Construction] = []
        for component, members in _components_by_record(org):
            blank = [e for e in members if e.skills is None]
            recorded = [e for e in members if e.skills is not None]
            if len(blank) != 1 or len(recorded) < 2:
                continue
            member_ids = {e.id for e in members}
            for leaver in recorded:
                failing = next(e for e in recorded if e.id != leaver.id)
                # Every recorded teammate outside as the stale owner in turn (see the conflict
                # class): the owner is what the reservation book may refuse.
                for outsider in _recorded_teammates_outside(org, leaver, member_ids):
                    constructions.append(
                        _composite_construction(
                            component, leaver, failing, outsider, blank[0], skill
                        )
                    )
        return tuple(constructions)


def _recorded_teammates_outside(
    org: OrgSpec, leaver: Employee, member_ids: set[EmployeeId]
) -> tuple[Employee, ...]:
    return tuple(
        e for e in org.members_of(leaver.team_id) if e.id not in member_ids and e.skills is not None
    )


def _composite_construction(
    component: Component,
    leaver: Employee,
    failing: Employee,
    outsider: Employee,
    blank: Employee,
    skill: SkillId,
) -> Construction:
    def plant(frame: Frame, rng: Random) -> Draft:
        visible = frame.window.start
        leave = plant_leave(frame, leaver)
        ticket = plant_ticket(frame, rng, component, leaver)
        policy, requires, clause = _release_clause(frame, ticket.entity.title, skill)
        section = frame.ids.clause()
        runbook = Document(
            frame.ids.document(),
            RUNBOOK_TITLE.format(release=ticket.entity.title),
            DocumentKind.RUNBOOK,
            visible,
            (),
        )
        stale = Fact(
            work_item_ref(ticket.entity.id),
            PredicateName.OWNS_WORK_ITEM,
            employee_ref(outsider.id),
            EvidenceRef(Source.CORPUS, clause_ref(section)),
            visible,
        )
        impact = ImpactKey(leave.entity.id, ImpactSubtype.DEADLINE, work_item_ref(ticket.entity.id))
        expected = ExpectedImpact(
            impact,
            CoverageActionKind.UNKNOWN,
            (
                AuthoredVerdict(
                    outsider.id,
                    Verdict.NON_VIABLE,
                    (AssessmentReason.COMPONENT, AssessmentReason.SKILL),
                ),
                AuthoredVerdict(blank.id, Verdict.UNKNOWN),
                AuthoredVerdict(failing.id, Verdict.NON_VIABLE, (AssessmentReason.SKILL,)),
            ),
        )
        owned = OwnedEntities(
            leaves=(leave,),
            work_items=(ticket,),
            documents=(policy, Planted(runbook, visible)),
        )
        return Draft(
            owned,
            leave.entity.id,
            (expected,),
            constraints=(ConstraintKey(clause, work_item_ref(ticket.entity.id)),),
            authored_facts=(requires, stale),
            pending=(PendingProse(SectionTarget(section, runbook.id, 0), (stale,)),),
            required_conflicts=(
                ExpectedConflict(
                    work_item_ref(ticket.entity.id),
                    PredicateName.OWNS_WORK_ITEM,
                    employee_ref(leaver.id),
                    AuthorityRule.SYSTEM_OF_RECORD_WINS,
                ),
            ),
            required_unknowns=(
                ExpectedUnknown(
                    blank.id, employee_ref(blank.id), PredicateName.HAS_SKILL, UnknownReason.ABSENT
                ),
            ),
        )

    return plant


ADVERSARIAL_CLASSES: Mapping[ScenarioClassName, ScenarioClass] = MappingProxyType(
    {
        ScenarioClassName.STALE_SOURCE_CONFLICT: StaleSourceConflict(),
        ScenarioClassName.MISSING_INFORMATION: MissingInformation(),
        ScenarioClassName.UNCOVERED: Uncovered(),
        ScenarioClassName.ADVERSARIAL_COMPOSITE: AdversarialComposite(),
    }
)
"""The adversarial classes built so far, by name; ``classes.SCENARIO_CLASSES`` joins every tier."""


__all__ = [
    "ADVERSARIAL_CLASSES",
    "RELEASE_SKILL_CLAUSE",
    "RUNBOOK_TITLE",
    "AdversarialComposite",
    "MissingInformation",
    "StaleSourceConflict",
    "Uncovered",
    "unheld_skill",
]
