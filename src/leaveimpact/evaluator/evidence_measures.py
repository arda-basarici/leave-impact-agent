"""The measures of how a run came by its answer: what its reads support, what it cited, what it
asked of its sources, and what it retrieved.

Each is a ``Measure`` like the answer-side ones, a numerator and a denominator per run, and
each states its own scope (the investigator milestone's fourth build step, ruling 6):

- *Grounding and citations* need a replayed report, so they exist for a graded and for a
  limited run whose claim set was structurally valid, and the two are measured apart and
  never pooled: a limited run has no expected answer, and its report is one written with
  a source missing. A run whose grounding was not evaluated is out of scope, which is a
  different statement from nothing grounded.
- *Source discipline* needs the trace alone and exists for every run; the join with the
  sources the answer depends on needs a context that resolves, and extra reads need a
  replay.
- *Retrieval* needs the targets, so it exists where the oracle had an answer for the
  condition the trace shows. A scenario with no target is in scope with nothing to count:
  it stays out of the denominator, and a table says how many there were.

Grounding. A claim is *reproduced*, *contradicted* or *unsupported* on its own, and those
three shares add up to one. *Local failures* are the claims that fail on their own, the
roots, where one wrong constraint is one. *Grounded end to end* asks that every premise
hold too, where the same constraint takes its assessments with it. *Strictly grounded*
also asks that no source be left unclosed anywhere beneath the claim. The word grounded,
alone, is never a measure's name.

Citations. A claim that cites nothing is neither perfect nor zero, so presence is its own
measure, and quality is over the citations made. Each axis is its own ratio: resolves and
retrieved over citations, used over the citations whose use was evaluated. A claim citing
one record twice, by two fields, is counted once here, by claim, source and target, and
the raw repeats are kept as an audit count (``repeated_citations``).

Two readings that are counts and not ratios are here as plain functions: the two-by-two
of retrieved against concluded per target, which tells a target retrieved without the
correct conclusion from one never retrieved, and the ranks at which searches returned
their targets.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from leaveimpact.core.enums import Source
from leaveimpact.core.ids import ClaimId
from leaveimpact.core.refs import EntityRef
from leaveimpact.evaluator.citations import CitationRecord
from leaveimpact.evaluator.grading import Excluded, Graded, Grounding, Limited
from leaveimpact.evaluator.grounded import grounded_end_to_end, local_failures, strictly_grounded
from leaveimpact.evaluator.measures import Counts, Measure
from leaveimpact.evaluator.replay import Standing
from leaveimpact.evaluator.retrieval import RunRetrieval
from leaveimpact.evaluator.trace_metrics import Evaluation, TraceMetrics

Replayed = type[Graded] | type[Limited]
"""The kind of run a grounding or a citation measure is over; the two are never pooled."""


# --- Grounding ---------------------------------------------------------------------------


def standing_share(standing: Standing, over: Replayed) -> Measure:
    """Claims with ``standing`` on their own, over the claims replayed."""

    def of(grounding: Grounding) -> Counts:
        claims = grounding.claims
        return sum(record.standing is standing for record in claims), len(claims)

    return Measure(_scoped(f"claims {standing.value}", over), _on_replayed(over, of))


def local_failure_share(over: Replayed) -> Measure:
    """Claims that fail on their own, not reproduced or lacking a premise, over the claims
    replayed: the roots, each counted once whatever rests on it."""

    def of(grounding: Grounding) -> Counts:
        return len(local_failures(grounding.claims)), len(grounding.claims)

    return Measure(_scoped("claims failing locally", over), _on_replayed(over, of))


def grounded_end_to_end_share(over: Replayed) -> Measure:
    """Claims reproduced with every premise beneath them reproduced, over the claims replayed."""

    def of(grounding: Grounding) -> Counts:
        return len(grounded_end_to_end(grounding.claims)), len(grounding.claims)

    return Measure(_scoped("claims grounded end to end", over), _on_replayed(over, of))


def strictly_grounded_share(over: Replayed) -> Measure:
    """Claims grounded end to end with no source left unclosed, over the claims replayed."""

    def of(grounding: Grounding) -> Counts:
        return len(strictly_grounded(grounding.claims)), len(grounding.claims)

    return Measure(_scoped("claims strictly grounded", over), _on_replayed(over, of))


# --- Citations ---------------------------------------------------------------------------


def citing_share(over: Replayed) -> Measure:
    """Claims that cite anything at all, over the claims replayed."""

    def of(grounding: Grounding) -> Counts:
        citing = {citation.claim_id for citation in grounding.citations}
        return len(citing), len(grounding.claims)

    return Measure(_scoped("claims citing", over), _on_replayed(over, of))


def resolving_share(over: Replayed) -> Measure:
    """Citations that name something the sealed world holds, over citations made."""

    def of(grounding: Grounding) -> Counts:
        made = _once_per_record(grounding.citations)
        return sum(citation.resolves for citation in made), len(made)

    return Measure(_scoped("citations that resolve", over), _on_replayed(over, of))


def retrieved_share(over: Replayed) -> Measure:
    """Citations of something the run read, over citations made."""

    def of(grounding: Grounding) -> Counts:
        made = _once_per_record(grounding.citations)
        return sum(citation.retrieved for citation in made), len(made)

    return Measure(_scoped("citations retrieved", over), _on_replayed(over, of))


def used_share(over: Replayed) -> Measure:
    """Citations the claim's proof rests on, over the citations whose use was evaluated: the
    retrieved ones of reproduced claims."""

    def of(grounding: Grounding) -> Counts:
        judged = [c for c in _once_per_record(grounding.citations) if c.used is not None]
        return sum(citation.used is True for citation in judged), len(judged)

    return Measure(_scoped("citations used", over), _on_replayed(over, of))


def citing_a_witness_share(over: Replayed) -> Measure:
    """Reproduced claims with at least one citation their proof rests on, over reproduced
    claims: the reverse direction, whether a claim that could be supported said by what."""

    def of(grounding: Grounding) -> Counts:
        reproduced = {
            record.claim_id for record in grounding.claims if record.standing is Standing.REPRODUCED
        }
        supported: set[ClaimId] = {
            citation.claim_id for citation in grounding.citations if citation.used is True
        }
        return len(reproduced & supported), len(reproduced)

    return Measure(_scoped("reproduced claims citing a witness", over), _on_replayed(over, of))


def repeated_citations(evaluation: Evaluation) -> int | None:
    """How many citations repeat a claim's citation of one record by another field: the audit
    count beside the record-level ratios. ``None`` when no grounding was evaluated."""
    grounding = _grounding_of(evaluation)
    if grounding is None:
        return None
    return len(grounding.citations) - len(_once_per_record(grounding.citations))


# --- Source discipline -------------------------------------------------------------------


def _required_attempted(metrics: TraceMetrics) -> Counts | None:
    required = metrics.required_sources
    if required is None:
        return None
    return sum(use.attempted for use in required), len(required)


def _required_answered(metrics: TraceMetrics) -> Counts | None:
    required = metrics.required_sources
    if required is None:
        return None
    return sum(use.succeeded for use in required), len(required)


def _refused(metrics: TraceMetrics) -> Counts:
    return metrics.discipline.refused_by_the_wrapper, metrics.discipline.model_operations


def _repeated(metrics: TraceMetrics) -> Counts:
    completed = sum(row.ended.completed for row in metrics.discipline.operations)
    return len(metrics.discipline.repeats), completed


def _extra(metrics: TraceMetrics) -> Counts | None:
    contribution = metrics.contribution
    if contribution is None:
        return None
    return len(contribution.extra), len(contribution.extra) + len(contribution.contributing)


# --- Retrieval ---------------------------------------------------------------------------


def _targets_retrieved(retrieval: RunRetrieval) -> Counts:
    return sum(found.retrieved for found in retrieval.targets), len(retrieval.targets)


def _required_targets_retrieved(retrieval: RunRetrieval) -> Counts:
    required = [found for found in retrieval.targets if found.target.moves_a_required_key]
    return sum(found.retrieved for found in required), len(required)


def _searches_with_a_hit(retrieval: RunRetrieval) -> Counts:
    return sum(bool(search.hits) for search in retrieval.searches), len(retrieval.searches)


def _targets_per_search(retrieval: RunRetrieval) -> Counts:
    searchable = sum(found.searchable for found in retrieval.targets)
    hits = sum(len(search.hits) for search in retrieval.searches)
    return hits, searchable * len(retrieval.searches)


def retrieved_against_concluded(evaluation: Evaluation) -> Counter[tuple[bool, bool]] | None:
    """The run's targets by (retrieved, concluded), over the targets whose conclusion was
    evaluated; ``None`` when retrieval was not evaluated."""
    retrieval = evaluation.metrics.retrieval
    if retrieval is None:
        return None
    return Counter(
        (found.retrieved, found.concluded)
        for found in retrieval.targets
        if found.concluded is not None
    )


def hit_ranks(evaluation: Evaluation) -> tuple[int, ...] | None:
    """The rank of every target a search returned, in the trace's order; ``None`` when
    retrieval was not evaluated."""
    retrieval = evaluation.metrics.retrieval
    if retrieval is None:
        return None
    return tuple(hit.rank for search in retrieval.searches for hit in search.hits)


# --- The catalog -------------------------------------------------------------------------


def _scoped(name: str, over: Replayed) -> str:
    return f"{name}: {'graded' if over is Graded else 'limited'} runs"


def _grounding_of(evaluation: Evaluation) -> Grounding | None:
    outcome = evaluation.outcome
    return None if isinstance(outcome, Excluded) else outcome.grounding


def _on_replayed(
    over: Replayed, of: Callable[[Grounding], Counts]
) -> Callable[[Evaluation], Counts | None]:
    """``of`` over the grounding of a run of the kind ``over``; any other run, and one whose
    grounding was not evaluated, is out of scope."""

    def measured(evaluation: Evaluation) -> Counts | None:
        outcome = evaluation.outcome
        if not isinstance(outcome, over) or outcome.grounding is None:
            return None
        return of(outcome.grounding)

    return measured


def _on_metrics(
    of: Callable[[TraceMetrics], Counts | None],
) -> Callable[[Evaluation], Counts | None]:
    def measured(evaluation: Evaluation) -> Counts | None:
        return of(evaluation.metrics)

    return measured


def _on_retrieval(of: Callable[[RunRetrieval], Counts]) -> Callable[[Evaluation], Counts | None]:
    def measured(evaluation: Evaluation) -> Counts | None:
        retrieval = evaluation.metrics.retrieval
        return None if retrieval is None else of(retrieval)

    return measured


def _once_per_record(citations: tuple[CitationRecord, ...]) -> list[CitationRecord]:
    """``citations`` with a claim's repeats of one record, by another field, set aside: the
    axes are the record's, so the first stands for all."""
    seen: dict[tuple[ClaimId, Source, EntityRef], CitationRecord] = {}
    for citation in citations:
        key = (citation.claim_id, citation.evidence.source, citation.evidence.target)
        seen.setdefault(key, citation)
    return list(seen.values())


