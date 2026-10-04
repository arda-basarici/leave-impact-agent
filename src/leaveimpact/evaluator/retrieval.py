"""Retrieval, for one run: which of the statements its answer depended on came back in a read,
through which operations, and what each search returned of them.

The targets are the scenario's under the run's condition (``retrieval_targets``): a property
of the sealed world. This is the run's side (the investigator milestone's fourth build
step, ruling 5).

*Retrieved* is by identity: a target was retrieved when a completed operation returned a
comment or a section that carries it, inside the ticket or the document the read returns.
A carrier that came back with other text was still retrieved; that it differs is an
integrity finding, and the content gate has already kept its fact out of what the rules
were fed. Every retrieving operation is kept, in the trace's order, with who asked: a
target the prefetch returned and one the model searched for are different findings. The
unit is the target, as it is where targets are derived: a statement's carriers are
alternatives, so an operation that returned two of them retrieved the target once, and is
one row naming both.

*Searches.* Each completed search is a row: its limit, how many documents it returned, and
the targets among them with the rank of the document that carries each, the first
returned being rank one. A target is a hit once per search, at the best rank among the
returned documents that carry it: two documents stating one thing are one target found,
not two. From the rows a table reads whether a search hit any target, how
many of the targets a search can return it did return, and at what rank. Only a target a
section carries can be returned by a search, so the comment-carried ones are in the
per-target coverage and out of a search's denominator. A search that failed is not a row:
it retrieved nothing because the source did not answer, which the per-source tally says.
A recorded search that is not what the tool declares is not a row either; what it
returned still counts as retrieved, by identity, and the operation is a finding of its
own.

*Concluded.* For a graded run, each target says whether every row the oracle requires
among the keys it moves was reported with the right payload. With retrieved, that is a
two-by-two per target: retrieved and concluded, retrieved without the correct conclusion,
concluded without retrieving (a guess, or a read of something else that happened to
suffice), neither. Nothing here says a system ignored what it retrieved: a trace shows what
came back and what was reported, and cannot tell inattention from misunderstanding. A
target that moves no required row has no conclusion to check, and neither has a run that
was not graded; both are recorded as not evaluated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from leaveimpact.core.claims import ClaimType, GradingKey
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.read_coverage import supplied_by, tool_mismatches
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_trace import Operation, OperationId, RecordsOutcome
from leaveimpact.core.tools import SEARCH_LIMIT, PortMethod, specification_named
from leaveimpact.evaluator.retrieval_targets import RetrievalTarget
from leaveimpact.evaluator.rows import ClaimRows, Expectation
from leaveimpact.evaluator.source_discipline import OriginKind, origin_kind
from leaveimpact.evaluator.world_index import Statement


@dataclass(frozen=True, slots=True)
class Retrieving:
    """One completed operation that returned a target: once, however many of its carriers
    came back.

    ``carriers`` are the ones this operation returned, in the target's order. ``rank`` and
    ``limit`` are set for a search that is what the tool declares: the best position, from
    one, among the returned documents that carry the target, and the limit the search was
    called with.
    """

    operation: OperationId
    origin: OriginKind
    tool: str
    carriers: tuple[EntityRef, ...]
    rank: int | None = None
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class TargetRetrieval:
    """One target in one run: every operation that returned it, and whether the report
    concluded what it moves.

    ``concluded`` is ``None`` when it was not evaluated: the run was not graded, or the
    target moves no row a report must hold.
    """

    target: RetrievalTarget
    retrieving: tuple[Retrieving, ...]
    concluded: bool | None

    @property
    def retrieved(self) -> bool:
        """Whether any completed read of the run returned a carrier of the target."""
        return bool(self.retrieving)

    @property
    def searchable(self) -> bool:
        """Whether a search can return the target: a section of a document carries it."""
        return any(carrier.part.kind is EntityKind.CLAUSE for carrier in self.target.carriers)


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A target a search returned, and the rank of the document that carries it: the best
    rank when several of the documents returned do. A row holds a target once."""

    statement: Statement
    rank: int


@dataclass(frozen=True, slots=True)
class SearchRow:
    """One completed search: who asked, its limit, how many documents came back, and the
    targets among them in rank order."""

    operation: OperationId
    origin: OriginKind
    limit: int
    returned: int
    hits: tuple[SearchHit, ...]


@dataclass(frozen=True, slots=True)
class RunRetrieval:
    """A run's retrieval: one record per target, in the targets' order, and one row per
    completed search, in the trace's."""

    targets: tuple[TargetRetrieval, ...]
    searches: tuple[SearchRow, ...]


