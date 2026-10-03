"""Prefetch conformance: whether the reads a run's harness made for the frozen prefetch are the
ones the plan obliged it to make, read off the export alone.

Every system opens with the same structured reads, and the comparison between systems rests
on that being true of each run (the investigator milestone's sixth build step, ruling 5).
The harness says so by construction; this is the evaluator saying so from the trace, for
every export that decodes, a failed attempt as much as a completed one. A discrepancy is a
harness finding: the model has no way to cause it, coverage stays derived from the reads
recorded, and nothing here is filled from sealed truth. The span the plan reads is the one
on the leave the run's own opening read returned.

What is shared and what is not. The planner, the chunking and the tool contracts are
``core``'s, the same ones the harness plans with, so a fault of the planner is invisible
here and stays with the planner's own tests. What this module reconstructs by itself is
the execution: which planned calls a run was obliged to make, given what its earlier ones
returned.

The obligations, in the plan's order:

- *The opening read* of the leave the context names is always obliged.
- *The rest of the plan* exists only when a prefetch read with exactly the opening call's
  tool and arguments returned a leave of the id asked for. A leave absent, unreachable,
  malformed or of another id ends the plan at its first call.
- *A source stop.* A planned call is not obliged once an earlier planned call of the same
  source ended unreachable: the first unreachable answer stops a source for the run.
- *Termination.* No planned call is obliged after one that ended in a malformed record,
  and nothing else ends the plan. A run can fail by a defect found at a read that
  completed, after the prefetch has finished; the failure's operation is then no boundary,
  and the reads after it were obliged.

The prefetch's operations are the ones of prefetch origin, in the trace's order. Each is
matched to at most one planned call, by tool and arguments, the order of keys aside. Four
kinds of finding:

- *Missing*: an obliged call has no operation.
- *Wrongly parameterized*: an obliged call has no operation with its arguments, and a
  prefetch operation of its tool that matches no planned call exists; the two are paired in
  order, and the operation's outcome is read as the call's.
- *Extra*: a prefetch operation that is no obliged call's: a second read of the same call,
  a call against a stopped source, a call after a malformed record, anything after a leave
  that did not come back.
- *Reordered*: walking the trace, an operation whose planned call comes before one already
  met. The rule is the simple one and can name more operations than were moved: a last
  call made first marks every other. The findings are counted per run, never estimated
  from, so the minimal set is not computed.

A finding names its kind, the plan's step and the operation, never an argument or a record.

Where a prefetch operation sits among the model's own reads is not judged here; that
needs each baseline's own contract and arrives with the baselines.

A run whose record names another prefetch rule than this code's was planned by another
planner. Its conformance is not evaluated, which is a different statement from having no
finding, and no finding is manufactured from a plan it never followed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from leaveimpact.core.entities import Leave
from leaveimpact.core.enums import Source
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.prefetch import PlannedCall, calls_after_leave, opening_call, prefetch_rule
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_export_json import thawed_json
from leaveimpact.core.run_trace import (
    DefectOutcome,
    Operation,
    OperationId,
    PrefetchOrigin,
    RecordOutcome,
    UnreachableOutcome,
)
from leaveimpact.core.tools import specification_named
from leaveimpact.core.worldtime import RunContext


class PrefetchFindingKind(StrEnum):
    """How a run's prefetch reads differ from the obliged ones; a member is the wire format."""

    MISSING = "missing"
    WRONGLY_PARAMETERIZED = "wrongly_parameterized"
    REORDERED = "reordered"
    EXTRA = "extra"


@dataclass(frozen=True, slots=True)
class PrefetchFinding:
    """One discrepancy between the prefetch a run recorded and the one it was obliged to make.

    ``step`` is the plan's step, absent for an extra operation, which serves none; a step
    chunked into several calls can carry several findings. ``operation`` is absent for a
    missing call, which has none.
    """

    kind: PrefetchFindingKind
    step: int | None
    operation: OperationId | None

    def __post_init__(self) -> None:
        if (self.step is None) != (self.kind is PrefetchFindingKind.EXTRA):
            raise ValueError("every finding names its step, and only an extra operation has none")
        if (self.operation is None) != (self.kind is PrefetchFindingKind.MISSING):
            raise ValueError("every finding names its operation, and only a missing call has none")


@dataclass(frozen=True, slots=True)
class PrefetchConformance:
    """What one export shows of its prefetch.

    ``evaluated`` is false when the record names another prefetch rule than this code's: the
    run was planned by another planner and is held to no plan here. ``findings`` are the
    missing and the wrongly parameterized calls in the plan's order, then the reordered and
    then the extra operations, each in the trace's order.
    """

    evaluated: bool
    findings: tuple[PrefetchFinding, ...]

    def __post_init__(self) -> None:
        if self.findings and not self.evaluated:
            raise ValueError("a run under another rule is not evaluated and carries no finding")


