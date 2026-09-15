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
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import ComponentId, EmployeeId, employee_id, scenario_id, skill_id
from leaveimpact.core.viability import assess_impact
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
from leaveimpact.world.briefs import ProseContractError, Register
from leaveimpact.world.construction import (
    Amendment,
    Claims,
    ConflictingEffects,
    Construction,
    Draft,
    Frame,
    Minting,
    MissingAffordance,
    Modifier,
    ReservationExhausted,
    Reservations,
    ScenarioClass,
    ScenarioInvariantFailed,
    claims_of,
    construct,
)
from leaveimpact.world.prose import FactRole
from leaveimpact.world.truth_facts import truth_fact_base
from tests.unit.prose_fixture import (
    KAFKA,
    PYTHON,
    ContactInNote,
    SkillInComment,
    StaleOwnerInRunbook,
    pending_scenario,
)

ORG = generate_org(7, DEFAULT_PARAMS)
WORLD_START = date(2026, 1, 1)
WINDOW = DateSpan(date(2026, 3, 1), date(2026, 3, 14))
TZ = "Europe/Istanbul"


@dataclass(frozen=True)
class OneTicket:
    """A leaver in a component owns a ticket due inside the leave; a fellow member is the candidate.

    ``lie`` authors the candidate the wrong way round; ``wrong_outcome`` declares uncovered
    where the org has cover; ``unowned`` gives the ticket to the candidate so the declared
    impact has no ground. All exist so the invariants have something to catch.
    """

    lie: bool = False
    wrong_outcome: bool = False
    ghost: bool = False
    unowned: bool = False
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
                    owner_id=candidate if self.unowned else leaver,
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


class UndatedTicket:
    """A modifier double that plants an open, undated ticket the leaver owns and declares
    nothing — an obligation the key does not know about."""

    name = ModifierName.ALREADY_RESOLVED
    affordance = "a ticket the leaver owns"

    def admissible(self, org: OrgSpec, draft: Draft) -> tuple[Amendment, ...]:
        def amend(draft: Draft, frame: Frame, rng: Random) -> tuple[Draft, ModifierEffect]:
            owned_ticket = draft.owned.work_items[0].entity
            undated = WorkItem(
                id=frame.ids.work_item(),
                title="Ledger cleanup",
                owner_id=owned_ticket.owner_id,
                status=WorkItemStatus.IN_PROGRESS,
                component_id=owned_ticket.component_id,
                opened_on=frame.window.start,
                resolved_on=None,
                due_on=None,
                comments=(),
            )
            planted = OwnedEntities(work_items=(Planted(undated, frame.window.start),))
            return draft.extended(owned=planted), ModifierEffect()

        return (amend,) if draft.owned.work_items else ()


def _construct(
    scenario_class: ScenarioClass = ONE_TICKET,
    modifiers: Sequence[Modifier] = (),
    seed: int = 1,
    reservations: Reservations | None = None,
    ids: Minting | None = None,
):
    return construct(
        scenario_class,
        modifiers,
        ORG,
        scenario_id=scenario_id(1),
        window=WINDOW,
        world_start=WORLD_START,
        reference_timezone=TZ,
        ids=Minting() if ids is None else ids,
        rng=Random(seed),
        reservations=reservations,
    )


def _draft(scenario_class: ScenarioClass, index: int = 0) -> Draft:
    now = datetime(2026, 3, 3, 9, tzinfo=ZoneInfo(TZ))
    frame = Frame(scenario_id(1), WINDOW, WINDOW, now, TZ, WORLD_START, Minting())
    return scenario_class.admissible(ORG)[index](frame, Random(1))


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
    (blank,) = expected.must_assess
    assert blank.verdict is Verdict.UNKNOWN
    assert Source.JIRA in scenario.key.required_sources
    # The counterfactual itself, through core's own assessment: with the tracker reachable
    # the candidate's skill is unknown because the record is blank; with it unreachable the
    # same candidate is unknown because a source of the skill's domain could not answer.
    # One verdict, two conclusions — the difference the outage comparison must carry.
    base = truth_fact_base(ORG, WORLD_START, [scenario.owned], scenario.authored_facts)
    normal = RunCondition.all_reachable()
    reasons = {}
    for label, condition in (("normal", normal), ("outage", normal.without(Source.JIRA))):
        (assessment,) = assess_impact(
            base.at(scenario.spec.today, condition), expected.key, [blank.employee_id],
            scenario.key.constraints, scenario.investigated_leave.span, TZ,
        )
        assert assessment.verdict is Verdict.UNKNOWN
        reasons[label] = {(u.predicate, u.reason) for u in assessment.unresolved}
    assert reasons["normal"] == {(PredicateName.HAS_SKILL, "absent")}
    assert reasons["outage"] == {(PredicateName.HAS_SKILL, "inaccessible")}


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


