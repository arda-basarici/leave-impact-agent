"""The reading pass: what the rules conclude about each impact in one view.

Two rules are always asked together of an impact: whether the leaver holds it, and how
every candidate stands for it. ``read_impacts`` is that composition and nothing more, and
it is here in ``core`` because every party that needs it must get the same one. The
benchmark seals a key from it and re-derives every key through it, the evaluator derives
what it expects of a run from it, and a harness whose deterministic rules report over its
own reads needs it too and may not import the benchmark. A composition written again in
any of them would be a second reading of the rules, free to drift from the first.

``conclude_impacts`` goes one step further for the two parties that need an answer per
impact and not only a reading: the need behind the impact, the requirements of the
constraints that apply to it, the number of people they ask for, and the coverage outcome
the plan rule gives over every candidate's verdict. The oracle lays its probe set and its
constraint scope over that; the rules-only baseline reports it as it is.

``core`` says what the rules conclude. Turning a reading into a benchmark's expectations,
the conflicts and the unknowns a sealed key holds, is the benchmark's and stays there.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from leaveimpact.core.claims import ConstraintKey, CoverageActionKind, ImpactKey
from leaveimpact.core.closure import Unresolved
from leaveimpact.core.facts import FactView
from leaveimpact.core.grounding import Grounding, ground_impact
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.plans import expected_action, required_count
from leaveimpact.core.viability import (
    Assessment,
    Need,
    ResolvedRequirement,
    applicable_requirements,
    assess_impact,
    need_of,
)
from leaveimpact.core.worldtime import DateSpan


@dataclass(frozen=True, slots=True)
class Reading:
    """What the rules conclude about one impact in one view: whether the leaver holds it, and
    every candidate's assessment for it, in the candidates' order."""

    impact: ImpactKey
    grounding: Grounding
    assessments: tuple[Assessment, ...]


def read_impacts(
    view: FactView,
    impacts: Sequence[ImpactKey],
    constraints: Sequence[ConstraintKey],
    leaver: EmployeeId,
    leave_span: DateSpan,
    reference_timezone: str,
    universe: Sequence[EmployeeId],
) -> tuple[Reading, ...]:
    """Each impact's grounding and its assessments over ``universe``, in ``impacts``' order.

    The one pass every derivation of what the rules conclude shares, so no consumer reads
    the rules a second way: construction seals a key from it, world assembly re-derives
    every key through it, the required-sources derivation asks it under each outage, and
    the evaluator derives what it expects of a run from it. It takes impact keys and not
    the key's expected impacts because under an outage the impacts are the ones the rules
    ground there, which no key lists.
    """
    return tuple(
        Reading(
            impact,
            ground_impact(view, impact, leaver, leave_span, reference_timezone),
            assess_impact(view, impact, universe, constraints, leave_span, reference_timezone),
        )
        for impact in impacts
    )


@dataclass(frozen=True, slots=True)
class ImpactConclusion:
    """What the rules conclude about one impact, whole: the reading, the need behind the
    impact or the fact that stops it from being read, the readable requirements of the
    constraints that apply, how many people they ask for (one when none does), and the
    coverage outcome over every candidate's verdict."""

    reading: Reading
    need: Need | Unresolved
    requirements: tuple[ResolvedRequirement, ...]
    required: int
    outcome: CoverageActionKind

    @property
    def impact(self) -> ImpactKey:
        return self.reading.impact


def conclude_impacts(
    view: FactView,
    impacts: Sequence[ImpactKey],
    constraints: Sequence[ConstraintKey],
    leaver: EmployeeId,
    leave_span: DateSpan,
    reference_timezone: str,
    universe: Sequence[EmployeeId],
) -> tuple[ImpactConclusion, ...]:
    """Each impact's conclusion over ``universe`` under ``constraints``, in ``impacts``' order.

    The reading pass, then per impact the need, the requirements the applicable
    constraints resolve to (an unresolved one is already an unknown of the assessments
    and counts for nothing here), the required count and the plan rule's outcome. One
    composition for the oracle and for a system that reports the rules' results.
    """
    conclusions: list[ImpactConclusion] = []
    for reading in read_impacts(
        view, impacts, constraints, leaver, leave_span, reference_timezone, universe
    ):
        need = need_of(view, reading.impact, leave_span, reference_timezone)
        requirements = (
            ()
            if isinstance(need, Unresolved)
            else tuple(
                requirement
                for requirement in applicable_requirements(view, need, constraints)
                if isinstance(requirement, ResolvedRequirement)
            )
        )
        required = required_count(requirements)
        outcome = expected_action((a.verdict for a in reading.assessments), required)
        conclusions.append(ImpactConclusion(reading, need, requirements, required, outcome))
    return tuple(conclusions)


__all__ = ["ImpactConclusion", "Reading", "conclude_impacts", "read_impacts"]
