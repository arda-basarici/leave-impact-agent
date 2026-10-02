"""Measures: a claim-level ratio as the numerator and the denominator of one run, and the ones
that read a report's graded rows.

A table's ratio is a sum of numerators over a sum of denominators across scenarios, and its
interval resamples scenarios. Both need the same thing of a metric: for one evaluated run,
two counts, or the statement that the run is outside the metric's scope. That is all a
``Measure`` is. Scope is part of the definition and not of the caller: answer quality is
measured on graded runs, a limited or an excluded run having no row to count (the
investigator milestone's fourth build step, ruling 6), and a run out of scope answers
``None``, which is neither a zero numerator nor a zero denominator.

The answer-side measures are read off the rows the matching wrote, by claim type and over
all six:

- *Recall*: of the keys a report must hold, the ones it holds with the right payload. A
  held key with a wrong payload is not a true positive.
- *Precision*, two readings shown together. A reported claim is *correct* when the oracle
  expects its key, required or optional, and its payload is right; an optional claim that
  is correct counts here and not for recall. *Strict* precision is over every reported
  claim. *Type-local* precision leaves out an assessment or an action that could not be
  judged because its impact was unexpected: the wrong impact is charged once, at the
  impact, and not again for each claim hung on it. The two differ only for assessments
  and actions; for the other four types they are one number. Type-local removes that one
  cascade and no other: a wrong constraint on an expected impact still makes its
  assessments wrong, and root causes are the premise graph's to count, not this ratio's.
- *Payload accuracy*: of the reported claims whose payload the oracle could judge, the
  ones it judged right. An impact and a constraint have no payload, their key being the
  whole fact, so the measure exists for the other four types.

A structurally invalid report is in every denominator and no numerator: it was graded,
with zero credit. Unexpected claims are also counted by *standing*, so that wrong is never
one bucket: a planted distractor, a conflict that is real and beside the point and a gap
claimed where the world is complete are different findings (``unexpected_by_standing``).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.claims import ClaimType
from leaveimpact.evaluator.grading import Graded
from leaveimpact.evaluator.rows import (
    ActionStanding,
    AssessmentStanding,
    ClaimRows,
    Expectation,
)
from leaveimpact.evaluator.trace_metrics import Evaluation

Counts = tuple[int, int]
"""One run's contribution to a ratio: its numerator and its denominator."""


@dataclass(frozen=True, slots=True)
class Measure:
    """A claim-level ratio by name, and how one run contributes to it.

    ``of`` gives the run's numerator and denominator, or ``None`` when the run is outside
    the measure's scope. A run in scope with nothing to count answers ``(0, 0)``.
    """

    name: str
    of: Callable[[Evaluation], Counts | None]


@dataclass(frozen=True, slots=True)
class _Judged:
    """One row as the answer measures read it, whatever its claim type.

    ``right`` is whether the payload is right, a claim with no payload being right by its
    key; ``has_payload`` whether the oracle judged one; ``cascaded`` whether the row could
    not be judged because its impact was unexpected.
    """

    claim_type: ClaimType
    expectation: Expectation
    reported: bool
    right: bool
    has_payload: bool
    cascaded: bool
    standing: StrEnum | None

    @property
    def correct(self) -> bool:
        """A reported claim the oracle expects, required or optional, with the right payload."""
        expected = self.expectation in (Expectation.REQUIRED, Expectation.OPTIONAL)
        return self.reported and expected and self.right


def recall(claim_type: ClaimType | None = None) -> Measure:
    """Required keys held with the right payload, over required keys; of one claim type, or
    of all six."""

    def of(rows: ClaimRows) -> Counts:
        required = [row for row in _rows(rows, claim_type) if _is_required(row)]
        return sum(row.correct for row in required), len(required)

    return Measure(_named("recall", claim_type), _on_graded(of))


def strict_precision(claim_type: ClaimType | None = None) -> Measure:
    """Correct claims over every reported claim, cascades included."""

    def of(rows: ClaimRows) -> Counts:
        reported = [row for row in _rows(rows, claim_type) if row.reported]
        return sum(row.correct for row in reported), len(reported)

    return Measure(_named("strict precision", claim_type), _on_graded(of))


def type_local_precision(claim_type: ClaimType | None = None) -> Measure:
    """Correct claims over reported claims, leaving out an assessment or an action on an
    unexpected impact: the impact is where that error is charged."""

    def of(rows: ClaimRows) -> Counts:
        reported = [row for row in _rows(rows, claim_type) if row.reported and not row.cascaded]
        return sum(row.correct for row in reported), len(reported)

    return Measure(_named("type-local precision", claim_type), _on_graded(of))


