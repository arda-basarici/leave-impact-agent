"""The scenario vocabulary: each record rejects at construction what the framework must never
compose — a naive or out-of-window ``now``, reasons on a viable verdict, a candidate authored
twice, duplicate impact keys, a spec and key naming different scenarios, an investigated
leave the scenario does not own."""

from dataclasses import replace
from datetime import UTC, date, datetime

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
    work_item_ref,
)
from leaveimpact.core.ids import employee_id, leave_id, scenario_id, work_item_id
from leaveimpact.world.scenario import (
    AuthoredVerdict,
    ExpectedImpact,
    ModifierEffect,
    OwnedEntities,
    Planted,
    Scenario,
    ScenarioClassName,
    ScenarioKey,
    ScenarioSpec,
    Tier,
)

WINDOW = DateSpan(date(2026, 3, 1), date(2026, 3, 14))
NOW = datetime(2026, 3, 6, 6, 0, tzinfo=UTC)  # 09:00 in Istanbul


def _spec(now: datetime = NOW, leave: int = 1) -> ScenarioSpec:
    return ScenarioSpec(scenario_id(1), leave_id(leave), now, "Europe/Istanbul", WINDOW)


def _impact(ticket: int = 42) -> ImpactKey:
    return ImpactKey(leave_id(1), ImpactSubtype.DEADLINE, work_item_ref(work_item_id(ticket)))


def _key(impacts: tuple[ExpectedImpact, ...], scenario: int = 1) -> ScenarioKey:
    return ScenarioKey(
        scenario_id=scenario_id(scenario),
        tier=Tier.STRUCTURED,
        scenario_class=ScenarioClassName.STRUCTURED_DEADLINE,
        modifiers=(),
        impacts=impacts,
        constraints=(),
        distractors=(),
        stable_interval=DateSpan(date(2026, 3, 1), date(2026, 3, 9)),
        required_sources=(Source.FRAPPE, Source.JIRA),
    )


def test_today_is_now_read_in_the_reference_timezone() -> None:
    late = datetime(2026, 3, 5, 22, 30, tzinfo=UTC)  # already the 6th in Istanbul
    assert _spec(late).today == date(2026, 3, 6)


def test_a_spec_rejects_a_naive_now_and_a_now_outside_its_window() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _spec(datetime(2026, 3, 6, 9, 0))
    with pytest.raises(ValueError, match="inside its window"):
        _spec(datetime(2026, 3, 20, 9, 0, tzinfo=UTC))


def test_reasons_travel_with_the_non_viable_verdict_only() -> None:
    AuthoredVerdict(employee_id(3), Verdict.NON_VIABLE, (AssessmentReason.SKILL,))
    AuthoredVerdict(employee_id(3), Verdict.UNKNOWN)
    with pytest.raises(ValueError, match="names its reasons"):
        AuthoredVerdict(employee_id(3), Verdict.NON_VIABLE)
    with pytest.raises(ValueError, match="non-viable verdict only"):
        AuthoredVerdict(employee_id(3), Verdict.UNKNOWN, (AssessmentReason.SKILL,))


def test_a_candidate_is_authored_once_per_impact() -> None:
    twice = (
        AuthoredVerdict(employee_id(3), Verdict.VIABLE),
        AuthoredVerdict(employee_id(3), Verdict.UNKNOWN),
    )
    with pytest.raises(ValueError, match="authored once"):
        ExpectedImpact(_impact(), CoverageActionKind.ASSIGN, twice)


def test_a_key_needs_an_impact_and_unique_keys_and_unique_tags() -> None:
    expected = ExpectedImpact(_impact(), CoverageActionKind.ASSIGN, ())
    with pytest.raises(ValueError, match="at least one impact"):
        _key(())
    with pytest.raises(ValueError, match="unique within a scenario"):
        _key((expected, expected))
    key = _key((expected,))
    with pytest.raises(ValueError, match="listed once"):
        replace(key, required_sources=(Source.JIRA, Source.JIRA))


def test_a_scenario_binds_one_id_and_owns_the_leave_it_investigates() -> None:
    leave = Leave(
        leave_id(1), employee_id(17), date(2026, 3, 10), date(2026, 3, 12),
        LeaveKind.ANNUAL, LeaveStatus.APPROVED,
    )
    owned = OwnedEntities(leaves=(Planted(leave, date(2026, 3, 1)),))
    key = _key((ExpectedImpact(_impact(), CoverageActionKind.ASSIGN, ()),))
    scenario = Scenario(_spec(), key, owned)
    assert scenario.spec.today == date(2026, 3, 6)
    with pytest.raises(ValueError, match="name one scenario"):
        Scenario(_spec(), _key(key.impacts, scenario=2), owned)
    with pytest.raises(ValueError, match="one the scenario owns"):
        Scenario(_spec(leave=2), key, owned)


def test_a_modifier_effect_defaults_to_no_change() -> None:
    assert ModifierEffect() == ModifierEffect((), ())
