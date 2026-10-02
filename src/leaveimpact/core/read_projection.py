"""The structured projection of a run's reads: what the rules can be fed from the records the
reads returned, and nothing those records do not hold.

Two parties build a fact view from a trace's reads and may not import each other: the
evaluator, replaying what a run's reads support, and a harness whose deterministic rules
conclude from its own reads. Part of that view needs no sealed world: which records came
back, which of them can be used, the facts and gaps derivation makes of each, what the
reads covered, and the condition they show. That part is this one function, so the view the
graded concludes from and the view the grader replays over cannot differ in it (the
investigator milestone's fifth build step, the build design's second call).

What the evaluator layers over it needs the sealed world and stays in the evaluator: the
comparison of every returned record with the sealed one, the sealed facts a returned
comment or section carries, and the withdrawals that comparison calls for. The view built
here holds no fact that only prose states. A harness that reads no prose concludes from
exactly this view; the two views differ by the evaluator's overlay and by nothing else.

How the projection is made, from the completed reads:

- *Each record as first returned*, in the order the reads returned them.
- *A usable record* is one the coverage mapping did not withdraw. Two completed reads that
  returned one record with different contents, or one that returned it and one that found
  none by its id, leave nothing to conclude from it, and it derives nothing here.
- *Structured facts and gaps* derive from each usable record exactly as returned, dated to
  the run's day, identical ones stated once.
- *A record no fact can be made from* is named in ``underivable`` and withdrawn from the
  coverage here, not left to each consumer. A decodable export can hold one (a blank
  location), and a record left covered with no fact would read as a negative to every
  rule that asks about it. What to make of it is the consumer's: the evaluator reports a
  finding and goes on, a harness fails its run by defect.
- *The condition* is derived from the same operations.

``project_reads`` raises nothing for what a run did or was shown. The fact base cannot
refuse what ``view`` builds: identical facts are stated once, a record contributes once,
and a gap and a value never come from one record's field; a refusal there would be a
defect of this module and should surface as one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from leaveimpact.core.derivation import Derived, derive
from leaveimpact.core.facts import Fact, FactBase, FactView, Gap
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.read_condition import ObservedCondition, observed_condition
from leaveimpact.core.read_coverage import ReadCoverage, coverage_from_reads, supplied_by
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_trace import Operation


@dataclass(frozen=True, slots=True)
class StructuredReads:
    """What a run's completed reads give the rules, with nothing sealed.

    ``returned`` holds each record as first returned, in that order, the withdrawn ones
    included. ``reads`` is the coverage mapping's own answer over the operations, where a
    record returned two ways is withdrawn. ``derived`` are the facts and gaps of the
    usable records, each once, in the order derived. ``underivable`` names the usable
    records derivation refused, in the order returned. ``condition`` is what the same
    operations show of their sources.
    """

    today: date
    returned: tuple[Observed[Entity], ...]
    reads: ReadCoverage
    derived: tuple[Derived, ...]
    underivable: tuple[EntityRef, ...]
    condition: ObservedCondition

    @property
    def facts(self) -> tuple[Fact, ...]:
        """The structured facts, in the order derived."""
        return tuple(item for item in self.derived if isinstance(item, Fact))

    @property
    def gaps(self) -> tuple[Gap, ...]:
        """The gaps, in the order derived."""
        return tuple(item for item in self.derived if isinstance(item, Gap))

    @property
    def coverage(self) -> ReadCoverage:
        """What the reads observed whole, the underivable records withdrawn as well."""
        return self.reads.excluding(self.underivable)

    def view(self) -> FactView:
        """The view the rules are asked over when nothing but the structured records is read:
        these facts and gaps, under this condition and this coverage."""
        return FactBase(self.facts, self.gaps).observed(
            self.today, self.condition.condition, self.coverage
        )


def project_reads(operations: Iterable[Operation], today: date) -> StructuredReads:
    """The structured projection of ``operations``, each fact dated to ``today``.

    >>> empty = project_reads((), date(2026, 3, 2))
    >>> (empty.returned, empty.derived, empty.underivable)
    ((), (), ())
    >>> empty.view().facts
    ()
    """
    made = tuple(operations)
    reads = coverage_from_reads(made)
    first: dict[EntityRef, Observed[Entity]] = {}
    for operation in made:
        for record in supplied_by(operation).records:
            first.setdefault(record.ref, record)
    derived: dict[Derived, None] = {}
    underivable: list[EntityRef] = []
    for ref, record in first.items():
        if ref in reads.unobserved:
            continue
        try:
            derived.update(dict.fromkeys(derive(record, today)))
        except ValueError:
            underivable.append(ref)
    return StructuredReads(
        today=today,
        returned=tuple(first.values()),
        reads=reads,
        derived=tuple(derived),
        underivable=tuple(underivable),
        condition=observed_condition(made),
    )


__all__ = ["StructuredReads", "project_reads"]