_OF_A_REPLAY: tuple[Callable[[Replayed], Measure], ...] = (
    *((lambda over, standing=standing: standing_share(standing, over)) for standing in Standing),
    local_failure_share,
    grounded_end_to_end_share,
    strictly_grounded_share,
    citing_share,
    resolving_share,
    retrieved_share,
    used_share,
    citing_a_witness_share,
)

GROUNDING_AND_CITATION_MEASURES: tuple[Measure, ...] = tuple(
    measure(over) for over in (Graded, Limited) for measure in _OF_A_REPLAY
)
"""Every grounding and citation measure, over graded runs and then over limited ones."""

SOURCE_MEASURES: tuple[Measure, ...] = (
    Measure("required sources asked", _on_metrics(_required_attempted)),
    Measure("required sources answered", _on_metrics(_required_answered)),
    Measure("tool requests refused", _on_metrics(_refused)),
    Measure("completed reads repeated", _on_metrics(_repeated)),
    Measure("completed reads extra", _on_metrics(_extra)),
)

RETRIEVAL_MEASURES: tuple[Measure, ...] = (
    Measure("targets retrieved", _on_retrieval(_targets_retrieved)),
    Measure(
        "targets a required row rests on retrieved", _on_retrieval(_required_targets_retrieved)
    ),
    Measure("searches with a hit", _on_retrieval(_searches_with_a_hit)),
    Measure("searchable targets returned per search", _on_retrieval(_targets_per_search)),
)

__all__ = [
    "GROUNDING_AND_CITATION_MEASURES",
    "RETRIEVAL_MEASURES",
    "SOURCE_MEASURES",
    "Replayed",
    "citing_a_witness_share",
    "citing_share",
    "grounded_end_to_end_share",
    "hit_ranks",
    "local_failure_share",
    "repeated_citations",
    "resolving_share",
    "retrieved_against_concluded",
    "retrieved_share",
    "standing_share",
    "strictly_grounded_share",
    "used_share",
]