# --- Pending prose: the framework completes what a class leaves for a model ---------------


def test_a_required_facts_role_is_derived_by_removing_it_from_the_base() -> None:
    """The Kafka fact makes the candidate viable, so removing it moves the verdict; the Python
    fact on the same comment moves nothing and is context."""
    scenario = pending_scenario(SkillInComment(context=True))
    [brief] = scenario.briefs
    roles = {required.fact.value: required.role for required in brief.required}
    assert roles == {KAFKA: FactRole.ANSWER_CHANGING, PYTHON: FactRole.CONTEXT}
    assert brief.register is Register.TICKET_COMMENT
    assert brief.namespace.form_of("skill", KAFKA) == "Kafka"
    [planted] = scenario.owned.work_items
    assert planted.entity.comments == ()  # pending until composed


def test_a_fact_evidenced_by_a_part_nobody_planted_or_briefed_fails_construction_by_name() -> None:
    carried_by_nothing = "neither a part the scenario planted nor a brief's target"
    with pytest.raises(ProseContractError, match=carried_by_nothing):
        pending_scenario(SkillInComment(orphan=True))


def test_a_template_written_clause_carries_its_fact_with_no_brief() -> None:
    scenario = pending_scenario()
    [policy] = scenario.owned.documents
    assert policy.entity.sections[0].text == "A release needs a Kafka engineer."
    skill_facts = [f for f in scenario.authored_facts if f.predicate is PredicateName.HAS_SKILL]
    assert [b.id for b in scenario.briefs] == [f.evidence.target.id for f in skill_facts]


# --- Grounding: the truth entails the declared impacts, and nothing more --------------------


def test_a_declared_impact_the_truth_does_not_ground_fails_construction_by_name() -> None:
    with pytest.raises(ScenarioInvariantFailed, match="declared deadline impact is not the leaver"):
        _construct(OneTicket(unowned=True))


def test_an_obligation_of_the_leaver_the_key_does_not_declare_fails_construction_by_name() -> None:
    undeclared = "grounds a responsibility impact of the leaver that the key does not declare"
    with pytest.raises(ScenarioInvariantFailed, match=undeclared):
        _construct(modifiers=[UndatedTicket()])


def test_a_documented_responsibility_is_answer_changing_through_its_grounding() -> None:
    """The section's fact moves no verdict and no outcome; removing it ungrounds the impact."""
    scenario = pending_scenario(ContactInNote())
    [brief] = scenario.briefs
    [required] = brief.required
    assert required.fact.predicate is PredicateName.NAMES_RESPONSIBLE
    assert required.role is FactRole.ANSWER_CHANGING
    assert brief.register is Register.CLIENT_NOTE
    assert "clause" not in {form.kind for form in brief.namespace.forms}
    assert Source.CORPUS in scenario.key.required_sources


def test_a_stale_owner_in_a_runbook_is_answer_changing_through_the_conflict() -> None:
    """The runbook's fact moves no verdict and no outcome; removing it removes the conflict."""
    scenario = pending_scenario(StaleOwnerInRunbook())
    [brief] = scenario.briefs
    [required] = brief.required
    assert required.fact.predicate is PredicateName.OWNS_WORK_ITEM
    assert required.role is FactRole.ANSWER_CHANGING
    assert brief.register is Register.RUNBOOK
    assert Source.CORPUS in scenario.key.required_sources


# --- The reservation book -------------------------------------------------------------


