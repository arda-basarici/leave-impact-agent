"""The preregistration as the evaluator reads it: names resolved against this package's own
registries, the estimation plan projected, and the scenario sets cut.

Names live in the registration and behaviour here (the investigator milestone's sixth
build step, rulings 1, 4 and 6). A registered measure or check is an identifier; the
registries below say which function it is, and a name they do not hold is refused, never
skipped: a table that silently lacked a registered row would read as a smaller plan.

A registered measure is a family of rows, the leading one first. An answer-side measure
is over all claims, then per claim type. A grounding or a citation measure is over graded
runs, then over limited ones, the two never pooled: a limited run has no expected answer
and its report was written with a source missing. A source-discipline or a retrieval
measure is one row. A comparison between two systems is made on a family's leading row;
the rest are reported per arm.

``preregistered`` projects the registration onto ``Preregistered``, the one record the
cells and the tables are cut under. An arm needs its system's variant, and a variant may
still be pending in a draft; such an arm cannot be built, and the projection says which
ones it left out instead of refusing the rest, since the baseline's development tables do
not need the agent's variant. Nothing is left to project when every arm is pending, and
that is refused. The retry rule the attempt histories are read under is the one this
package implements, retries after an infrastructure failure only, so another category is
refused here. So is a registered prefetch that is not the one this code plans, by
identifier, protocol version or digest: the conformance check holds a run to this code's
plan, and under another registered rule it would manufacture findings from a planner the
registration never named.

The scenario sets: the full set is the world's scenarios, the primary set the ones held
out from scenario-specific tuning, every scenario that is not a development one. The
development scenarios are selected by tier alone: a seeded draw of the registered number
from each tier, the stream derived from the registration's seed, so the selection is
reproducible and reads no expected answer. A draw, and not the first ids of a tier,
because ids follow the generator's construction order and the first of a tier may share a
scenario class.

A registered development list is held to the registered allocation before the primary set
is cut from it: the registered number from every tier. The registration's own type cannot
check this, a scenario's tier being sealed, and a list that passed it unbalanced would
leave a primary set unbalanced the other way with nothing to say so. The list is not held
to the draw itself: the draw is how the list is first produced, and a seed changed later
must not disown the scenarios the tuning was really done on. The refusal names no tier
and no count per tier, since which listed scenarios share a tier is sealed and the
evaluation's log is public.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from random import Random

from leaveimpact.core.facts import RunCondition
from leaveimpact.core.ids import ScenarioId
from leaveimpact.core.prefetch import PREFETCH_PROTOCOL, prefetch_rule
from leaveimpact.core.registration import (
    Pending,
    RegisteredArm,
    Registration,
    ScenarioSetName,
)
from leaveimpact.core.run_record import FailureCategory, System
from leaveimpact.evaluator.cells import CountedAttempt, MissingRepeat, Preregistered
from leaveimpact.evaluator.evidence_measures import (
    RETRIEVAL_MEASURES,
    SOURCE_MEASURES,
    Replayed,
    citing_a_witness_share,
    citing_share,
    grounded_end_to_end_share,
    local_failure_share,
    resolving_share,
    retrieved_share,
    standing_share,
    strictly_grounded_share,
    used_share,
)
from leaveimpact.evaluator.grading import Graded, Limited
from leaveimpact.evaluator.intervals import derived_seed
from leaveimpact.evaluator.measures import ANSWER_MEASURES, Measure, conflict_observations
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.run_checks import CORRECT_WHOLE, EXPECTED_ACTION, REPRODUCED_WHOLE
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.tables import Check
from leaveimpact.world.scenario import Tier


def _answer(display: str) -> tuple[Measure, ...]:
    """The answer-side family named ``display``: over all claims, then per claim type."""
    return tuple(m for m in ANSWER_MEASURES if m.name.startswith(f"{display}: "))


def _replayed(build: Callable[[Replayed], Measure]) -> tuple[Measure, ...]:
    """A grounding or a citation measure over graded runs, then over limited ones."""
    return build(Graded), build(Limited)


def _named(held: tuple[Measure, ...], display: str) -> tuple[Measure, ...]:
    (found,) = (measure for measure in held if measure.name == display)
    return (found,)


MEASURES: dict[str, tuple[Measure, ...]] = {
    "strict_precision": _answer("strict precision"),
    "type_local_precision": _answer("type-local precision"),
    "recall": _answer("recall"),
    "payload_accuracy": _answer("payload accuracy"),
    "conflict_observations_holding": (conflict_observations(),),
    "claims_reproduced": _replayed(lambda over: standing_share(Standing.REPRODUCED, over)),
    "claims_contradicted": _replayed(lambda over: standing_share(Standing.CONTRADICTED, over)),
    "claims_unsupported": _replayed(lambda over: standing_share(Standing.UNSUPPORTED, over)),
    "claims_failing_locally": _replayed(local_failure_share),
    "claims_grounded_end_to_end": _replayed(grounded_end_to_end_share),
    "claims_strictly_grounded": _replayed(strictly_grounded_share),
    "claims_citing": _replayed(citing_share),
    "citations_resolving": _replayed(resolving_share),
    "citations_retrieved": _replayed(retrieved_share),
    "citations_used": _replayed(used_share),
    "reproduced_claims_citing_a_witness": _replayed(citing_a_witness_share),
    "required_sources_asked": _named(SOURCE_MEASURES, "required sources asked"),
    "required_sources_answered": _named(SOURCE_MEASURES, "required sources answered"),
    "tool_requests_refused": _named(SOURCE_MEASURES, "tool requests refused"),
    "completed_reads_repeated": _named(SOURCE_MEASURES, "completed reads repeated"),
    "completed_reads_extra": _named(SOURCE_MEASURES, "completed reads extra"),
    "targets_retrieved": _named(RETRIEVAL_MEASURES, "targets retrieved"),
    "required_targets_retrieved": _named(
        RETRIEVAL_MEASURES, "targets a required row rests on retrieved"
    ),
    "searches_with_a_hit": _named(RETRIEVAL_MEASURES, "searches with a hit"),
    "targets_per_search": _named(RETRIEVAL_MEASURES, "searchable targets returned per search"),
}
"""The measures a registration can name, each as its family of rows, the leading one first."""

CHECKS: dict[str, Check] = {
    check.name: check for check in (CORRECT_WHOLE, EXPECTED_ACTION, REPRODUCED_WHOLE)
}
"""The checks a registration can name, by the identifier each carries."""


def registered_measures(name: str) -> tuple[Measure, ...]:
    """The rows of the measure registered as ``name``, the leading one first."""
    if name not in MEASURES:
        raise ValueError(
            f"no measure is registered as {name!r}; this evaluator holds {list(MEASURES)}"
        )
    return MEASURES[name]


def registered_check(name: str) -> Check:
    """The check registered as ``name``."""
    if name not in CHECKS:
        raise ValueError(f"no check is registered as {name!r}; this evaluator holds {list(CHECKS)}")
    return CHECKS[name]


@dataclass(frozen=True, slots=True)
class Projection:
    """The plan the tables are cut under, and the registered arms it could not hold because
    their system's variant is still pending."""

    plan: Preregistered
    pending_arms: tuple[RegisteredArm, ...]


