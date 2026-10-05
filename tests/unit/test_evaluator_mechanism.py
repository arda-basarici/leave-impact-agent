"""The mechanism measure through the registered analysis: the arms it is reported for, the four
stages over one denominator at the whole and by tier, a scenario with nothing to count kept
out of every ratio, the stages by predicate, the supporting detail, and the contrasts on the
pairs the registration compares and on no other."""

import pytest

from leaveimpact.core import PredicateName, System, SystemKind
from leaveimpact.core.stated import FactRefusal
from leaveimpact.evaluator.analysis import (
    Analysis,
    ContrastOf,
    MechanismArm,
    MechanismContrast,
    analyse,
)
from leaveimpact.evaluator.cells import StratumKind
from leaveimpact.evaluator.fact_stages import EmissionClass, PlacementOutcome
from leaveimpact.evaluator.intervals import Unresolved
from leaveimpact.evaluator.mechanism import (
    STAGE_MEASURES,
    STAGE_MEASURES_BY_PREDICATE,
    stage_measure,
)
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import RatioEstimate
from leaveimpact.evaluator.trace_metrics import Evaluation
from tests.unit.evaluation_fixture import BASE, PADDED, evaluated, relabelled
from tests.unit.registration_fixture import DRAFT, decided, light, named
from tests.unit.stating_fixture import truthful_stater_runs
from tests.unit.throwaway_world import loaded_world

AGENT = System(SystemKind.AGENT, "graph")
FULL_CONTEXT = System(SystemKind.FULL_CONTEXT, "all-documents")


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture(scope="module")
def analysis(world: SealedWorld) -> Analysis:
    """The agent through the gates at base and let in whole at padded, full context the
    other way round, and the reference system beside them."""
    registration = light(
        decided(named(DRAFT, agent=AGENT.variant, full_context=FULL_CONTEXT.variant), True)
    )
    whole, gated = truthful_stater_runs(gated=False), truthful_stater_runs(gated=True)
    runs: list[Evaluation] = [evaluated(world, scenario) for scenario in world.scenarios]
    for system, at_base, at_padded in ((AGENT, gated, whole), (FULL_CONTEXT, whole, gated)):
        runs += [relabelled(run, system=system, level=BASE) for run in at_base]
        runs += [relabelled(run, system=system, level=PADDED) for run in at_padded]
    return analyse(world, runs, registration)


def arm_of(held: Analysis, kind: SystemKind, condition: str, level: str) -> MechanismArm:
    assert held.mechanism is not None
    (found,) = (
        arm
        for arm in held.mechanism.arms
        if (arm.system.kind, arm.condition, arm.level) == (kind, condition, level)
    )
    return found


def counts(estimates: tuple[RatioEstimate, ...], kind: StratumKind, name: str) -> list[str]:
    return [
        f"{each.numerator}/{each.denominator}"
        for each in estimates
        if (each.stratum.kind, each.stratum.name) == (kind, name)
    ]


def contrast_of(held: Analysis, of: ContrastOf, system: SystemKind) -> MechanismContrast:
    assert held.mechanism is not None
    (found,) = (
        each for each in held.mechanism.contrasts if each.of is of and each.first.system is system
    )
    return found


# --- The arms ------------------------------------------------------------------------------------


def test_the_measure_is_reported_for_the_scored_arms_of_the_systems_that_state_facts(
    analysis: Analysis,
) -> None:
    mechanism = analysis.mechanism
    assert analysis.mechanism_pending is None and mechanism is not None
    assert (mechanism.name, mechanism.stages) == (
        "needed_prose_facts",
        ("returned", "emitted", "admitted", "usable"),
    )
    assert [(arm.system.kind.value, arm.condition, arm.level) for arm in mechanism.arms] == [
        (kind, condition, level)
        for kind in ("agent", "full_context")
        for condition, level in (
            ("normal", BASE),
            ("normal", PADDED),
            ("calendar_down", BASE),
            ("jira_down", BASE),
        )
    ]


def test_the_four_stages_fall_over_one_denominator_at_the_whole_and_by_tier(
    analysis: Analysis,
) -> None:
    agent = arm_of(analysis, SystemKind.AGENT, "normal", BASE)
    assert [each.measure for each in agent.stages[:4]] == [m.name for m in STAGE_MEASURES]
    assert counts(agent.stages, StratumKind.OVERALL, "overall") == [
        "31/31",
        "31/31",
        "17/31",
        "17/31",
    ]
    assert counts(agent.stages, StratumKind.TIER, "structured") == ["0/0"] * 4
    assert counts(agent.stages, StratumKind.TIER, "fragmented") == [
        "20/20",
        "20/20",
        "10/20",
        "10/20",
    ]
    assert counts(agent.stages, StratumKind.TIER, "adversarial") == [
        "11/11",
        "11/11",
        "7/11",
        "7/11",
    ]
    # A scenario whose answer needs no prose statement is in scope with nothing to count:
    # it is in no ratio, and the estimate says how many there were.
    whole = agent.stages[0]
    assert (whole.scenarios, whole.empty) == (30, 10)
    structured = next(each for each in agent.stages if each.stratum.name == "structured")
    assert (structured.scenarios, structured.empty, structured.value) == (10, 10, None)
    assert structured.unresolved is Unresolved.ZERO_DENOMINATOR
    # No class stratum: the measure is cut at the whole and at the tiers.
    assert {each.stratum.kind for each in agent.stages} == {StratumKind.OVERALL, StratumKind.TIER}
    # The arm nobody ran has no scenario in scope, which is not a stage at nought.
    idle = arm_of(analysis, SystemKind.AGENT, "jira_down", BASE)
    assert {(each.scenarios, each.denominator) for each in idle.stages} == {(0, 0)}


