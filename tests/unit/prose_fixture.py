"""A scenario class that leaves a comment for a model — the fragmented tier's shape, shared by the
brief, construction and composition tests.

A meeting falls inside the leave under a policy clause requiring a Kafka engineer; the clause
is written by the class itself (a template-carried fact). The candidate's skills record lacks
Kafka, and the fact that makes the candidate viable — Kafka evidenced in a ticket comment —
is left pending for a model to write. ``context`` adds a second required fact on the same
comment the answer does not depend on; ``orphan`` evidences the Kafka fact by a comment
nobody planted or briefed, which the pre-compose contract must refuse.
"""

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from random import Random
from zoneinfo import ZoneInfo

from leaveimpact.core import (
    CalendarEvent,
    ConstraintKey,
    CoverageActionKind,
    DateSpan,
    Document,
    DocumentKind,
    DocumentSection,
    EvidenceRef,
    Fact,
    ImpactKey,
    ImpactSubtype,
    Leave,
    LeaveKind,
    LeaveStatus,
    PredicateName,
    Requirement,
    SkillCriterion,
    Source,
    Verdict,
    WorkItem,
    WorkItemStatus,
    clause_ref,
    comment_ref,
    employee_ref,
    event_ref,
    work_item_ref,
)
from leaveimpact.core.ids import ComponentId, EmployeeId, comment_id, scenario_id, skill_id
from leaveimpact.world import (
    DEFAULT_PARAMS,
    GENERATOR_VERSION,
    AuthoredVerdict,
    CommentTarget,
    Construction,
    Draft,
    ExpectedImpact,
    Frame,
    MaterializationRecord,
    Minting,
    ModelConfiguration,
    OrgSpec,
    OwnedEntities,
    PendingProse,
    PlanRow,
    Planted,
    Scenario,
    ScenarioClassName,
    SectionTarget,
    SemanticWorld,
    Setting,
    TargetRecord,
    Tier,
    construct,
    generate_org,
    vocabulary_digest,
    world_fact_base,
)

ORG = generate_org(7, DEFAULT_PARAMS)
WORLD_START = date(2026, 1, 1)
WINDOW = DateSpan(date(2026, 3, 1), date(2026, 3, 14))
TZ = "Europe/Istanbul"
KAFKA = skill_id("kafka")
PYTHON = skill_id("python")


@dataclass(frozen=True)
class SkillInComment:
    context: bool = False
    orphan: bool = False
    name = ScenarioClassName.FREE_TEXT_QUALIFICATION
    tier = Tier.FRAGMENTED
    affordance = "a Kafka holder, plus a leaver and a candidate whose skills records lack it"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        holders = {e.id for e in org.holders_of(KAFKA)}
        others = [e for e in org.employees if e.skills is not None and e.id not in holders]
        if not holders or len(others) < 2:
            return ()
        leaver, candidate = others[0], others[1]

        def plant(frame: Frame, rng: Random) -> Draft:
            visible = frame.window.start
            leave = Leave(
                frame.ids.leave(),
                leaver.id,
                frame.leave.start,
                frame.leave.end,
                LeaveKind.ANNUAL,
                LeaveStatus.APPROVED,
            )
            zone = ZoneInfo(frame.reference_timezone)
            start = datetime.combine(frame.leave.start, time(10, 0), tzinfo=zone)
            event = CalendarEvent(
                frame.ids.event(), "Kafka release", start, start + timedelta(hours=1), (leaver.id,)
            )
            clause = frame.ids.clause()
            policy = Document(
                frame.ids.document(),
                "Release policy",
                DocumentKind.POLICY,
                visible,
                (DocumentSection(clause, "A release needs a Kafka engineer."),),
            )
            requires = Fact(
                clause_ref(clause),
                PredicateName.REQUIRES,
                Requirement(1, (SkillCriterion(KAFKA),)),
                EvidenceRef(Source.CORPUS, clause_ref(clause)),
                visible,
            )
            ticket = WorkItem(
                frame.ids.work_item(),
                "Event Ingestion: migrate the retry queue",
                candidate.id,
                WorkItemStatus.IN_PROGRESS,
                org.components[0].id,
                visible,
                None,
                None,
                (),
            )
            comment = frame.ids.comment()
            evidenced = comment_ref(comment_id(999) if self.orphan else comment)
            evidence = EvidenceRef(Source.JIRA, evidenced)
            who = employee_ref(candidate.id)
            carried = [Fact(who, PredicateName.HAS_SKILL, KAFKA, evidence, visible)]
            if self.context:
                carried.append(Fact(who, PredicateName.HAS_SKILL, PYTHON, evidence, visible))
            target = CommentTarget(comment, ticket.id, 0, visible, candidate.id)
            pending = () if self.orphan else (PendingProse(target, tuple(carried)),)
            impact = ImpactKey(leave.id, ImpactSubtype.MEETING, event_ref(event.id))
            owned = OwnedEntities(
                leaves=(Planted(leave, visible),),
                work_items=(Planted(ticket, visible),),
                events=(Planted(event, visible),),
                documents=(Planted(policy, visible),),
            )
            expected = ExpectedImpact(
                impact, CoverageActionKind.ASSIGN, (AuthoredVerdict(candidate.id, Verdict.VIABLE),)
            )
            return Draft(
                owned,
                leave.id,
                (expected,),
                constraints=(ConstraintKey(clause, event_ref(event.id)),),
                authored_facts=(requires, *carried),
                pending=pending,
            )

        return (plant,)




