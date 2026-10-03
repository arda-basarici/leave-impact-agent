"""Trace metrics: what a run did, measured beside its outcome, for every export that decodes.

An outcome says how a report fared: graded, limited, or excluded. What the run *did* to
get there is a second record, and it exists for more runs than a grade does. An attempt
the provider failed still made calls and cost money; a run of a mismatched context still
has reads to count. So the metrics are one record beside the outcome, never fields inside
its three types, and the entry here returns the pair (the investigator milestone's fourth
build step, ruling 5).

The record has six parts, and each is evaluated only where what it needs exists. A part
that was not evaluated is ``None``, which is a different statement from a part that found
nothing:

- *Source discipline*, the *cost check* and *prefetch conformance* need the export alone
  and are always there: the reads by source, outcome and origin, the refused calls, the
  model calls by how each ended, the repeats, the operations no conforming harness
  records; the usage and the cost recomputed, with every disagreement between them and
  the record; and whether the prefetch reads recorded are the ones the frozen plan
  obliged, which says of itself when a run was planned under another rule and is held to
  none.
- *Required sources* need the sealed key: for each source the scenario's answer depends
  on, whether the run asked it and whether it answered. Evaluated when the export's
  context is the sealed scenario's; a run of another context keeps its raw tallies and
  is compared with nothing.
- *Proof contribution* needs the replay: which completed reads supplied something a
  conclusion about the report rests on, and which were extra. Evaluated where grounding
  was, a graded or a limited run with a claim set that can be replayed. For a failed
  attempt it is not evaluated, since with no report replayed every read would count as
  extra and say nothing.
- *Retrieval* needs the oracle's answer under the condition the trace shows: the targets
  there, which of them came back, the search rows. Evaluated whenever that answer
  exists, a failed attempt included, since what a run retrieved before it failed is still
  what it retrieved; not evaluated for a mixed condition or one with no answer. Whether
  the report concluded what a target moves is filled in for a graded run only.

The pair also holds the condition the run was *assigned*: the outage its record says was
scheduled for it, whatever its reads then met. A run is graded against the condition its
trace shows, and it is counted in the arm it was assigned to, so that a system's own
behaviour never chooses its arm: one that never called the failed source ran under no
outage, and is still a run of the outage arm (ruling 6).

Nothing a run did raises here. What can raise is the sealed world against today's rules:
the oracle disagreeing with a sealed key, or a statement whose removal the rules cannot
read. Both are refusals with no sealed content, and both are the evaluator's to fix
before any run is measured.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.facts import RunCondition
from leaveimpact.core.read_condition import observed_condition
from leaveimpact.core.run_export import RunExport
from leaveimpact.evaluator.cost_check import CostCheck, check_cost
from leaveimpact.evaluator.grading import (
    Excluded,
    ExcludedReason,
    Graded,
    RunOutcome,
    grade_run,
)
from leaveimpact.evaluator.oracle import Answerable, oracle_for
from leaveimpact.evaluator.prefetch_conformance import PrefetchConformance, prefetch_conformance
from leaveimpact.evaluator.proof_contribution import ProofContribution, proof_contribution
from leaveimpact.evaluator.retrieval import RunRetrieval, retrieval_of
from leaveimpact.evaluator.retrieval_targets import retrieval_targets
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.source_discipline import (
    RequiredSourceUse,
    SourceDiscipline,
    source_discipline,
)
from leaveimpact.world.scenario import Scenario


@dataclass(frozen=True, slots=True)
class TraceMetrics:
    """What one run did; see the module for what each part needs and when it is ``None``."""

    discipline: SourceDiscipline
    cost: CostCheck
    prefetch: PrefetchConformance
    required_sources: tuple[RequiredSourceUse, ...] | None
    contribution: ProofContribution | None
    retrieval: RunRetrieval | None


@dataclass(frozen=True, slots=True)
class Evaluation:
    """One run evaluated: how its report fared, what the run did, and the condition it was
    assigned, every source reachable but the ones its record says were scheduled out."""

    outcome: RunOutcome
    metrics: TraceMetrics
    assigned: RunCondition


def evaluate_run(world: SealedWorld, export: RunExport) -> Evaluation:
    """The outcome of the run ``export`` records against ``world``, and its trace metrics.

    Raises nothing for what the run did; see ``grade_run`` and the module for what the
    sealed world can make it raise.
    """
    outcome = grade_run(world, export)
    assigned = RunCondition.all_reachable().without(*export.record.outage.scheduled_unreachable)
    return Evaluation(outcome, trace_metrics(world, export, outcome), assigned)


def trace_metrics(world: SealedWorld, export: RunExport, outcome: RunOutcome) -> TraceMetrics:
    """What the run ``export`` records did; ``outcome`` is ``grade_run``'s for the same export."""
    trace = export.trace
    discipline = source_discipline(trace)
    cost = check_cost(export)
    prefetch = prefetch_conformance(export)
    scenario = world.scenario(export.context.scenario_id)
    mismatched = isinstance(outcome, Excluded) and outcome.reason is ExcludedReason.CONTEXT_MISMATCH
    if scenario is None or mismatched:
        return TraceMetrics(discipline, cost, prefetch, None, None, None)
    grounding = None if isinstance(outcome, Excluded) else outcome.grounding
    return TraceMetrics(
        discipline=discipline,
        cost=cost,
        prefetch=prefetch,
        required_sources=discipline.required_source_use(scenario.key.required_sources),
        contribution=(
            None if grounding is None else proof_contribution(trace.operations, grounding.claims)
        ),
        retrieval=_retrieval(world, scenario, export, outcome),
    )


def _retrieval(
    world: SealedWorld, scenario: Scenario, export: RunExport, outcome: RunOutcome
) -> RunRetrieval | None:
    """The run's retrieval against the targets of the condition its trace shows, or ``None``
    when that condition is mixed or has no answer."""
    observed = observed_condition(export.trace.operations)
    if observed.is_mixed:
        return None
    oracle = oracle_for(world, scenario, observed.condition)
    if not isinstance(oracle, Answerable):
        return None
    rows = outcome.rows if isinstance(outcome, Graded) else None
    return retrieval_of(export.trace.operations, retrieval_targets(world, oracle), rows)


__all__ = ["Evaluation", "TraceMetrics", "evaluate_run", "trace_metrics"]
