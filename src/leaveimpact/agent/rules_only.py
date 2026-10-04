"""The rules-only baseline: the frozen prefetch, the structured projection of what it read, the
shared rules over it, the one report, and nothing a model decided.

The baseline is the plumbing check of the investigator milestone's measurement (the
fifth build step, rulings 2, 4 and 6): a system that reads exactly what every system reads
first, concludes from it through the rules the oracle itself runs, and reports every result
under one frozen policy. Where the sealed key needs no prose it should be right whole, and
a miss there is a plumbing fault to investigate; where the key lives in a clause it is
wrong with confidence, and that is the measured worth of what it did not read. It makes
no model call and no corpus read, and its empty constraint list is a premise its record
declares.

What a run does, in order. The prefetch over the executor; the structured projection of
the operations at the context's day, which is the whole view, since nothing sealed and
nothing stated in prose enters it. Then the preconditions:

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
- *Else conclude.* The universe is the distinct employee ids the enumeration returned, in
  the code-point order of the ids; the rest is the composer's, the path every
  rules-composed system shares, given no stated fact: the impacts the rules ground for
  the leaver over the returned leave's span, ``core``'s composing pass with no
  constraint, the report's claims.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.agent.composer import compose
from leaveimpact.agent.execution import Executor, ReadPorts, run_prefetch
from leaveimpact.core.claims import Claim
from leaveimpact.core.contradictions import self_contradictions
from leaveimpact.core.coverage import KindSlice, SliceStatus
from leaveimpact.core.entities import Leave
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import EmployeeId
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.read_condition import ObservedCondition
from leaveimpact.core.read_projection import StructuredReads, project_reads
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_ending import OperationSite
from leaveimpact.core.run_record import Failure, FailureCategory
from leaveimpact.core.run_trace import (
    DefectOutcome,
    Operation,
    OperationId,
    RecordOutcome,
    RecordsOutcome,
)
from leaveimpact.core.worldtime import RunContext


class Abstention(StrEnum):
    """Why a completed run states nothing; never exported, the trace says it to the evaluator."""

    LEAVE_NOT_RETURNED = "leave_not_returned"
    UNIVERSE_NOT_COVERED = "universe_not_covered"


@dataclass(frozen=True, slots=True)
class RulesOnlyRun:
    """How one run of the baseline ended: its operations in order, its claims (none on an
    abstention or a failure), the condition its reads show, the defect that failed it, or
    why it abstained. Exactly one of ``failure`` and ``abstention`` is set, or neither."""

    operations: tuple[Operation, ...]
    claims: tuple[Claim, ...]
    condition: ObservedCondition
    failure: Failure | None
    abstention: Abstention | None

    def __post_init__(self) -> None:
        if self.failure is not None and self.abstention is not None:
            raise ValueError("a run failed by defect did not abstain; a defect outranks abstention")
        if (self.failure is not None or self.abstention is not None) and self.claims:
            raise ValueError("a run that failed or abstained states no claim")


def investigate(
    context: RunContext,
    ports: ReadPorts,
    next_id: Callable[[], OperationId] | None = None,
) -> RulesOnlyRun:
    """The baseline's run of ``context`` over ``ports``.

    Raises nothing for what a source answered; a planned call the surface refuses, and a
    report the policy cannot state, raise as defects of the harness.
    """
    executor = Executor(ports) if next_id is None else Executor(ports, next_id)
    result = run_prefetch(executor, context)
    operations = tuple(executor.operations)
    projection = project_reads(operations, context.today)
    leave = result.leave

    failure = _defect(operations, projection, context, leave)
    if failure is not None:
        return RulesOnlyRun(operations, (), projection.condition, failure, None)
    if leave is None:
        return RulesOnlyRun(
            operations, (), projection.condition, None, Abstention.LEAVE_NOT_RETURNED
        )
    if projection.coverage.status(KindSlice(EntityKind.EMPLOYEE)) is not SliceStatus.COVERED:
        return RulesOnlyRun(
            operations, (), projection.condition, None, Abstention.UNIVERSE_NOT_COVERED
        )

    composed = compose(projection, (), context, leave, _universe(projection))
    return RulesOnlyRun(operations, composed.claims, projection.condition, None, None)


def _universe(projection: StructuredReads) -> tuple[EmployeeId, ...]:
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


def _defect(
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
            if any(record.ref == ref for record in _records_of(operation)):
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


def _records_of(operation: Operation) -> tuple[Observed[Entity], ...]:
    outcome = operation.outcome
    if isinstance(outcome, RecordOutcome):
        return (outcome.record,)
    if isinstance(outcome, RecordsOutcome):
        return outcome.records
    return ()


def _failure(operation: Operation, reason: str) -> Failure:
    return Failure(FailureCategory.DEFECT, OperationSite(operation.id), reason)


def _named(ref: EntityRef) -> str:
    return f"{ref.kind.value} {ref.id}"


__all__ = ["Abstention", "RulesOnlyRun", "investigate"]