def payload_accuracy(claim_type: ClaimType | None = None) -> Measure:
    """Payloads judged right over payloads the oracle could judge."""

    def of(rows: ClaimRows) -> Counts:
        judged = [row for row in _rows(rows, claim_type) if row.reported and row.has_payload]
        return sum(row.right for row in judged), len(judged)

    return Measure(_named("payload accuracy", claim_type), _on_graded(of))


def unexpected_by_standing(evaluation: Evaluation) -> Counter[tuple[ClaimType, str]] | None:
    """How many reported claims the oracle does not expect, by claim type and standing; ``None``
    for a run that was not graded."""
    if not isinstance(evaluation.outcome, Graded):
        return None
    return Counter(
        (row.claim_type, row.standing.value)
        for row in _rows(evaluation.outcome.rows, None)
        if row.standing is not None
    )


def _named(measure: str, claim_type: ClaimType | None) -> str:
    return f"{measure}: {'all claims' if claim_type is None else claim_type.value}"


def _on_graded(of: Callable[[ClaimRows], Counts]) -> Callable[[Evaluation], Counts | None]:
    """``of`` over a graded run's rows; a run that was not graded is out of scope."""

    def measured(evaluation: Evaluation) -> Counts | None:
        outcome = evaluation.outcome
        return of(outcome.rows) if isinstance(outcome, Graded) else None

    return measured


def _is_required(row: _Judged) -> bool:
    return row.expectation is Expectation.REQUIRED


def _rows(rows: ClaimRows, claim_type: ClaimType | None) -> Iterator[_Judged]:
    """The rows of ``claim_type``, or of every type, in the one shape the measures read."""
    for row in _all_rows(rows):
        if claim_type is None or row.claim_type is claim_type:
            yield row


def _all_rows(rows: ClaimRows) -> Iterator[_Judged]:
    for impact in rows.impacts:
        yield _Judged(
            ClaimType.IMPACT,
            impact.expectation,
            impact.claim_id is not None,
            True,
            False,
            False,
            impact.standing,
        )
    for constraint in rows.constraints:
        yield _Judged(
            ClaimType.CONSTRAINT,
            constraint.expectation,
            constraint.claim_id is not None,
            True,
            False,
            False,
            constraint.standing,
        )
    for assessment in rows.assessments:
        yield _Judged(
            ClaimType.CANDIDATE_ASSESSMENT,
            assessment.expectation,
            assessment.claim_id is not None,
            assessment.payload_correct is True,
            assessment.payload_correct is not None,
            assessment.standing is AssessmentStanding.ON_AN_UNEXPECTED_IMPACT,
            assessment.standing,
        )
    for action in rows.actions:
        yield _Judged(
            ClaimType.COVERAGE_ACTION,
            action.expectation,
            action.claim_id is not None,
            action.outcome_matches is True,
            action.outcome_matches is not None,
            action.standing is ActionStanding.ON_AN_UNEXPECTED_IMPACT,
            action.standing,
        )
    for conflict in rows.conflicts:
        yield _Judged(
            ClaimType.SOURCE_CONFLICT,
            conflict.expectation,
            conflict.claim_id is not None,
            conflict.payload_correct is True,
            conflict.payload_correct is not None,
            False,
            conflict.standing,
        )
    for unknown in rows.unknowns:
        yield _Judged(
            ClaimType.UNKNOWN,
            unknown.expectation,
            unknown.claim_id is not None,
            unknown.reason_matches is True,
            unknown.reason_matches is not None,
            False,
            unknown.standing,
        )


_WITH_PAYLOAD = (
    ClaimType.CANDIDATE_ASSESSMENT,
    ClaimType.COVERAGE_ACTION,
    ClaimType.SOURCE_CONFLICT,
    ClaimType.UNKNOWN,
)

ANSWER_MEASURES: tuple[Measure, ...] = (
    *(
        measure(claim_type)
        for claim_type in (None, *ClaimType)
        for measure in (recall, type_local_precision, strict_precision)
    ),
    *(payload_accuracy(claim_type) for claim_type in (None, *_WITH_PAYLOAD)),
)
"""Every answer-side measure: recall and the two precisions over all claims and per claim
type, and payload accuracy over all and per type that has a payload."""


__all__ = [
    "ANSWER_MEASURES",
    "Counts",
    "Measure",
    "payload_accuracy",
    "recall",
    "strict_precision",
    "type_local_precision",
    "unexpected_by_standing",
]