@dataclass(frozen=True)
class ContactInNote:
    """The responsibility class's shape: a client note's model-written section names the leaver
    as a client's contact, the section itself is the impact's artifact, and with no clause
    applying to it every other employee could cover it. The one prose fact is the impact's
    ground, which only the grounding conclusion can see."""

    name = ScenarioClassName.FREE_TEXT_RESPONSIBILITY
    tier = Tier.FRAGMENTED
    affordance = "two employees"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        if len(org.employees) < 2:
            return ()
        leaver, candidate = org.employees[0], org.employees[1]

        def plant(frame: Frame, rng: Random) -> Draft:
            visible = frame.window.start
            leave = Leave(
                frame.ids.leave(),
                leaver.id,
                frame.leave.start,
                frame.leave.end,
                LeaveKind.ANNUAL,
                LeaveStatus.APPROVED,
            )
            clause = frame.ids.clause()
            note = Document(
                frame.ids.document(), "Acme account notes", DocumentKind.CLIENT_NOTE, visible, ()
            )
            names = Fact(
                clause_ref(clause),
                PredicateName.NAMES_RESPONSIBLE,
                employee_ref(leaver.id),
                EvidenceRef(Source.CORPUS, clause_ref(clause)),
                visible,
            )
            impact = ImpactKey(leave.id, ImpactSubtype.RESPONSIBILITY, clause_ref(clause))
            owned = OwnedEntities(
                leaves=(Planted(leave, visible),), documents=(Planted(note, visible),)
            )
            expected = ExpectedImpact(
                impact, CoverageActionKind.ASSIGN, (AuthoredVerdict(candidate.id, Verdict.VIABLE),)
            )
            return Draft(
                owned,
                leave.id,
                (expected,),
                authored_facts=(names,),
                pending=(PendingProse(SectionTarget(clause, note.id, 0), (names,)),),
            )

        return (plant,)


