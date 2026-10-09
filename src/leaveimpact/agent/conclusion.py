"""The preconditions every rules-composed system decides before it composes: the defect that
fails a run at its operation, the abstention that completes it with no claim, and the
candidate universe the plan rule runs over.

The rules-only baseline decided these inline (the investigator milestone's fifth build
step, ruling 4); the investigator's graph asks the same questions at three points, after
the prefetch, after each answer's reads and at the review payload, and a recovery that
reaches any of them must find the same answer (the graph step, fork 8). So they are pure
functions over the operations a run holds and its context, called by both systems, and the
baseline's graded test is the proof the move changed nothing.

- *A defect fails the run at its operation*, ahead of everything: a read that returned a
  malformed record; the opening read answered with a leave of another id; the employee
  enumeration completed without the leaver; a returned record no fact could be made from;
  two complete reads of one structured source that cannot both be true
  (``core.contradictions``: one record with two contents, a record a read by id returned
  that an enumeration or a window over its span omits, or the reverse), at the later of
  the two, or at the earlier when the later one answered "no such record", since an
  absent answer anchors no defect. Each is a source or an adapter contradicting itself,
  and a degrade would fold a defect into a legitimate unknown (DESIGN's runtime policy).
- *Abstention*, a completed run with no claims: the leave was not returned (absent, or its
  source unreachable), or the employee-kind slice was not covered, so the candidate
  universe is unknown. The plan rule is never run over a universe the run did not read.
  No claim type, status or field says why; the evaluator derives the degraded state from
  the trace, and the reason here is for tests and logs.
- *The universe* is the distinct employee ids the reads returned, in the code-point order
  of the ids.

The leave a run investigates is what its opening read returned, when that is the record
the context asked for (``execution.leave_asked_for``); the graph has no in-process prefetch
result on recovery and reads it off the first operation, so ``leave_of`` does the same for
every caller.
"""

from __future__ import annotations

from enum import StrEnum

from leaveimpact.agent.execution import leave_asked_for
from leaveimpact.core.contradictions import self_contradictions
from leaveimpact.core.coverage import KindSlice, SliceStatus
from leaveimpact.core.entities import Leave
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.read_projection import StructuredReads
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_ending import OperationSite
from leaveimpact.core.run_record import Failure, FailureCategory
from leaveimpact.core.run_trace import (
    DefectOutcome,
    Operation,
    RecordOutcome,
    RecordsOutcome,
    records_of,
)
from leaveimpact.core.worldtime import RunContext


class Abstention(StrEnum):
    """Why a completed run states nothing; never exported, the trace says it to the evaluator."""

    LEAVE_NOT_RETURNED = "leave_not_returned"
    UNIVERSE_NOT_COVERED = "universe_not_covered"


def leave_of(operations: tuple[Operation, ...], context: RunContext) -> Leave | None:
    """The leave ``context`` names, when the first operation returned exactly that record."""
    if not operations:
        return None
    return leave_asked_for(operations[0].outcome, context)


def abstention_of(projection: StructuredReads, leave: Leave | None) -> Abstention | None:
    """Why a run with these reads abstains, or ``None`` when it may conclude."""
    if leave is None:
        return Abstention.LEAVE_NOT_RETURNED
    if projection.coverage.status(KindSlice(EntityKind.EMPLOYEE)) is not SliceStatus.COVERED:
        return Abstention.UNIVERSE_NOT_COVERED
    return None


def universe_of(projection: StructuredReads) -> tuple[EmployeeId, ...]:
    """The candidate universe: the distinct employee ids the reads returned, by code point."""
    return tuple(
        sorted(
            {
                EmployeeId(record.ref.id)
                for record in projection.returned
                if record.ref.kind is EntityKind.EMPLOYEE
            }
        )
    )


def defect_of(
    operations: tuple[Operation, ...],
    projection: StructuredReads,
    context: RunContext,
    leave: Leave | None,
) -> Failure | None:
    """The first operation, in trace order, at which the run fails by defect, or ``None``."""
    found: list[tuple[int, Failure]] = []
    for index, operation in enumerate(operations):
        outcome = operation.outcome
        if isinstance(outcome, DefectOutcome):
            found.append((index, _failure(operation, outcome.reason)))
        if index == 0 and isinstance(outcome, RecordOutcome) and leave is None:
            found.append(
                (
                    index,
                    _failure(
                        operation,
                        f"the HR system answered leave {context.leave_id} with "
                        f"{outcome.record.ref.kind.value} {outcome.record.ref.id}",
                    ),
                )
            )
        if (
            leave is not None
            and operation.tool == "employees"
            and isinstance(outcome, RecordsOutcome)
            and all(record.ref.id != leave.employee_id for record in outcome.records)
        ):
            found.append(
                (
                    index,
                    _failure(
                        operation,
                        f"the employee enumeration holds no {leave.employee_id}, the leaver of "
                        f"leave {leave.id}",
                    ),
                )
            )
        for ref in projection.underivable:
            if any(record.ref == ref for record in records_of(operation.outcome)):
                found.append(
                    (index, _failure(operation, f"no fact could be made from {_named(ref)}"))
                )
                break
    placed = {operation.id: index for index, operation in enumerate(operations)}
    for contradiction in self_contradictions(operations):
        # Found once the later read is logged, whichever of the two the failure names.
        other = (
            contradiction.later
            if contradiction.site == contradiction.earlier
            else contradiction.earlier
        )
        found.append(
            (
                placed[contradiction.later],
                _failure(
                    operations[placed[contradiction.site]],
                    f"{contradiction.kind.value}: this read and {other} disagree about "
                    f"{_named(contradiction.record)}",
                ),
            )
        )
    if not found:
        return None
    return min(found, key=lambda item: item[0])[1]


def _failure(operation: Operation, reason: str) -> Failure:
    return Failure(FailureCategory.DEFECT, OperationSite(operation.id), reason)


def _named(ref: EntityRef) -> str:
    return f"{ref.kind.value} {ref.id}"


__all__ = ["Abstention", "abstention_of", "defect_of", "leave_of", "universe_of"]