def preregistered(registration: Registration) -> Projection:
    """``registration`` as the estimation plan, every name it registers resolved.

    Raises ``ValueError`` for a check or a measure this evaluator does not hold, a retry
    rule it does not implement, a registered prefetch other than the one this code plans,
    and a registration with no arm whose variant is resolved.
    """
    _require_registered_prefetch(registration)
    statistics = registration.statistics
    for name in statistics.checks:
        registered_check(name)
    for name in statistics.measures:
        registered_measures(name)
    accounting = registration.run_accounting
    if accounting.retry.after is not FailureCategory.INFRASTRUCTURE:
        raise ValueError(
            "attempt histories are read under retries after an infrastructure failure, "
            f"the registration retries after {accounting.retry.after.value}"
        )
    arms: list[tuple[System, RunCondition]] = []
    pending: list[RegisteredArm] = []
    for arm in registration.arms:
        system = registration.system(arm.system)
        condition = registration.outage.condition(arm.condition)
        assert system is not None and condition is not None, arm
        if isinstance(system.variant, Pending):
            pending.append(arm)
            continue
        assigned = RunCondition.all_reachable().without(*condition.unreachable)
        arms.append((System(arm.system, system.variant), assigned))
    if not arms:
        raise ValueError("no registered arm can be built: every system's variant is pending")
    plan = Preregistered(
        confidence=statistics.confidence_percent / 100,
        seed=statistics.seed,
        resamples=statistics.resamples,
        intended_repeats=accounting.repeats,
        counted_attempt=CountedAttempt(accounting.counted_attempt.value),
        missing_repeat=MissingRepeat(accounting.missing_run.value),
        arms=tuple(arms),
        max_attempts=accounting.retry.max_attempts,
    )
    return Projection(plan, tuple(pending))