def test_the_stages_by_predicate_are_at_the_whole(analysis: Analysis) -> None:
    agent = arm_of(analysis, SystemKind.AGENT, "normal", BASE)
    assert [each.measure for each in agent.by_predicate] == [
        m.name for m in STAGE_MEASURES_BY_PREDICATE
    ]
    assert {each.stratum.kind for each in agent.by_predicate} == {StratumKind.OVERALL}
    admitted = {
        name: next(
            f"{each.numerator}/{each.denominator}"
            for each in agent.by_predicate
            if each.measure == stage_measure("admitted", name).name
        )
        for name in (
            PredicateName.REQUIRES,
            PredicateName.HAS_SKILL,
            PredicateName.NAMES_RESPONSIBLE,
            PredicateName.OWNS_WORK_ITEM,
            PredicateName.MEMBER_OF_COMPONENT,
        )
    }
    assert list(admitted.values()) == ["17/17", "0/5", "0/5", "0/4", "0/0"]


def test_the_supporting_detail_counts_every_emission_once(analysis: Analysis) -> None:
    agent = arm_of(analysis, SystemKind.AGENT, "normal", BASE)
    whole = agent.detail[0]
    assert (whole.stratum.kind, whole.runs) == (StratumKind.OVERALL, 30)
    assert dict(whole.emissions) == {
        EmissionClass.NEEDED: 31,
        EmissionClass.TRUE_UNNEEDED: 899,
    }
    # The truthful stater states each fact once, so distinct statements are the emissions.
    assert whole.distinct == whole.emissions
    assert dict(whole.refused) == {FactRefusal.MISSING_ANCHOR: 420}
    assert whole.excluded == ()
    placed = dict(whole.placements)
    assert set(placed) <= {PlacementOutcome.ON_THE_SEALED_TARGET, PlacementOutcome.UNPLACED}
    assert sum(placed.values()) == 510
    assert [each.stratum.name for each in agent.detail] == [
        "overall",
        "structured",
        "fragmented",
        "adversarial",
    ]
    assert sum(each.runs for each in agent.detail[1:]) == whole.runs
    # Let in whole, nothing is refused in the record.
    padded = arm_of(analysis, SystemKind.AGENT, "normal", PADDED)
    assert padded.detail[0].refused == ()
    assert sum(dict(padded.detail[0].placements).values()) == 510


# --- The contrasts -------------------------------------------------------------------------------


def test_the_stages_are_contrasted_on_the_registered_pairs_and_on_no_other(
    analysis: Analysis,
) -> None:
    mechanism = analysis.mechanism
    assert mechanism is not None
    assert [(c.of, c.first.system, c.second.system) for c in mechanism.contrasts] == [
        (ContrastOf.PRIMARY, SystemKind.AGENT, SystemKind.FULL_CONTEXT),
        (ContrastOf.SECONDARY, SystemKind.AGENT, SystemKind.SINGLE_SHOT),
        (ContrastOf.SECONDARY, SystemKind.AGENT, SystemKind.SINGLE_SHOT),
        (ContrastOf.LEVEL_CONTRAST, SystemKind.AGENT, SystemKind.AGENT),
        (ContrastOf.LEVEL_CONTRAST, SystemKind.SINGLE_SHOT, SystemKind.SINGLE_SHOT),
        (ContrastOf.LEVEL_CONTRAST, SystemKind.FULL_CONTEXT, SystemKind.FULL_CONTEXT),
    ]
    primary = contrast_of(analysis, ContrastOf.PRIMARY, SystemKind.AGENT)
    assert (primary.first.level, primary.second.level, primary.unavailable) == (
        PADDED,
        PADDED,
        None,
    )
    # Four stages at the whole and at each of three tiers.
    assert len(primary.stages) == 16
    admitted = next(
        each
        for each in primary.stages
        if each.measure == stage_measure("admitted").name
        and each.stratum.kind is StratumKind.OVERALL
    )
    assert (admitted.paired, admitted.first, admitted.second) == (30, 1.0, 17 / 31)
    assert admitted.interval is not None and admitted.interval.low > 0
    returned = primary.stages[0]
    assert (returned.first, returned.second, returned.unresolved) == (
        1.0,
        1.0,
        Unresolved.EVERY_RESAMPLE_EQUAL,
    )
    # A pair with a system that cannot be built is kept and says why.
    for unbuilt in mechanism.contrasts[1], mechanism.contrasts[2], mechanism.contrasts[4]:
        assert unbuilt.stages == () and "single_shot" in (unbuilt.unavailable or "")


def test_a_level_contrast_of_the_stages_is_one_system_at_two_levels(analysis: Analysis) -> None:
    for system, padded, base in (
        (SystemKind.AGENT, 1.0, 17 / 31),
        (SystemKind.FULL_CONTEXT, 17 / 31, 1.0),
    ):
        contrast = contrast_of(analysis, ContrastOf.LEVEL_CONTRAST, system)
        assert (contrast.first.level, contrast.second.level) == (PADDED, BASE)
        assert contrast.first.system is contrast.second.system
        admitted = next(
            each
            for each in contrast.stages
            if each.measure == stage_measure("admitted").name
            and each.stratum.kind is StratumKind.OVERALL
        )
        assert (admitted.first, admitted.second) == (padded, base)


def test_the_stages_enter_no_other_table(analysis: Analysis) -> None:
    # A stage is no registered measure: no arm's cell and no descriptive comparison holds one.
    names = {measure.name for measure in (*STAGE_MEASURES, *STAGE_MEASURES_BY_PREDICATE)}
    for arm in analysis.arms:
        for cell in arm.cells:
            assert not names & {each.measure for each in cell.measures or ()}
    for row in analysis.descriptive:
        assert not names & {each.measure for each in row.measures}
