"""Trace metrics: what a run did, measured beside its outcome, for every export that decodes.

An outcome says how a report fared: graded, limited, or excluded. What the run *did* to
get there is a second record, and it exists for more runs than a grade does. An attempt
the provider failed still made calls and cost money; a run of a mismatched context still
has reads to count. So the metrics are one record beside the outcome, never fields inside
its three types, and the entry here returns the pair (the investigator milestone's fourth
build step, ruling 5).

The record has fifteen parts, and each is evaluated only where what it needs exists. A part
that was not evaluated is ``None``, which is a different statement from a part that found
nothing:

- *Source discipline*, the *cost check*, *prefetch conformance*, the *fact recheck* and
  the *ending check* need the export alone and are always there: the reads by source,
  outcome and origin, the refused calls, the model calls by how each ended, the tool calls
  by what became of each, the repeats, the operations no conforming harness records and
  the sends an SDK retried; the usage and the cost recomputed, with every disagreement
  between them and the record; whether the prefetch reads recorded are the ones the frozen
  plan obliged, which says of itself when a run was planned under another rule and is held
  to none; the admission of every stated fact and the composition decided again, with
  where the record says otherwise; and the segments, the elapsed time and the approval's
  digest the record states of its ending, held to the export.
- *The attribution check* needs the registered attribution table: every dispatch's
  recorded reading held to it, and every call to the re-dispatch bound when that is set.
  Evaluated when a table is given and the record names its digest; a rules-only record
  names none, and a run made under another table is held to no rows.
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
- *The level check* needs the sealed world's membership for the corpus level the record
  assigns: every document the run was shown, held to it. Evaluated when the export's
  context is the sealed scenario's and the world seals a membership for that level.
- *The fact stages* need the oracle's answer under the condition the run was *assigned*,
  which fixes the statements the answer needs whatever the reads then met: how far each
  got, and what every statement the model made was. Evaluated for a system that states
  facts to the rules, a failed attempt included; not for the rules-only system, a claim
  set a model authored, or an assigned condition with no answer.
- *The account check* needs the export alone and a record that holds a reservation, which
  a rules-only record does not: every authorization replayed over the account as it stood,
  the allocations' arithmetic, the inputs against their bounds, the breaches, the
  settlement against the reservation. *The count check* needs the export alone, and the
  registration's re-dispatch policy and counting identifiers for its two registration
  parts, which it marks: every bound against the count it names, every count against its
  outcome, every group of counts against the retry rule. *The call check* needs the table
  and the policy: each call's standing under the within-call decision, and whether the
  attempt ended where its calls say. *The eligibility check* needs the retry rule, and
  the call's standing or the policy where the ending is at a dispatch or at the input
  bound: how the attempt ended and whether it permitted an attempt after it, which the
  attempt history reads.

The pair also holds what the run was *assigned*: the outage its record says was scheduled
for it, whatever its reads then met, and the corpus level. A run is graded against the
condition its trace shows, and it is counted in the arm it was assigned to, so that a
system's own behaviour never chooses its arm: one that never called the failed source ran
under no outage, and is still a run of the outage arm (ruling 6).

And it holds the contradictions among the run's own reads (``core.contradictions``),
recomputed from the trace whether or not the run failed on them: two complete reads of one
structured source that cannot both be true are evidence about the world or the execution,
never about the system, and the analysis reports them for the whole measurement. A run
that met one and did not fail by defect says so (``contradiction_not_failed``): the rule
stops a harness there, and one that went on, to a report or to a later failure of another
kind, is a finding about the harness.

Nothing a run did raises here. What can raise is the sealed world against today's rules:
the oracle disagreeing with a sealed key, or a statement whose removal the rules cannot
read. Both are refusals with no sealed content, and both are the evaluator's to fix
before any run is measured.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from leaveimpact.core.attribution import (
    AttributionTable,
    RedispatchPolicy,
    attribution_table_digest,
)
from leaveimpact.core.contradictions import Contradiction, self_contradictions
from leaveimpact.core.facts import RunCondition
from leaveimpact.core.read_condition import observed_condition
from leaveimpact.core.registration import RetryRule
from leaveimpact.core.run_ending import ClaimAuthor
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import FailureCategory, SystemKind
from leaveimpact.evaluator.account_check import AccountCheck, check_account
from leaveimpact.evaluator.attribution_check import AttributionCheck, check_attributions
from leaveimpact.evaluator.call_check import CallCheck, check_calls
from leaveimpact.evaluator.cost_check import CostCheck, check_cost
from leaveimpact.evaluator.count_check import CountCheck, check_counts
from leaveimpact.evaluator.eligibility_check import EligibilityCheck, check_eligibility
from leaveimpact.evaluator.ending_check import EndingCheck, check_ending
from leaveimpact.evaluator.fact_recheck import FactRecheck, recheck_facts
from leaveimpact.evaluator.fact_stages import FactStages, fact_stages
from leaveimpact.evaluator.grading import (
    Excluded,
    ExcludedReason,
    Graded,
    RunOutcome,
    grade_run,
)
from leaveimpact.evaluator.level_check import LevelCheck, level_check
from leaveimpact.evaluator.oracle import Answerable, oracle_for, runtime_truth
from leaveimpact.evaluator.prefetch_conformance import PrefetchConformance, prefetch_conformance
from leaveimpact.evaluator.proof_contribution import ProofContribution, proof_contribution
from leaveimpact.evaluator.retrieval import RunRetrieval, retrieval_of
from leaveimpact.evaluator.retrieval_targets import RetrievalTarget, retrieval_targets
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.source_discipline import (
    RequiredSourceUse,
    SourceDiscipline,
    source_discipline,
)
from leaveimpact.evaluator.world_index import statement_of
from leaveimpact.world.scenario import Scenario


@dataclass(frozen=True, slots=True)
class TraceMetrics:
    """What one run did; see the module for what each part needs and when it is ``None``."""

    discipline: SourceDiscipline
    cost: CostCheck
    prefetch: PrefetchConformance
    recheck: FactRecheck
    ending: EndingCheck
    required_sources: tuple[RequiredSourceUse, ...] | None
    contribution: ProofContribution | None
    retrieval: RunRetrieval | None
    level: LevelCheck | None
    facts: FactStages | None
    attribution: AttributionCheck | None
    account: AccountCheck | None
    counts: CountCheck
    calls: CallCheck | None
    eligibility: EligibilityCheck | None


@dataclass(frozen=True, slots=True)
class Evaluation:
    """One run evaluated: how its report fared, what the run did, the condition it was
    assigned, every source reachable but the ones its record says were scheduled out, the
    corpus level it was assigned, the contradictions among its own reads, and whether it
    met one of them without failing by defect."""

    outcome: RunOutcome
    metrics: TraceMetrics
    assigned: RunCondition
    level: str
    contradictions: tuple[Contradiction, ...]
    contradiction_not_failed: bool = False


def evaluate_run(
    world: SealedWorld,
    export: RunExport,
    *,
    table: AttributionTable | None = None,
    redispatch: RedispatchPolicy | None = None,
    retry: RetryRule | None = None,
    counting_identifiers: Mapping[str, str] | None = None,
) -> Evaluation:
    """The outcome of the run ``export`` records against ``world``, and its trace metrics.

    ``table``, ``redispatch``, ``retry`` and ``counting_identifiers`` (each role's registered
    counting model id, by role name) are the registration's, each ``None`` while it is
    pending or when no registration is at hand; the attribution check is evaluated only
    with a table, the call check with a table and a policy, the eligibility check with a
    retry rule, and the count check's registration parts with a policy and the identifiers.

    Raises nothing for what the run did; see ``grade_run`` and the module for what the
    sealed world can make it raise.
    """
    outcome = grade_run(world, export)
    assigned = RunCondition.all_reachable().without(*export.record.outage.scheduled_unreachable)
    contradictions = self_contradictions(export.trace.operations)
    failure = export.record.failure
    by_defect = failure is not None and failure.category is FailureCategory.DEFECT
    return Evaluation(
        outcome,
        trace_metrics(
            world,
            export,
            outcome,
            table=table,
            redispatch=redispatch,
            retry=retry,
            counting_identifiers=counting_identifiers,
        ),
        assigned,
        export.record.corpus_level,
        contradictions,
        bool(contradictions) and not by_defect,
    )


def trace_metrics(
    world: SealedWorld,
    export: RunExport,
    outcome: RunOutcome,
    *,
    table: AttributionTable | None = None,
    redispatch: RedispatchPolicy | None = None,
    retry: RetryRule | None = None,
    counting_identifiers: Mapping[str, str] | None = None,
) -> TraceMetrics:
    """What the run ``export`` records did; ``outcome`` is ``grade_run``'s for the same
    export, the keyword arguments as ``evaluate_run`` takes them."""
    trace = export.trace
    discipline = source_discipline(trace)
    cost = check_cost(export)
    prefetch = prefetch_conformance(export)
    recheck = recheck_facts(export)
    ending = check_ending(export)
    attribution = _attribution(export, table, redispatch)
    account = check_account(export)
    counts = check_counts(export, redispatch, counting_identifiers)
    calls = (
        None
        if table is None or redispatch is None or attribution is None
        else check_calls(trace.model_calls, export.record.failure, table, redispatch, attribution)
    )
    eligibility = check_eligibility(export, retry, calls, redispatch)
    scenario = world.scenario(export.context.scenario_id)
    mismatched = isinstance(outcome, Excluded) and outcome.reason is ExcludedReason.CONTEXT_MISMATCH
    if scenario is None or mismatched:
        return TraceMetrics(
            discipline,
            cost,
            prefetch,
            recheck,
            ending,
            None,
            None,
            None,
            None,
            None,
            attribution,
            account,
            counts,
            calls,
            eligibility,
        )
    grounding = None if isinstance(outcome, Excluded) else outcome.grounding
    targets = _Targets(world, scenario)
    return TraceMetrics(
        discipline=discipline,
        cost=cost,
        prefetch=prefetch,
        recheck=recheck,
        ending=ending,
        required_sources=discipline.required_source_use(scenario.key.required_sources),
        contribution=(
            None if grounding is None else proof_contribution(trace.operations, grounding.claims)
        ),
        retrieval=_retrieval(targets, export, outcome),
        level=level_check(world, export),
        facts=_facts(world, targets, export),
        attribution=attribution,
        account=account,
        counts=counts,
        calls=calls,
        eligibility=eligibility,
    )


def _attribution(
    export: RunExport, table: AttributionTable | None, redispatch: RedispatchPolicy | None
) -> AttributionCheck | None:
    """The run's dispatches read again by ``table``, or ``None`` when there is no table or
    the record does not name this one's digest."""
    if table is None or export.record.attribution_table != attribution_table_digest(table):
        return None
    return check_attributions(table, redispatch, export.trace.model_calls)


