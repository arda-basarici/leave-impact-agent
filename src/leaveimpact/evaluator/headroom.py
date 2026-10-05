"""Headroom: at one place, how many scenarios the reference system does not already pass.

Under an outage the oracle expects less, and a system that states little is right more
often, so a comparison there can be between two systems that are both already correct on
most scenarios. The registration names a procedure that characterizes this (the contract
step's ruling on correct-whole under an outage): a reference system, a check and a reading.
Per place where the reference runs under an answer-quality condition, this module counts
the scenarios the reference does not pass, of how many.

It is a diagnostic reported beside the cells. It enters no estimate, it selects no scenario
and no cell, and what it returns names none: two counts, so that it can be read before a
measurement without disclosing which scenarios are the hard ones. It is not the most a
system could improve by: a system can also be wrong where the reference is right.

A scenario passes when every one of its trials does. With one run a scenario that is the
run; with repeats a reference that passes some of them has not passed the scenario. A
scenario with no trial under the reading is left out of both counts. Where the reference's
arm has no counted run at all there is nothing to characterize, and the result says so
instead of reporting every scenario as headroom; an arm that could not be built is the
analysis's to say, with what the registration holds pending.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.evaluator.cells import Cell, Preregistered
from leaveimpact.evaluator.tables import Check, Reading, scenario_passes


@dataclass(frozen=True, slots=True)
class Headroom:
    """The headroom at one place, a condition at a corpus level: ``not_passed`` of
    ``scenarios`` are not already passed by the reference, or ``unavailable`` says why
    neither count exists. Exactly one side is set."""

    condition: str
    level: str
    scenarios: int | None
    not_passed: int | None
    unavailable: str | None


def headroom_at(
    condition: str, level: str, reference: Cell, check: Check, reading: Reading, plan: Preregistered
) -> Headroom:
    """The headroom under ``condition`` at ``level``, from ``reference``, the whole of the
    reference system's arm there."""
    if not any(runs.counted for runs in reference.scenarios):
        return Headroom(condition, level, None, None, "the reference's arm has no counted run")
    passes = scenario_passes(reference, check, reading, plan)
    tried = [(passed, of) for _, passed, of in passes if of]
    return Headroom(condition, level, len(tried), sum(passed < of for passed, of in tried), None)


__all__ = ["Headroom", "headroom_at"]