def test_claims_are_read_off_the_draft_never_declared() -> None:
    """Each fixture binds exactly what its standing facts and absence-based verdicts imply:
    a ticket class only its leave subject; a skill clause with a candidate failing it the
    (person, skill) assumed absent; a skill in a comment the (person, skill) provided; a
    contact in a note the person named."""
    ticket = claims_of(_draft(ONE_TICKET), ORG)
    leaver = ORG.components[0].member_ids[0]
    assert ticket == Claims(leaver)
    clause = claims_of(_draft(MeetingWithClause()), ORG)
    [(person, skill)] = clause.skills_required_absent
    record = next(e for e in ORG.employees if e.id == person)
    assert skill == KAFKA and skill not in (record.skills or ())
    assert clause.standing_contacts == frozenset() and clause.skills_provided == frozenset()
    comment = claims_of(_draft(SkillInComment()), ORG)
    [(candidate, provided)] = comment.skills_provided
    assert provided == KAFKA and candidate != comment.leave_subject
    note = claims_of(_draft(ContactInNote()), ORG)
    assert note.standing_contacts == frozenset({note.leave_subject})


def test_a_standing_contact_and_a_leave_subject_exclude_each_other_in_both_orders() -> None:
    # Construction order never decides correctness: whichever is reserved first, the
    # other is refused, and the refusal names the scenario holding the reservation.
    person, other = employee_id(1), employee_id(2)
    named = Claims(person, standing_contacts=frozenset({person}))
    leave = Claims(person)
    book = Reservations()
    book.reserve(scenario_id(3), named)
    assert book.conflicts(leave) == (
        f"leave subject {person} is a standing contact of scenario_003",
    )
    assert book.conflicts(Claims(other)) == ()
    book = Reservations()
    book.reserve(scenario_id(4), leave)
    assert book.conflicts(named) == (
        f"standing contact {person} is a leave subject of scenario_004",
    )
    # A scenario's own contact being its own leaver is its own key's business, no conflict.
    assert Reservations().conflicts(named) == ()


def test_a_prose_skill_and_an_assumed_absent_skill_exclude_each_other_in_both_orders() -> None:
    person = employee_id(5)
    provided = Claims(employee_id(1), skills_provided=frozenset({(person, KAFKA)}))
    assumed = Claims(employee_id(2), skills_required_absent=frozenset({(person, KAFKA)}))
    elsewhere = Claims(employee_id(2), skills_required_absent=frozenset({(person, PYTHON)}))
    book = Reservations()
    book.reserve(scenario_id(1), provided)
    assert book.conflicts(assumed) == (
        f"kafka assumed absent of {person} is provided by scenario_001",
    )
    assert book.conflicts(elsewhere) == ()
    book = Reservations()
    book.reserve(scenario_id(2), assumed)
    assert book.conflicts(provided) == (
        f"kafka provided to {person} is assumed absent by scenario_002",
    )


def test_the_first_admitted_candidate_is_planted_and_a_refused_one_is_unplanted() -> None:
    """The book refuses the candidate the seed would have chosen, so the next in the seed's
    order is planted; the refused candidate's ids and titles go back to the book, so the
    admitted scenario numbers as if the refused one never was. The unfiltered choice is
    the same draw, so a world the book never refuses anything in is the world it was
    before the book existed."""
    refused = _construct(seed=1).owned.leaves[0].entity.employee_id
    book = Reservations()
    book.reserve(scenario_id(9), Claims(refused, standing_contacts=frozenset({refused})))
    ids = Minting()
    scenario = _construct(seed=1, reservations=book, ids=ids)
    assert scenario.owned.leaves[0].entity.employee_id != refused
    assert scenario.owned.leaves[0].entity.id == "leave_001"
    assert scenario.owned.work_items[0].entity.id == "ticket_001"
    assert ids.leave() == "leave_002"


def test_every_candidate_refused_is_named_with_the_rule_and_the_count() -> None:
    book = Reservations()
    for index in range(len(ONE_TICKET.admissible(ORG))):
        who = claims_of(_draft(ONE_TICKET, index), ORG).leave_subject
        book.reserve(scenario_id(index + 10), Claims(who, standing_contacts=frozenset({who})))
    with pytest.raises(ReservationExhausted, match="the reservation book admits none") as caught:
        _construct(reservations=book)
    assert caught.value.universe == len(ONE_TICKET.admissible(ORG))
    assert sum(caught.value.eliminated.values()) == caught.value.universe
    assert all(rule.startswith("leave subject ") for rule in caught.value.eliminated)