def prefetch_conformance(export: RunExport) -> PrefetchConformance:
    """Whether the prefetch reads ``export`` records are the ones its plan obliged.

    Raises nothing for what the run did.
    """
    if export.record.prefetch_rule != prefetch_rule():
        return PrefetchConformance(False, ())
    made = [
        (position, operation)
        for position, operation in enumerate(export.trace.operations)
        if isinstance(operation.origin, PrefetchOrigin)
    ]
    plan = _plan(export.context, [operation for _, operation in made])
    exact = _exact_matches(plan, made)
    # A second read of a planned call is extra, never another call's wrong parameters.
    planned = {_asked(call.tool, call.arguments) for call in plan}
    spare = [
        slot
        for slot, (_, operation) in enumerate(made)
        if _asked(operation.tool, _arguments(operation)) not in planned
    ]

    findings: list[PrefetchFinding] = []
    served: list[tuple[int, int]] = []
    stopped: set[Source] = set()
    ended = False
    for index, call in enumerate(plan):
        if ended or _source_of(call) in stopped:
            continue
        slot = exact.get(index)
        if slot is None:
            slot = next((s for s in spare if made[s][1].tool == call.tool), None)
            if slot is None:
                findings.append(PrefetchFinding(PrefetchFindingKind.MISSING, call.step, None))
                continue
            spare.remove(slot)
            findings.append(
                PrefetchFinding(
                    PrefetchFindingKind.WRONGLY_PARAMETERIZED, call.step, made[slot][1].id
                )
            )
        served.append((slot, index))
        outcome = made[slot][1].outcome
        if isinstance(outcome, UnreachableOutcome):
            stopped.add(_source_of(call))
        if isinstance(outcome, DefectOutcome):
            ended = True

    latest = -1
    for slot, index in sorted(served):
        if index < latest:
            findings.append(
                PrefetchFinding(PrefetchFindingKind.REORDERED, plan[index].step, made[slot][1].id)
            )
        latest = max(latest, index)
    serving = {slot for slot, _ in served}
    findings.extend(
        PrefetchFinding(PrefetchFindingKind.EXTRA, None, operation.id)
        for slot, (_, operation) in enumerate(made)
        if slot not in serving
    )
    return PrefetchConformance(True, tuple(findings))


def _plan(context: RunContext, made: list[Operation]) -> tuple[PlannedCall, ...]:
    """The whole plan of ``context`` given what its opening read returned in ``made``: the
    opening call alone, or with the calls the returned leave's own span gives."""
    opening = opening_call(context)
    asked = _asked(opening.tool, opening.arguments)
    answer = next((op for op in made if _asked(op.tool, _arguments(op)) == asked), None)
    if answer is None or not isinstance(answer.outcome, RecordOutcome):
        return (opening,)
    record = answer.outcome.record.value
    if not isinstance(record, Leave) or record.id != context.leave_id:
        return (opening,)
    return (opening, *calls_after_leave(record, context.reference_timezone))


def _exact_matches(
    plan: tuple[PlannedCall, ...], made: list[tuple[int, Operation]]
) -> dict[int, int]:
    """For each planned call, by its index, the first operation with its tool and arguments
    that no earlier planned call took, as its place in ``made``."""
    free: dict[tuple[str, str], list[int]] = {}
    for slot, (_, operation) in enumerate(made):
        free.setdefault(_asked(operation.tool, _arguments(operation)), []).append(slot)
    matches: dict[int, int] = {}
    for index, call in enumerate(plan):
        slots = free.get(_asked(call.tool, call.arguments))
        if slots:
            matches[index] = slots.pop(0)
    return matches


def _arguments(operation: Operation) -> JsonObject:
    return cast("JsonObject", thawed_json(operation.arguments))


def _asked(tool: str, arguments: JsonObject) -> tuple[str, str]:
    """What a call asks, comparable between a planned call and a recorded one.

    Keys are sorted at every depth: an operation holds its arguments in key order and the
    planner spells them in the order it builds them, and the order of an object's keys is
    no part of what was asked.
    """
    return tool, json.dumps(arguments, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _source_of(call: PlannedCall) -> Source:
    specification = specification_named(call.tool)
    assert specification is not None, call.tool
    return specification.facts.source


__all__ = [
    "PrefetchConformance",
    "PrefetchFinding",
    "PrefetchFindingKind",
    "prefetch_conformance",
]
