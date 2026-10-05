"""The fact recheck: admission and composition run again from an export, and where the record
says otherwise.

A harness decides two things about the facts a model stated and writes both down: whether
each statement entered the run's view (the admission inside its batch entry), and what
composing then made of the admitted ones (the placements and the exclusions of the
composition). The gates, the join and the scope rules are ``core``'s, so the evaluator can
ask them again over the same export and compare (the contract step's rulings; the
evaluator group's third point).

*Admission* is rerun where it was decided: over the operations logged before the answer
that carried the statement, the outcome position of the answering call's last dispatch
being the boundary, with the lexicon of those reads. A read made later rescues nothing
here either. A finding says the record admitted what the gates refuse or the reverse, or
that both refuse and name different reasons; a refusal's detail text is not compared.

*Composition* is rerun over all the run's reads and the statements its record admitted, in
the order stated: the join, the scope rules, and the join again without what they withhold,
which is the composer's own sequence. The order stated is the order the answers were
logged in, a batch's entries in their own, and not the order the calls were asked in: two
calls that overlap can answer the other way round, and the join keeps the first of two
equal statements. A finding says the placements or the exclusions
recorded are not the ones recomputed; the two are compared as sets, an order being no part
of what was composed. It is evaluated for a claim set the rules composed in an attempt
that did not fail: a failed attempt composed nothing, and a model-authored claim set has
no composition to rerun. A record that admitted a statement whose carrier no read returned
cannot be composed again at all, which is its own finding.

The findings are the harness's and never the model's: a model cannot make a record
disagree with the functions that wrote it. Nothing is corrected here. The stages of the
mechanism measure read what the export records, because the claims were composed from the
recorded admissions, and a measure read from recomputed ones would describe another run
than the report does; a run with a finding is counted as carrying one and stays where it
is.

Needs the export alone. The registered anchor table is checked against ``core``'s where
the registration is read, so the gates run here are the registered ones.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.admission import admit, run_lexicon
from leaveimpact.core.model_calls import ModelCall, ParsedBatch
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.run_ending import ClaimAuthor
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import TerminalStatus
from leaveimpact.core.run_trace import ModelCallId
from leaveimpact.core.scoping import scope_requirements
from leaveimpact.core.stated import Admitted, Refused, StatedFact
from leaveimpact.core.stated_view import view_with_stated


class RecheckKind(StrEnum):
    """How a record can differ from the functions that wrote it; a member is the wire format."""

    ADMISSION_DIFFERS = "admission_differs"
    """The record admitted a statement the gates refuse, or refused one they admit."""
    REFUSAL_REASON_DIFFERS = "refusal_reason_differs"
    """Both refuse the statement, under different reasons."""
    PLACEMENTS_DIFFER = "placements_differ"
    EXCLUSIONS_DIFFER = "exclusions_differ"
    NOT_COMPOSABLE = "not_composable"
    """The recorded admissions cannot be composed again: one names a carrier no read of the
    run returned."""


@dataclass(frozen=True, slots=True)
class RecheckFinding:
    """One difference, by kind and where: the call, the batch and the entry for an admission,
    nothing for the three that are about the composition as a whole."""

    kind: RecheckKind
    model_call: ModelCallId | None = None
    batch: int | None = None
    entry: int | None = None


@dataclass(frozen=True, slots=True)
class FactRecheck:
    """What the rerun found: how many admissions were decided again, whether the composition
    was, and every difference, admissions first in the order the answers were logged."""

    admissions: int
    composition_evaluated: bool
    findings: tuple[RecheckFinding, ...]


def recheck_facts(export: RunExport) -> FactRecheck:
    """Admission and composition of the run ``export`` records, decided again, with every
    difference from the record. Raises nothing for what the record states."""
    trace = export.trace
    today = export.context.today
    findings: list[RecheckFinding] = []
    admitted: list[StatedFact] = []
    decided = 0
    for call in _in_answer_order(trace.model_calls):
        if call.answer is None:
            continue
        entries = [
            (batch_at, entry_at, entry)
            for batch_at, batch in enumerate(call.answer.fact_batches)
            if isinstance(batch, ParsedBatch)
            for entry_at, entry in enumerate(batch.entries)
            if isinstance(entry, Admitted | Refused)
        ]
        if not entries:
            continue
        answered_at = call.dispatches[-1].outcome_position
        assert answered_at is not None  # an answer is what a recorded response carried
        reads = project_reads(
            (
                operation
                for operation in trace.operations
                if operation.position is not None and operation.position < answered_at
            ),
            today,
        )
        lexicon = run_lexicon(reads)
        for batch_at, entry_at, recorded in entries:
            decided += 1
            if isinstance(recorded, Admitted):
                admitted.append(recorded.fact)
            again = admit(recorded.fact, reads, lexicon)
            if type(again) is not type(recorded):
                kind = RecheckKind.ADMISSION_DIFFERS
            elif (
                isinstance(again, Refused)
                and isinstance(recorded, Refused)
                and again.reason is not recorded.reason
            ):
                kind = RecheckKind.REFUSAL_REASON_DIFFERS
            else:
                continue
            findings.append(RecheckFinding(kind, call.id, batch_at, entry_at))

    composition = trace.composition
    composed = (
        composition.author is ClaimAuthor.RULES
        and export.record.status is not TerminalStatus.FAILED
    )
    if composed:
        findings.extend(_composition_findings(export, admitted))
    return FactRecheck(decided, composed, tuple(findings))


def _in_answer_order(calls: Sequence[ModelCall]) -> list[ModelCall]:
    """The answered calls of ``calls`` in the order their answers were logged.

    A trace holds its calls in the order they were first asked, and two calls that overlap
    can answer the other way round. Statements were made when an answer was logged, so
    that is their order: a composer takes them in it, and which of two equal statements
    the join keeps, with its quote, follows from it.
    """
    answered = [call for call in calls if call.answer is not None]
    # An answer is what a recorded response carried, so its position is always held.
    return sorted(answered, key=lambda call: call.dispatches[-1].outcome_position or 0)


def _composition_findings(export: RunExport, admitted: list[StatedFact]) -> list[RecheckFinding]:
    """Where the recorded composition is not the one the join and the scope rules give for
    the recorded admissions."""
    composition = export.trace.composition
    if not admitted:
        # Nothing stated composes nothing; no read needs projecting to say so.
        placements: frozenset[object] = frozenset()
        exclusions: frozenset[object] = frozenset()
    else:
        reads = project_reads(export.trace.operations, export.context.today)
        try:
            joined = view_with_stated(reads, admitted)
            scoped = scope_requirements(
                reads, (s for s in joined.included if s.predicate is PredicateName.REQUIRES)
            )
            if scoped.withheld:
                joined = view_with_stated(
                    reads, admitted, {each.fact: each.reason for each in scoped.withheld}
                )
        except ValueError:
            return [RecheckFinding(RecheckKind.NOT_COMPOSABLE)]
        placements = frozenset(scoped.placements)
        exclusions = frozenset(joined.excluded)
    found: list[RecheckFinding] = []
    if frozenset(composition.placements) != placements:
        found.append(RecheckFinding(RecheckKind.PLACEMENTS_DIFFER))
    if frozenset(composition.exclusions) != exclusions:
        found.append(RecheckFinding(RecheckKind.EXCLUSIONS_DIFFER))
    return found


__all__ = ["FactRecheck", "RecheckFinding", "RecheckKind", "recheck_facts"]