def _require_registered_prefetch(registration: Registration) -> None:
    registered = registration.prefetch
    rule = prefetch_rule()
    declared = (registered.identifier, registered.protocol_version, registered.digest)
    computed = (rule.identifier, PREFETCH_PROTOCOL[1], rule.digest)
    if declared != computed:
        raise ValueError(
            f"the registered prefetch is {declared}, this evaluator checks conformance to "
            f"{computed} (identifier, protocol version, digest)"
        )


def scenario_set(
    world: SealedWorld, registration: Registration, name: ScenarioSetName
) -> tuple[ScenarioId, ...]:
    """The scenarios of ``world`` in the set ``name``, in the world's order.

    Raises ``ValueError`` for the primary set while the development scenarios are pending,
    when a registered development scenario is not one of ``world``'s, and when the
    registered ones are not the registered number from each tier.
    """
    every = tuple(scenario.spec.id for scenario in world.scenarios)
    if name is ScenarioSetName.FULL:
        return every
    development = registration.scenario_sets.development
    if isinstance(development, Pending):
        raise ValueError(
            "the primary set is every scenario that is not a development one, and the "
            f"development scenarios are pending ({development.awaiting})"
        )
    strangers = sorted(set(development) - set(every))
    if strangers:
        raise ValueError(f"the world holds no scenario {', '.join(strangers)}")
    per_tier = registration.scenario_sets.development_per_tier
    for tier in Tier:
        held = [s.spec.id for s in world.scenarios if s.key.tier is tier]
        if held and sum(scenario in development for scenario in held) != per_tier:
            raise ValueError(
                f"the registered development scenarios are not {per_tier} from each tier of "
                "the world"
            )
    return tuple(scenario for scenario in every if scenario not in development)


def development_selection(world: SealedWorld, registration: Registration) -> tuple[ScenarioId, ...]:
    """The development scenarios of ``world`` as ``registration`` selects them: the
    registered number from each tier, drawn by a stream derived from its seed, in id order.

    Reads each scenario's tier and nothing else of its key. Raises ``ValueError`` when the
    world's tiers cannot give the registered numbers.
    """
    sets = registration.scenario_sets
    by_tier = {
        tier: sorted(s.spec.id for s in world.scenarios if s.key.tier is tier) for tier in Tier
    }
    held = {tier: ids for tier, ids in by_tier.items() if ids}
    if sets.development_per_tier * len(held) != sets.development_size:
        raise ValueError(
            f"{sets.development_size} development scenarios at {sets.development_per_tier} "
            f"per tier need {sets.development_size // sets.development_per_tier} tiers, "
            f"the world has {len(held)}"
        )
    selected: list[ScenarioId] = []
    for tier, ids in held.items():
        if len(ids) < sets.development_per_tier:
            raise ValueError(
                f"a tier of {len(ids)} scenarios cannot give {sets.development_per_tier} "
                "development scenarios"
            )
        stream = Random(
            derived_seed(registration.statistics.seed, "development-scenarios", tier.value)
        )
        selected.extend(stream.sample(ids, sets.development_per_tier))
    return tuple(sorted(selected))


__all__ = [
    "CHECKS",
    "MEASURES",
    "Projection",
    "development_selection",
    "preregistered",
    "registered_check",
    "registered_measures",
    "scenario_set",
]
