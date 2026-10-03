"""The rules-only run as the one artifact the evaluator reads: its record and its trace, with
the provenance the harness around it supplies.

A run knows what it did: its operations, its claims, the condition its reads show, how it
ended. It does not know the outage it was assigned, which commit it ran from, the
preregistration it ran under, the caps or the price table, because those are the harness's
knowledge and the run must not learn them from itself; nor the wall clock, which is read
only at a composition root. So the export is built from two things kept apart on purpose,
the run and a ``RunProvenance`` the harness hands over, and ``RunExport`` checks the whole
at construction.

What the record states of a rules-only run is fixed by what it is: the observed condition
is the trace's own, so the evaluator's finding against a record that disagrees with its
trace can never fire for this system; the prefetch rule is ``core``'s current one; the
retrieval is none; there is no model configuration, no pricing selection, no prompt or
tool-surface digest, no usage counter and no cost, since no model is called; the caps are
recorded all the same, as the preregistration's. A failed run records its failure at the
operation the fault was found at, which the export's own rule checks; an abstention is a
completed run with no claims and says nothing more, the trace saying it to the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.agent.rules_only import RulesOnlyRun
from leaveimpact.core.prefetch import prefetch_rule
from leaveimpact.core.run_export import EXPORT_FORMAT_VERSION, RunExport
from leaveimpact.core.run_record import (
    Caps,
    HarnessRevision,
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
from leaveimpact.core.run_trace import RunTrace
from leaveimpact.core.worldtime import RunContext


@dataclass(frozen=True, slots=True)
class RunProvenance:
    """What the harness knows about a run and the run does not: the outage it was assigned,
    the commit it ran from, the preregistration, the caps and the price table it ran
    under, and the variant name the system is recorded as."""

    outage: OutageAssignment
    harness: HarnessRevision
    preregistration_commit: str
    caps: Caps
    pricing: PricingBasis
    variant: str = "reference"


def export_rules_only_run(
    run: RulesOnlyRun,
    context: RunContext,
    provenance: RunProvenance,
    *,
    run_id: str,
    attempt: int,
    duration_ms: int,
) -> RunExport:
    """``run`` of ``context`` as the export the evaluator grades, under ``provenance``.

    ``duration_ms`` is the run's own elapsed time as the caller measured it. Raises
    ``ValueError`` only for what ``RunExport`` refuses, a defect of this harness.
    """
    record = RunRecord(
        observed_condition=run.condition.condition,
        outage=provenance.outage,
        harness=provenance.harness,
        preregistration_commit=provenance.preregistration_commit,
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
        usage=UsageAggregate((), 0, duration_ms),
        cost=None,
        pricing=provenance.pricing,
    )
    return RunExport(
        EXPORT_FORMAT_VERSION,
        run_id,
        attempt,
        context,
        record,
        RunTrace((), run.operations, run.claims),
    )


__all__ = ["RunProvenance", "export_rules_only_run"]