class _Targets:
    """The retrieval targets of one scenario by condition, each derived once: a run's
    retrieval is read against the condition its trace shows and its fact stages against the
    one it was assigned, and for most runs the two are one condition."""

    def __init__(self, world: SealedWorld, scenario: Scenario) -> None:
        self._world = world
        self.scenario = scenario
        self._held: dict[RunCondition, tuple[RetrievalTarget, ...] | None] = {}

    def under(self, condition: RunCondition) -> tuple[RetrievalTarget, ...] | None:
        """The targets under ``condition``, or ``None`` when it has no answer."""
        if condition not in self._held:
            oracle = oracle_for(self._world, self.scenario, condition)
            self._held[condition] = (
                retrieval_targets(self._world, oracle) if isinstance(oracle, Answerable) else None
            )
        return self._held[condition]


def _retrieval(targets: _Targets, export: RunExport, outcome: RunOutcome) -> RunRetrieval | None:
    """The run's retrieval against the targets of the condition its trace shows, or ``None``
    when that condition is mixed or has no answer."""
    observed = observed_condition(export.trace.operations)
    if observed.is_mixed:
        return None
    found = targets.under(observed.condition)
    if found is None:
        return None
    rows = outcome.rows if isinstance(outcome, Graded) else None
    return retrieval_of(export.trace.operations, found, rows)


def _facts(world: SealedWorld, targets: _Targets, export: RunExport) -> FactStages | None:
    """The run's fact stages against the statements its assigned condition's answer needs,
    or ``None`` where the measure does not apply: a system that states no fact, a claim set
    a model authored, an assigned condition with no answer."""
    record = export.record
    if (
        record.system.kind is SystemKind.RULES_ONLY
        or export.trace.composition.author is not ClaimAuthor.RULES
    ):
        return None
    assigned = RunCondition.all_reachable().without(*record.outage.scheduled_unreachable)
    found = targets.under(assigned)
    if found is None:
        return None
    needed = tuple(target for target in found if target.moves_a_required_key)
    scenario = targets.scenario
    truth = runtime_truth(world, scenario).at(scenario.spec.today, RunCondition.all_reachable())
    held = frozenset(statement_of(fact) for fact in truth.facts)
    return fact_stages(world.index, export, needed, held)


__all__ = ["Evaluation", "TraceMetrics", "evaluate_run", "trace_metrics"]
