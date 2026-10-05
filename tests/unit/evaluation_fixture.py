"""Evaluated runs for the tests of what is aggregated from them: a scenario of the throwaway
golden world, run by a named system under an assigned condition, with the reads and the report
a test gives it.

Test infrastructure. An evaluation is the whole grading of one export, seconds for a world's
worth, and the aggregation's tests need many that differ only in who ran what, when and how
often. ``evaluated`` builds one through the real entry, and remembers the ones a truthful
system makes over a full read, the common case; ``relabelled`` gives an evaluation another
run identity, system, corpus level or arm without grading it again, which is what a
repeat, a second system with the same behaviour or the same run at another level is.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from leaveimpact.core import (
    Claim,
    Operation,
    OutageAssignment,
    RunCondition,
    Source,
    System,
    SystemKind,
)
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world import Scenario
from tests.unit.export_fixture import DIGEST, run_export
from tests.unit.reads_fixture import reads_of_everything
from tests.unit.report_fixture import truthful_report

NORMAL = RunCondition.all_reachable()
REFERENCE = System(SystemKind.RULES_ONLY, "reference")
BASE, PADDED = "base", "padded"

_TRUTHFUL: dict[tuple[str, tuple[Source, ...], tuple[Source, ...]], Evaluation] = {}


def truthful(world: SealedWorld, scenario: Scenario, condition: RunCondition) -> tuple[Claim, ...]:
    """The oracle's own answer for ``scenario`` under ``condition``, as a report."""
    oracle = oracle_for(world, scenario, condition)
    assert isinstance(oracle, Answerable)
    return truthful_report(oracle)


def evaluated(
    world: SealedWorld,
    scenario: Scenario,
    *,
    down: tuple[Source, ...] = (),
    assigned: tuple[Source, ...] | None = None,
    claims: Sequence[Claim] | None = None,
    operations: Sequence[Operation] | None = None,
) -> Evaluation:
    """The evaluation of a reference run of ``scenario`` with the sources in ``down``
    unreachable for the whole run.

    ``assigned`` is the outage its record says was scheduled, the same sources unless
    given. The report is the truthful one for the condition met unless ``claims`` is; the
    run read everything it could unless ``operations`` says what it read.
    """
    scheduled = down if assigned is None else assigned
    key = (scenario.spec.id, down, scheduled)
    remembered = claims is None and operations is None
    if remembered and key in _TRUTHFUL:
        return _TRUTHFUL[key]
    condition = NORMAL.without(*down)
    export = run_export(
        world,
        scenario,
        truthful(world, scenario, condition) if claims is None else claims,
        operations=(
            reads_of_everything(world, scenario, *down) if operations is None else operations
        ),
        recorded=condition,
    )
    outage = OutageAssignment(frozenset(scheduled), DIGEST)
    evaluation = evaluate_run(world, replace(export, record=replace(export.record, outage=outage)))
    if remembered:
        _TRUTHFUL[key] = evaluation
    return evaluation


def relabelled(
    evaluation: Evaluation,
    *,
    run_id: str | None = None,
    attempt: int | None = None,
    system: System | None = None,
    level: str | None = None,
) -> Evaluation:
    """``evaluation`` as another run, attempt or system would have produced it, or the same
    one at another corpus level: the same outcome and metrics under another identity."""
    header = evaluation.outcome.header
    header = replace(
        header,
        run_id=header.run_id if run_id is None else run_id,
        attempt=header.attempt if attempt is None else attempt,
        system=header.system if system is None else system,
    )
    return replace(
        evaluation,
        outcome=replace(evaluation.outcome, header=header),
        level=evaluation.level if level is None else level,
    )


__all__ = ["BASE", "NORMAL", "PADDED", "REFERENCE", "evaluated", "relabelled", "truthful"]