def retrieval_of(
    operations: Sequence[Operation],
    targets: Sequence[RetrievalTarget],
    rows: ClaimRows | None,
) -> RunRetrieval:
    """What ``operations`` returned of ``targets``, and what the report concluded of them.

    ``rows`` are the graded rows of the same run, or ``None`` for a run that was not
    graded, whose targets then carry no conclusion.
    """
    retrieving: dict[Statement, list[Retrieving]] = {target.statement: [] for target in targets}
    searches: list[SearchRow] = []
    for operation in operations:
        returned = set(supplied_by(operation).returned)
        search = _as_a_search(operation)
        if search is None and not returned:
            continue
        origin = origin_kind(operation.origin)
        hits: list[SearchHit] = []
        for target in targets:
            came_back = [carrier for carrier in target.carriers if carrier.part in returned]
            if not came_back:
                continue
            rank: int | None = None
            if search is not None:
                # Carriers are alternatives: the target was found where the first of them
                # was. A section returned inside a document the sealed world does not place
                # it in has no rank to give; that drift is an integrity finding.
                ranks = [
                    position
                    for carrier in came_back
                    if (position := search.ranks.get(carrier.record)) is not None
                ]
                if ranks:
                    rank = min(ranks)
                    hits.append(SearchHit(target.statement, rank))
            retrieving[target.statement].append(
                Retrieving(
                    operation.id,
                    origin,
                    operation.tool,
                    tuple(carrier.part for carrier in came_back),
                    rank,
                    None if search is None else search.limit,
                )
            )
        if search is not None:
            ordered = tuple(sorted(hits, key=lambda hit: hit.rank))
            searches.append(SearchRow(operation.id, origin, search.limit, search.returned, ordered))
    correct = None if rows is None else _reported_correctly(rows)
    return RunRetrieval(
        tuple(
            TargetRetrieval(
                target, tuple(retrieving[target.statement]), _concluded(target, correct)
            )
            for target in targets
        ),
        tuple(searches),
    )


@dataclass(frozen=True, slots=True)
class _Search:
    """A completed search as its tool declares it: the limit, how many documents came back,
    and each one's rank, the first return of a document standing."""

    limit: int
    returned: int
    ranks: dict[EntityRef, int]


def _as_a_search(operation: Operation) -> _Search | None:
    """``operation`` read as a completed search, or ``None`` when it is not one or is not what
    the tool declares."""
    specification = specification_named(operation.tool)
    outcome = operation.outcome
    if (
        specification is None
        or specification.method is not PortMethod.SEARCH
        or not isinstance(outcome, RecordsOutcome)
        or tool_mismatches(operation)
    ):
        return None
    limit = operation.arguments[SEARCH_LIMIT.name]
    assert isinstance(limit, int)  # the tool's own validation accepted the arguments
    ranks: dict[EntityRef, int] = {}
    for position, record in enumerate(outcome.records, start=1):
        ranks.setdefault(record.ref, position)
    return _Search(limit, len(outcome.records), ranks)


def _reported_correctly(rows: ClaimRows) -> set[tuple[ClaimType, GradingKey]]:
    """The required keys a report holds with the right payload: its true positives, by key."""
    judged: list[tuple[ClaimType, GradingKey, Expectation, object, bool | None]] = [
        *((ClaimType.IMPACT, r.key, r.expectation, r.claim_id, True) for r in rows.impacts),
        *((ClaimType.CONSTRAINT, r.key, r.expectation, r.claim_id, True) for r in rows.constraints),
        *(
            (ClaimType.CANDIDATE_ASSESSMENT, r.key, r.expectation, r.claim_id, r.payload_correct)
            for r in rows.assessments
        ),
        *(
            (ClaimType.COVERAGE_ACTION, r.key, r.expectation, r.claim_id, r.outcome_matches)
            for r in rows.actions
        ),
        *(
            (ClaimType.SOURCE_CONFLICT, r.key, r.expectation, r.claim_id, r.payload_correct)
            for r in rows.conflicts
        ),
        *(
            (ClaimType.UNKNOWN, r.key, r.expectation, r.claim_id, r.reason_matches)
            for r in rows.unknowns
        ),
    ]
    return {
        (claim_type, key)
        for claim_type, key, expectation, claim_id, payload_right in judged
        if expectation is Expectation.REQUIRED and claim_id is not None and payload_right
    }


def _concluded(
    target: RetrievalTarget, correct: set[tuple[ClaimType, GradingKey]] | None
) -> bool | None:
    """Whether every required key ``target`` moves is among the keys reported correctly."""
    required = [moved for moved in target.moves if moved.required]
    if correct is None or not required:
        return None
    return all((moved.claim_type, moved.key) in correct for moved in required)


__all__ = [
    "Retrieving",
    "RunRetrieval",
    "SearchHit",
    "SearchRow",
    "TargetRetrieval",
    "retrieval_of",
]
