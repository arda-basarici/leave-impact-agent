"""The preregistration as the evaluator reads it: names resolved against this package's own
registries, and the estimation plan projected.

Names live in the registration and behaviour here (the investigator milestone's sixth
build step, rulings 1, 4 and 6; the contract step's rulings on the registration). A
registered measure, check or interval method is an identifier; the registries below say
which function it is, and a name they do not hold is refused, never skipped: a table that
silently lacked a registered row would read as a smaller plan.

A registered measure is a family of rows, the leading one first. An answer-side measure
is over all claims, then per claim type. A grounding or a citation measure is over graded
runs, then over limited ones, the two never pooled: a limited run has no expected answer
and its report was written with a source missing. A source-discipline or a retrieval
measure is one row. A comparison between two systems is made on a family's leading row;
the rest are reported per arm.

``preregistered`` projects the registration onto ``Preregistered``, the one record the
cells and the tables are cut under. A registered cell becomes an arm of the plan unless one
of two things holds, and the projection says which cells it left out and why instead of
refusing the rest, since the baseline's development tables do not need the agent's roles.
The cell belongs to a conditional group that is not decided as run: nobody executes it and
nothing is reported for it. Or its system has a value pending that an execution needs
(``core.registration.blocking``), the one reading the harness and the eligibility check
share. Nothing is left to project when every cell is left out, and that is refused.

What is refused whole, because tables cut under it would be about something else: a retry
rule other than the one the attempt histories are read under, retries after an
infrastructure failure only; a registered prefetch that is not the one this code plans, by
identifier, protocol version or digest, since the conformance check would manufacture
findings from a planner the registration never named; a registered anchor table that is
not ``core``'s, the one part of the stated-fact contract this package can compute; and a
resolved mechanism measure this evaluator does not hold. While the mechanism measure is
pending the analysis says so with its reason and computes none.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.anchors import anchor_table_digest
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.prefetch import PREFETCH_PROTOCOL, prefetch_rule
from leaveimpact.core.registration import (
    MechanismMeasure,
    Pending,
    RegisteredCell,
    Registration,
    blocking,
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
from leaveimpact.evaluator.measures import ANSWER_MEASURES, Measure, conflict_observations
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.run_checks import CORRECT_WHOLE, EXPECTED_ACTION, REPRODUCED_WHOLE
from leaveimpact.evaluator.tables import Check


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

INTERVAL_METHODS: tuple[str, ...] = ("paired_scenario_bootstrap_within_tier",)
"""The interval methods a registration can name. The one held is what ``tables`` computes:
scenarios resampled within their tier, a scenario's repeats kept together, two arms paired
on the scenario, by one method at any repeat count."""

MECHANISM_MEASURES: tuple[str, ...] = ()
"""The mechanism measures a registration can name; none until the fact-stage measures are
built, so a registration holds its mechanism measure pending until then."""


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


class WhyUnbuilt(StrEnum):
    """Why a registered cell is no arm of the plan; a member is the wire format."""

    GROUP_NOT_RUN = "group_not_run"
    """Its conditional group is not decided as run: pending, or decided against."""
    SYSTEM_PENDING = "system_pending"
    """Its system has a value pending that an execution needs."""


@dataclass(frozen=True, slots=True)
class Unbuilt:
    """A registered cell the plan does not hold, why, and what in the registration says so:
    the group, or the pending values by name."""

    cell: RegisteredCell
    why: WhyUnbuilt
    detail: str


@dataclass(frozen=True, slots=True)
class Projection:
    """The plan the tables are cut under, and the registered cells it does not hold."""

    plan: Preregistered
    unbuilt: tuple[Unbuilt, ...]


def preregistered(registration: Registration) -> Projection:
    """``registration`` as the estimation plan, every name it registers resolved.

    Raises ``ValueError`` for a check, a measure, an interval method or a resolved
    mechanism measure this evaluator does not hold, a retry rule it does not implement, a
    registered prefetch or anchor table other than this code's, and a registration with no
    cell that can be built.
    """
    _require_registered_prefetch(registration)
    _require_registered_anchors(registration)
    statistics = registration.statistics
    for name in statistics.checks:
        registered_check(name)
    for name in statistics.measures:
        registered_measures(name)
    if statistics.interval_method not in INTERVAL_METHODS:
        raise ValueError(
            f"no interval method is registered as {statistics.interval_method!r}; this "
            f"evaluator holds {list(INTERVAL_METHODS)}"
        )
    mechanism_pending(registration)
    accounting = registration.run_accounting
    if accounting.retry.after is not FailureCategory.INFRASTRUCTURE:
        raise ValueError(
            "attempt histories are read under retries after an infrastructure failure, "
            f"the registration retries after {accounting.retry.after.value}"
        )
    arms: list[tuple[System, RunCondition, str]] = []
    unbuilt: list[Unbuilt] = []
    for cell in registration.cells:
        system = registration.system(cell.system)
        condition = registration.outage.condition(cell.condition)
        assert system is not None and condition is not None, cell
        if not registration.runs(cell):
            assert cell.group is not None
            unbuilt.append(Unbuilt(cell, WhyUnbuilt.GROUP_NOT_RUN, cell.group))
            continue
        pending = blocking(registration, cell.system)
        if pending or not isinstance(system.variant, str):
            unbuilt.append(Unbuilt(cell, WhyUnbuilt.SYSTEM_PENDING, ", ".join(pending)))
            continue
        assigned = RunCondition.all_reachable().without(*condition.unreachable)
        arms.append((System(cell.system, system.variant), assigned, cell.level))
    if not arms:
        raise ValueError(
            "no registered cell can be built: each has a system with a value pending or a "
            "group not decided as run"
        )
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
    return Projection(plan, tuple(unbuilt))


def mechanism_pending(registration: Registration) -> str | None:
    """What the registered mechanism measure is pending on, or ``None`` when it is resolved
    to a measure this evaluator holds. A resolved name it does not hold raises
    ``ValueError``, like any other registered name."""
    mechanism = registration.statistics.mechanism
    if isinstance(mechanism, Pending):
        return mechanism.awaiting
    assert isinstance(mechanism, MechanismMeasure)
    if mechanism.name not in MECHANISM_MEASURES:
        raise ValueError(
            f"no mechanism measure is registered as {mechanism.name!r}; this evaluator "
            f"holds {list(MECHANISM_MEASURES)}"
        )
    return None


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


def _require_registered_anchors(registration: Registration) -> None:
    registered = registration.stated_facts.anchor_table
    if registered != anchor_table_digest():
        raise ValueError(
            f"the registered anchor table is {registered}, this evaluator guards with "
            f"{anchor_table_digest()}"
        )


__all__ = [
    "CHECKS",
    "INTERVAL_METHODS",
    "MEASURES",
    "MECHANISM_MEASURES",
    "Projection",
    "Unbuilt",
    "WhyUnbuilt",
    "mechanism_pending",
    "preregistered",
    "registered_check",
    "registered_measures",
]
