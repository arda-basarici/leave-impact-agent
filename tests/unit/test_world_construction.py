"""The construction framework, exercised with minimal test doubles: a class that plants one ticket
due inside the leave and authors one candidate, and modifiers that plant a concurrent leave or a
resolved distractor. The doubles are framework probes, not scenario classes — each test asserts
one framework behaviour: selection among admissible constructions, composition of declared
effects, the two invariants, the named errors, and determinism over the whole result."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from random import Random

import pytest

from leaveimpact.core import (
    AssessmentReason,
    CoverageActionKind,
    DateSpan,
    ImpactKey,
    ImpactSubtype,
    Leave,
    LeaveKind,
    LeaveStatus,
    Source,
    Verdict,
    WorkItem,
    WorkItemStatus,
    work_item_ref,
)
from leaveimpact.core.ids import ComponentId, EmployeeId, scenario_id
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
    name = ScenarioClassName.STRUCTURED_DEADLINE
    tier = Tier.STRUCTURED
    affordance = "a component with at least three members"

    def admissible(self, org: OrgSpec) -> tuple[Construction, ...]:
        constructions: list[Construction] = []
        for component in org.components:
            if len(component.member_ids) < 3:
                continue
            leaver, candidate = component.member_ids[0], component.member_ids[1]

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