@dataclass(frozen=True)
class StaleOwnerInRunbook:
    """The conflict class's shape: the tracker gives the leaver a ticket due inside the leave, and a
    runbook's model-written section names the previous owner. The prose fact moves no verdict
    and no outcome; only the conflict conclusion sees it."""

    name = ScenarioClassName.STALE_SOURCE_CONFLICT
    tier = Tier.ADVERSARIAL
    affordance = "a component with three members"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        for component in org.components:
            if len(component.member_ids) < 3:
                continue
            leaver, candidate, previous = component.member_ids[:3]

            def plant(
                frame: Frame,
                rng: Random,
                component_id: ComponentId = component.id,
                leaver: EmployeeId = leaver,
                candidate: EmployeeId = candidate,
                previous: EmployeeId = previous,
            ) -> Draft:
                visible = frame.window.start
                leave = Leave(
                    frame.ids.leave(),
                    leaver,
                    frame.leave.start,
                    frame.leave.end,
                    LeaveKind.ANNUAL,
                    LeaveStatus.APPROVED,
                )
                ticket = WorkItem(
                    id=frame.ids.work_item(),
                    title="Ledger migration",
                    owner_id=leaver,
                    status=WorkItemStatus.IN_PROGRESS,
                    component_id=component_id,
                    opened_on=visible,
                    resolved_on=None,
                    due_on=frame.leave.start + timedelta(days=1),
                    comments=(),
                )
                clause = frame.ids.clause()
                runbook = Document(
                    frame.ids.document(),
                    "Ledger migration runbook",
                    DocumentKind.RUNBOOK,
                    visible,
                    (),
                )
                stale = Fact(
                    work_item_ref(ticket.id),
                    PredicateName.OWNS_WORK_ITEM,
                    employee_ref(previous),
                    EvidenceRef(Source.CORPUS, clause_ref(clause)),
                    visible,
                )
                impact = ImpactKey(leave.id, ImpactSubtype.DEADLINE, work_item_ref(ticket.id))
                owned = OwnedEntities(
                    leaves=(Planted(leave, visible),),
                    work_items=(Planted(ticket, visible),),
                    documents=(Planted(runbook, visible),),
                )
                expected = ExpectedImpact(
                    impact, CoverageActionKind.ASSIGN, (AuthoredVerdict(candidate, Verdict.VIABLE),)
                )
                return Draft(
                    owned,
                    leave.id,
                    (expected,),
                    authored_facts=(stale,),
                    pending=(PendingProse(SectionTarget(clause, runbook.id, 0), (stale,)),),
                )

            return (plant,)
        return ()


def pending_scenario(
    scenario_class: SkillInComment | ContactInNote | StaleOwnerInRunbook | None = None,
) -> Scenario:
    """One scenario of ``scenario_class`` under the shared organization, deterministic."""
    return construct(
        scenario_class or SkillInComment(),
        [],
        ORG,
        scenario_id=scenario_id(1),
        window=WINDOW,
        world_start=WORLD_START,
        reference_timezone=TZ,
        ids=Minting(),
        rng=Random(1),
    )


def semantic_world_of(scenario: Scenario) -> SemanticWorld:
    """A one-scenario semantic world around ``scenario``, plan and facts consistent with it."""
    key = scenario.key
    return SemanticWorld(
        seed=7,
        world_start=WORLD_START,
        org=ORG,
        slices=(scenario.spec.window,),
        plan=(PlanRow(key.scenario_id, key.tier, key.scenario_class, key.modifiers),),
        scenarios=(scenario,),
        facts=world_fact_base(ORG, WORLD_START, [scenario]),
        generator_version=GENERATOR_VERSION,
        interpreter=(3, 13),
        vocabulary_digest=vocabulary_digest(),
    )


def digest_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_for(
    bodies: Mapping[str, str], extra_targets: Iterable[str] = ()
) -> MaterializationRecord:
    """A record accepting ``bodies`` on the first attempt, plus any extra targets named."""
    writer = ModelConfiguration("writer-model", (Setting("temperature", 0.7),))
    checker = ModelConfiguration("checker-model", (Setting("temperature", 0),))
    targets = [
        TargetRecord(target, 1, (), digest_of(f"request:{target}"), digest_of(body), ())
        for target, body in bodies.items()
    ]
    targets.extend(
        TargetRecord(target, 1, (), digest_of(f"request:{target}"), digest_of(target), ())
        for target in extra_targets
    )
    return MaterializationRecord(
        writer, checker, (("writer-system", digest_of("writer")),), 4, tuple(targets)
    )
