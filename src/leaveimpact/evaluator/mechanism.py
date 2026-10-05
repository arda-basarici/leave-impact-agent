"""The mechanism measure as tables read it: the four stages as measures, and the supporting
detail tallied per cell.

``fact_stages`` says, for one run, how far each needed statement got and what each emission
was. This module turns that into what a table holds (the contract step's ruling on the
mechanism measure; the evaluator group's fourth and fifth points):

- *A stage is a measure*: per run, the needed statements that reached it over the needed
  statements. A run the measure does not apply to is out of scope; a scenario whose answer
  needs no prose statement is in scope with nothing to count, so it enters no ratio and is
  never read as perfect, and an estimate says how many such scenarios there were. The four
  share one denominator by construction, and a stage can be cut by the predicate of the
  needed statement.
- *The detail* is counts with no interval: every emission by its class, as emissions and as
  distinct statements, a statement stated ten times being ten of the first and one of the
  second; the recorded refusals by reason; the recorded exclusions by reason; the
  placements against the sealed scope. Omissions need no count of their own: they are the
  statements returned and not emitted, the first stage less the second.

The measure is registered under one name, ``needed_prose_facts``, with its stage names.
Where it is reported and contrasted is the analysis's reading of that name: per arm at the
whole and at each tier, by predicate at the whole, and contrasted on the pairs the
registration already compares, never on a pair chosen here.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.stated import STATED_PREDICATES, FactRefusal
from leaveimpact.core.stated_view import Exclusion
from leaveimpact.evaluator.cells import Cell, Stratum
from leaveimpact.evaluator.fact_stages import STAGES, EmissionClass, PlacementOutcome
from leaveimpact.evaluator.measures import Counts, Measure
from leaveimpact.evaluator.trace_metrics import Evaluation

NEEDED_PROSE_FACTS = "needed_prose_facts"
"""The mechanism measure's registered name."""


def stage_measure(stage: str, of_predicate: PredicateName | None = None) -> Measure:
    """The needed statements that reached ``stage`` over the needed statements, of one
    predicate or of all.

    >>> stage_measure("admitted").name
    'needed prose facts admitted: all predicates'
    """
    position = STAGES.index(stage)

    def of(evaluation: Evaluation) -> Counts | None:
        facts = evaluation.metrics.facts
        if facts is None:
            return None
        targets = [
            target
            for target in facts.targets
            if of_predicate is None or target.predicate is of_predicate
        ]
        return sum(target.reached[position] for target in targets), len(targets)

    scope = "all predicates" if of_predicate is None else of_predicate.value
    return Measure(f"needed prose facts {stage}: {scope}", of)


STAGE_MEASURES: tuple[Measure, ...] = tuple(stage_measure(stage) for stage in STAGES)
"""The four stages over every needed statement, in the funnel's order."""

STAGE_MEASURES_BY_PREDICATE: tuple[Measure, ...] = tuple(
    stage_measure(stage, name) for name in STATED_PREDICATES for stage in STAGES
)
"""The four stages cut by the predicate of the needed statement, a predicate's four
together, over the predicates a model may state."""


@dataclass(frozen=True, slots=True)
class FactDetail:
    """What the counted runs of a cell stated, beside the stages.

    ``runs`` are the counted runs the measure applies to. Each tally holds the values that
    occur, in name order. ``emissions`` counts every entry of every batch by its class and
    ``distinct`` each run's distinct statements by class, a statement being its subject,
    predicate, value and carrier. ``refused`` are the recorded refusals by reason, per
    emission; ``excluded`` the recorded exclusions by reason; ``placements`` the recorded
    placements against the sealed scope.
    """

    stratum: Stratum
    runs: int
    emissions: tuple[tuple[EmissionClass, int], ...]
    distinct: tuple[tuple[EmissionClass, int], ...]
    refused: tuple[tuple[FactRefusal, int], ...]
    excluded: tuple[tuple[Exclusion, int], ...]
    placements: tuple[tuple[PlacementOutcome, int], ...]


def fact_detail(cell: Cell) -> FactDetail:
    """The supporting detail of ``cell``'s counted runs."""
    held = [
        facts
        for runs in cell.scenarios
        for run in runs.counted
        if (facts := run.metrics.facts) is not None
    ]
    rows = [(position, row) for position, facts in enumerate(held) for row in facts.emissions]
    stated_once = {
        (position, row.emission_class, row.fact.statement, row.fact.carrier)
        for position, row in rows
        if row.fact is not None
    }
    # A malformed entry has no statement to be the same as another's: each is its own.
    malformed = sum(row.fact is None for _, row in rows)
    distinct = Counter(emission_class for _, emission_class, _, _ in stated_once)
    if malformed:
        distinct[EmissionClass.MALFORMED] += malformed
    return FactDetail(
        cell.stratum,
        len(held),
        _tally(row.emission_class for _, row in rows),
        _tally(distinct.elements()),
        _tally(row.refusal for _, row in rows if row.refusal is not None),
        _tally(reason for facts in held for reason in facts.exclusions),
        _tally(outcome for facts in held for outcome in facts.placements),
    )


def _tally[T: StrEnum](values: Iterable[T]) -> tuple[tuple[T, int], ...]:
    """How many of each value, the values that occur, in name order."""
    return tuple(sorted(Counter(values).items(), key=lambda item: item[0].value))


__all__ = [
    "NEEDED_PROSE_FACTS",
    "STAGE_MEASURES",
    "STAGE_MEASURES_BY_PREDICATE",
    "FactDetail",
    "fact_detail",
    "stage_measure",
]
