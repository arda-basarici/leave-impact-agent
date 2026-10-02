"""The reading pass: what the rules conclude about each impact in one view.

Two rules are always asked together of an impact: whether the leaver holds it, and how
every candidate stands for it. ``read_impacts`` is that composition and nothing more, and
it is here in ``core`` because every party that needs it must get the same one. The
benchmark seals a key from it and re-derives every key through it, the evaluator derives
what it expects of a run from it, and a harness whose deterministic rules report over its
own reads needs it too and may not import the benchmark. A composition written again in
any of them would be a second reading of the rules, free to drift from the first.

``core`` says what the rules conclude. Turning a reading into a benchmark's expectations,
the conflicts and the unknowns a sealed key holds, is the benchmark's and stays there.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from leaveimpact.core.claims import ConstraintKey, ImpactKey
from leaveimpact.core.facts import FactView
from leaveimpact.core.grounding import Grounding, ground_impact
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.viability import Assessment, assess_impact
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


__all__ = ["Reading", "read_impacts"]
