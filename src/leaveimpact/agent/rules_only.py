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
nothing stated in prose enters it. Then the preconditions, the ``conclusion`` module's
since the graph step, which asks them at three points of the investigator's run: a defect
fails the run at its operation, ahead of everything; an abstention completes it with no
claim, the leave not returned or the universe not covered; else the run concludes. The
universe is the distinct employee ids the enumeration returned, in the code-point order of
the ids; the rest is the composer's, the path every rules-composed system shares, given no
stated fact: the impacts the rules ground for the leaver over the returned leave's span,
``core``'s composing pass with no constraint, the report's claims.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from leaveimpact.agent.composer import compose
from leaveimpact.agent.conclusion import Abstention, abstention_of, defect_of, universe_of
from leaveimpact.agent.execution import Executor, ReadPorts, run_prefetch
from leaveimpact.core.claims import Claim
from leaveimpact.core.read_condition import ObservedCondition
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.run_record import Failure
from leaveimpact.core.run_trace import Operation, OperationId
from leaveimpact.core.worldtime import RunContext


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

    failure = defect_of(operations, projection, context, leave)
    if failure is not None:
        return RulesOnlyRun(operations, (), projection.condition, failure, None)
    abstention = abstention_of(projection, leave)
    if abstention is not None:
        return RulesOnlyRun(operations, (), projection.condition, None, abstention)
    assert leave is not None
    composed = compose(projection, (), context, leave, universe_of(projection))
    return RulesOnlyRun(operations, composed.claims, projection.condition, None, None)


__all__ = ["Abstention", "RulesOnlyRun", "investigate"]
