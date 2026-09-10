"""The construction framework, exercised with minimal test doubles: a class that plants one ticket
due inside the leave and authors one candidate, and modifiers that plant a concurrent leave or a
resolved distractor. The doubles are framework probes, not scenario classes — each test asserts
one framework behaviour: selection among admissible constructions, composition of declared
effects, the two invariants, the named errors, and determinism over the whole result."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from random import Random
from zoneinfo import ZoneInfo

import pytest

from leaveimpact.core import (
    AssessmentReason,
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
    event_ref,
    work_item_ref,
)
from leaveimpact.core.ids import ComponentId, EmployeeId, employee_id, scenario_id, skill_id
from leaveimpact.world import (
    DEFAULT_PARAMS,
    AuthoredVerdict,
    DistractorReason,
    ExpectedImpact,
    ModifierEffect,
    ModifierName,
    NamedDistractor,
    OrgSpec,
    OwnedEntities,
    Planted,
    ScenarioClassName,
    Tier,
    VerdictOverride,
    generate_org,
)
from leaveimpact.world.construction import (
    Amendment,
    ConflictingEffects,
    Construction,
    Draft,
    Frame,
    Minting,
    MissingAffordance,
    Modifier,
    ScenarioClass,
    ScenarioInvariantFailed,
    construct,
)

ORG = generate_org(7, DEFAULT_PARAMS)
WORLD_START = date(2026, 1, 1)
WINDOW = DateSpan(date(2026, 3, 1), date(2026, 3, 14))
TZ = "Europe/Istanbul"


@dataclass(frozen=True)
class OneTicket:
    """A leaver in a component owns a ticket due inside the leave; a fellow member is the candidate.

    ``lie`` authors the candidate the wrong way round; ``wrong_outcome`` declares uncovered
    where the org has cover. Both exist so the invariants have something to catch.
    """

    lie: bool = False
    wrong_outcome: bool = False
    ghost: bool = False
    name = ScenarioClassName.STRUCTURED_DEADLINE
    tier = Tier.STRUCTURED
    affordance = "a component with at least three members"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        constructions: list[Construction] = []
        for component in org.components:
            if len(component.member_ids) < 3:
                continue
            leaver, candidate = component.member_ids[0], component.member_ids[1]
            if self.ghost:
                candidate = employee_id(999)

            def plant(
                frame: Frame,
                rng: Random,
                component_id: ComponentId = component.id,
                leaver: EmployeeId = leaver,
                candidate: EmployeeId = candidate,
            ) -> Draft:
                leave = Leave(
                    frame.ids.leave(), leaver, frame.leave.start, frame.leave.end,
                    LeaveKind.ANNUAL, LeaveStatus.APPROVED,
                )
                ticket = WorkItem(
                    id=frame.ids.work_item(),
                    title="Kafka upgrade",
                    owner_id=leaver,
                    status=WorkItemStatus.IN_PROGRESS,
                    component_id=component_id,
                    opened_on=frame.window.start,
                    resolved_on=None,
                    due_on=frame.leave.start + timedelta(days=1),
                    comments=(),
                )
                verdict = (
                    AuthoredVerdict(candidate, Verdict.NON_VIABLE, (AssessmentReason.COMPONENT,))
                    if self.lie
                    else AuthoredVerdict(candidate, Verdict.VIABLE)
                )
                outcome = CoverageActionKind.ASSIGN
                if self.wrong_outcome:
                    outcome = CoverageActionKind.UNCOVERED
                impact = ImpactKey(leave.id, ImpactSubtype.DEADLINE, work_item_ref(ticket.id))
                owned = OwnedEntities(
                    leaves=(Planted(leave, frame.window.start),),
                    work_items=(Planted(ticket, frame.window.start),),
                )
                return Draft(owned, leave.id, (ExpectedImpact(impact, outcome, (verdict,)),))

            constructions.append(plant)
        return tuple(constructions)


@dataclass(frozen=True)
class MeetingWithClause:
    """A release meeting during the leave under a clause that needs Kafka; the candidate lacks it.

    The negative skill verdict needs both the HR record and the tracker to have answered,
    and no tracker fact is about the meeting — so the tracker is required only through
    the negative, which is what the required-sources derivation must catch.
    """

    blank_candidate: bool = False
    name = ScenarioClassName.STRUCTURED_MEETING
    tier = Tier.FRAGMENTED
    affordance = "a Kafka holder, plus a leaver and a candidate with skills records lacking it"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        kafka = skill_id("kafka")
        holders = {e.id for e in org.holders_of(kafka)}
        others = [e.id for e in org.employees if e.skills is not None and e.id not in holders]
        blank = [e.id for e in org.employees if e.skills is None]
        if not holders or len(others) < 2 or not blank:
            return ()
        leaver, candidate = others[0], others[1]
        if self.blank_candidate:
            candidate = blank[0]

        def plant(frame: Frame, rng: Random) -> Draft:
            visible = frame.window.start
            leave = Leave(
                frame.ids.leave(), leaver, frame.leave.start, frame.leave.end,
                LeaveKind.ANNUAL, LeaveStatus.APPROVED,
            )
            zone = ZoneInfo(frame.reference_timezone)
            start = datetime.combine(frame.leave.start, time(10, 0), tzinfo=zone)
            event = CalendarEvent(
                frame.ids.event(), "Kafka release", start, start + timedelta(hours=1), (leaver,)
            )
            clause = frame.ids.clause()
            policy = Document(
                frame.ids.document(), "Release policy", DocumentKind.POLICY, visible,
                (DocumentSection(clause, "A release needs a Kafka engineer."),),
            )
            requires = Fact(
                clause_ref(clause), PredicateName.REQUIRES,
                Requirement(1, (SkillCriterion(kafka),)),
                EvidenceRef(Source.CORPUS, clause_ref(clause)), visible,
            )
            impact = ImpactKey(leave.id, ImpactSubtype.MEETING, event_ref(event.id))
            owned = OwnedEntities(
                leaves=(Planted(leave, visible),),
                events=(Planted(event, visible),),
                documents=(Planted(policy, visible),),
            )
            lacking = (
                AuthoredVerdict(candidate, Verdict.UNKNOWN)
                if self.blank_candidate
                else AuthoredVerdict(candidate, Verdict.NON_VIABLE, (AssessmentReason.SKILL,))
            )
            expected = ExpectedImpact(impact, CoverageActionKind.ASSIGN, (lacking,))
            return Draft(
                owned, leave.id, (expected,),
                constraints=(ConstraintKey(clause, event_ref(event.id)),),
                authored_facts=(requires,),
            )

        return (plant,)


@dataclass(frozen=True)
class Nothing:
    name = ScenarioClassName.UNCOVERED
    tier = Tier.ADVERSARIAL
    affordance = "a skill nobody holds and a ticket that needs it"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        return ()


@dataclass(frozen=True)
class ConcurrentLeave:
    """Any authored candidate can be sent on leave over the same days; declares the verdict flip."""

    name = ModifierName.CONCURRENT_LEAVE
    affordance = "an authored candidate to send on leave"

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]:
        amendments: list[Amendment] = []
        for expected in draft.impacts:
            for authored in expected.must_assess:

                def amend(
                    draft: Draft,
                    frame: Frame,
                    rng: Random,
                    impact: ImpactKey = expected.key,
                    who: EmployeeId = authored.employee_id,
                ) -> tuple[Draft, ModifierEffect]:
                    leave = Leave(
                        frame.ids.leave(), who, frame.leave.start, frame.leave.end,
                        LeaveKind.SICK, LeaveStatus.APPROVED,
                    )
                    planted = OwnedEntities(leaves=(Planted(leave, frame.window.start),))
                    away = (AssessmentReason.AVAILABILITY,)
                    flipped = AuthoredVerdict(who, Verdict.NON_VIABLE, away)
                    effect = ModifierEffect(verdict_overrides=(VerdictOverride(impact, flipped),))
                    return draft.extended(owned=planted), effect

                amendments.append(amend)
        return tuple(amendments)


@dataclass(frozen=True)
class ResolvedDistractor:
    """The leaver also owns a ticket resolved before the leave, named as a near-miss."""

    name = ModifierName.ALREADY_RESOLVED
    affordance = "an owned open ticket to shadow"

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]:
        def amend(draft: Draft, frame: Frame, rng: Random) -> tuple[Draft, ModifierEffect]:
            open_ticket = draft.owned.work_items[0].entity
            done = WorkItem(
                id=frame.ids.work_item(),
                title="Kafka upgrade, phase one",
                owner_id=open_ticket.owner_id,
                status=WorkItemStatus.DONE,
                component_id=open_ticket.component_id,
                opened_on=frame.window.start,
                resolved_on=frame.window.start + timedelta(days=1),
                due_on=frame.leave.start,
                comments=(),
            )
            planted = OwnedEntities(work_items=(Planted(done, frame.window.start),))
            near_miss = NamedDistractor(work_item_ref(done.id), DistractorReason.ALREADY_RESOLVED)
            return draft.extended(owned=planted), ModifierEffect(distractors=(near_miss,))

        return (amend,) if draft.owned.work_items else ()


ONE_TICKET = OneTicket()


def _construct(
    scenario_class: ScenarioClass = ONE_TICKET, modifiers: Sequence[Modifier] = (), seed: int = 1
):
    return construct(
        scenario_class,
        modifiers,
        ORG,
        scenario_id=scenario_id(1),
        window=WINDOW,
        world_start=WORLD_START,
        reference_timezone=TZ,
        ids=Minting(),
        rng=Random(seed),
    )


def test_a_class_selects_plants_and_the_rules_agree_with_what_it_authored() -> None:
    scenario = _construct()
    (expected,) = scenario.key.impacts
    assert expected.outcome is CoverageActionKind.ASSIGN
    (authored,) = expected.must_assess
    assert authored.verdict is Verdict.VIABLE
    assert scenario.key.stable_interval.contains(scenario.spec.today)
    assert {Source.FRAPPE, Source.JIRA} <= set(scenario.key.required_sources)
    assert scenario.spec.leave_id == scenario.owned.leaves[0].entity.id


def test_the_same_inputs_give_an_equal_scenario() -> None:
    assert _construct(seed=5) == _construct(seed=5)
    assert _construct(seed=5) != _construct(seed=6)


def test_an_authored_verdict_the_rule_disagrees_with_fails_construction_by_name() -> None:
    with pytest.raises(ScenarioInvariantFailed, match="authored non_viable.*the rule says viable"):
        _construct(OneTicket(lie=True))


def test_a_declared_outcome_the_truth_disagrees_with_fails_construction_by_name() -> None:
    with pytest.raises(ScenarioInvariantFailed, match="declared uncovered, the truth outcome is"):
        _construct(OneTicket(wrong_outcome=True))


def test_an_org_without_the_affordance_fails_before_anything_is_planted() -> None:
    with pytest.raises(MissingAffordance, match="uncovered found no admissible construction"):
        _construct(Nothing())


def test_a_modifier_amends_a_verdict_declaratively_and_the_rules_confirm_the_amendment() -> None:
    scenario = _construct(modifiers=(ConcurrentLeave(),))
    (expected,) = scenario.key.impacts
    (authored,) = expected.must_assess
    assert authored.verdict is Verdict.NON_VIABLE
    assert authored.reasons == (AssessmentReason.AVAILABILITY,)
    assert expected.outcome is CoverageActionKind.ASSIGN, "the class outcome survives the modifier"
    assert scenario.key.modifiers == (ModifierName.CONCURRENT_LEAVE,)
    assert len(scenario.owned.leaves) == 2


def test_a_modifier_adds_a_named_distractor_to_the_key() -> None:
    scenario = _construct(modifiers=(ResolvedDistractor(),))
    (distractor,) = scenario.key.distractors
    assert distractor.reason is DistractorReason.ALREADY_RESOLVED
    assert distractor.entity != scenario.key.impacts[0].key.artifact
    assert len(scenario.owned.work_items) == 2


def test_two_effects_on_one_candidate_collide() -> None:
    with pytest.raises(ConflictingEffects, match="two effects amend"):
        _construct(modifiers=(ConcurrentLeave(), ConcurrentLeave()))


def test_a_modifier_without_its_structure_finds_no_amendment() -> None:
    @dataclass(frozen=True)
    class NoTickets:
        name = ScenarioClassName.STRUCTURED_MEETING
        tier = Tier.STRUCTURED
        affordance = "anything"

        def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
            inner = OneTicket().admissible(org)

            def strip(frame: Frame, rng: Random) -> Draft:
                draft = inner[0](frame, rng)
                return Draft(
                    OwnedEntities(leaves=draft.owned.leaves), draft.investigated, draft.impacts
                )

            return (strip,)

    with pytest.raises(MissingAffordance, match="already_resolved found no admissible"):
        _construct(NoTickets(), modifiers=(ResolvedDistractor(),))


def test_a_source_needed_only_to_prove_a_negative_is_required() -> None:
    scenario = _construct(MeetingWithClause())
    (expected,) = scenario.key.impacts
    assert expected.must_assess[0].verdict is Verdict.NON_VIABLE
    assert Source.JIRA in scenario.key.required_sources
    assert set(scenario.key.required_sources) >= {Source.FRAPPE, Source.CALENDAR, Source.CORPUS}


def test_a_source_that_turns_an_absent_unknown_into_an_inaccessible_one_is_required() -> None:
    scenario = _construct(MeetingWithClause(blank_candidate=True))
    (expected,) = scenario.key.impacts
    assert expected.must_assess[0].verdict is Verdict.UNKNOWN
    assert Source.JIRA in scenario.key.required_sources


def test_a_draft_states_each_impact_once() -> None:
    (construction,) = OneTicket().admissible(ORG)[:1]
    frame = Frame(
        scenario_id(1), WINDOW, DateSpan(date(2026, 3, 6), date(2026, 3, 8)),
        datetime(2026, 3, 3, 9, 0, tzinfo=ZoneInfo(TZ)), TZ, WORLD_START, Minting(),
    )
    draft = construction(frame, Random(1))
    (expected,) = draft.impacts
    twice = (expected, ExpectedImpact(expected.key, CoverageActionKind.UNCOVERED, ()))
    with pytest.raises(ValueError, match="states each impact once"):
        Draft(draft.owned, draft.investigated, twice)


def test_a_candidate_authored_from_outside_the_organization_is_named() -> None:
    with pytest.raises(ScenarioInvariantFailed, match="emp_999 is authored .* not in the org"):
        _construct(OneTicket(ghost=True))


def test_the_id_book_numbers_world_wide_across_scenarios() -> None:
    ids = Minting()
    first = construct(
        OneTicket(), (), ORG, scenario_id=scenario_id(1), window=WINDOW,
        world_start=WORLD_START, reference_timezone=TZ, ids=ids, rng=Random(1),
    )
    later = DateSpan(WINDOW.end + timedelta(days=2), WINDOW.end + timedelta(days=15))
    second = construct(
        OneTicket(), (), ORG, scenario_id=scenario_id(2), window=later,
        world_start=WORLD_START, reference_timezone=TZ, ids=ids, rng=Random(2),
    )
    assert first.owned.work_items[0].entity.id != second.owned.work_items[0].entity.id
    assert first.spec.leave_id != second.spec.leave_id
