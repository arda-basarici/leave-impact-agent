"""The rules-only run as the one artifact the evaluator reads: its record and its trace, with
the provenance the harness around it supplies.

A run knows what it did: its operations, its claims, the condition its reads show, how it
ended. It does not know the outage and the corpus level it was assigned, which commit it
ran from, the preregistration it ran under, the caps or the price table, because those are
the harness's knowledge and the run must not learn them from itself; nor the wall clock,
which is read only at a composition root; nor whether it was approved, which the run path
decides before this is called (``approval``). So the export is built from things kept
apart on purpose, the run, a ``RunProvenance`` and the approval the harness hands over,
and ``RunExport`` checks the whole at construction. The exporter projects; it decides
nothing.

What the record states of a rules-only run is fixed by what it is: the observed condition
is the trace's own, so the evaluator's finding against a record that disagrees with its
trace can never fire for this system; the prefetch rule is ``core``'s current one; the
retrieval is none; there is no model configuration, no pricing selection, no prompt or
tool-surface digest, no attribution table, no usage counter, no cost and no reservation,
since no model is called; the caps are recorded all the same, as the preregistration's.
It ran in one process, so its timing is one segment whose end was recorded, and it paused
for nothing, so no approval stamp exists. Its claims were composed by the rules under the
reporting policy. A failed run records its failure at the operation the fault was found
at, which the export's own rule checks; an abstention is a completed run with no claims
and says nothing more, the trace saying it to the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from leaveimpact.agent.report import rules_only_composition
from leaveimpact.agent.rules_only import RulesOnlyRun
from leaveimpact.core.prefetch import prefetch_rule
from leaveimpact.core.run_ending import Approval
from leaveimpact.core.run_export import EXPORT_FORMAT_VERSION, RunExport, RunTrace
from leaveimpact.core.run_record import (
    Caps,
    OutageAssignment,
    PricingBasis,
    Retrieval,
    RetrievalKind,
    RunRecord,
    System,
    SystemKind,
    TerminalStatus,
    UsageAggregate,
)
from leaveimpact.core.run_timing import HarnessRevision, Segment, Timing
from leaveimpact.core.worldtime import RunContext


@dataclass(frozen=True, slots=True)
class RunProvenance:
    """What the harness knows about a run and the run does not: the outage and the corpus
    level it was assigned, the commit it ran from, the preregistration, the caps and the
    price table it ran under, and the variant name the system is recorded as. Built from
    the registration (``registered``), no field defaulted."""

    outage: OutageAssignment
    corpus_level: str
    harness: HarnessRevision
    preregistration_commit: str
    caps: Caps
    pricing: PricingBasis
    variant: str


def export_rules_only_run(
    run: RulesOnlyRun,
    context: RunContext,
    provenance: RunProvenance,
    *,
    run_id: str,
    attempt: int,
    approval: Approval,
    admitted_at: datetime,
    terminal_at: datetime,
    duration_ms: int,
) -> RunExport:
    """``run`` of ``context`` as the export the evaluator grades, under ``provenance``.

    ``approval`` is the run path's decision (``approval.approve_rules_only_run``).
    ``admitted_at`` and ``terminal_at`` are the wall-clock instants the caller read, and
    ``duration_ms`` the run's own elapsed time on the caller's monotonic clock, recorded as
    its one segment's last offset. Raises ``ValueError`` only for what ``RunExport``
    refuses, a defect of this harness.
    """
    record = RunRecord(
        observed_condition=run.condition.condition,
        outage=provenance.outage,
        corpus_level=provenance.corpus_level,
        preregistration_commit=provenance.preregistration_commit,
        attribution_table=None,
        model_configurations=(),
        pricing_selections=(),
        prompt_digests=(),
        tool_surface_digests=(),
        system=System(SystemKind.RULES_ONLY, provenance.variant),
        retrieval=Retrieval(RetrievalKind.NONE, None),
        prefetch_rule=prefetch_rule(),
        caps=provenance.caps,
        status=TerminalStatus.FAILED if run.failure is not None else TerminalStatus.COMPLETED,
        failure=run.failure,
        abandonment=None,
        timing=Timing(
            (Segment(1, provenance.harness, duration_ms, True),),
            admitted_at,
            terminal_at,
            None,
            None,
        ),
        usage=UsageAggregate((), 0, 0),
        cost=None,
        reservation=None,
        approval=approval,
        pricing=provenance.pricing,
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        run_id,
        attempt,
        context,
        record,
        RunTrace((), run.operations, run.claims, rules_only_composition()),
    )


__all__ = ["RunProvenance", "export_rules_only_run"]
