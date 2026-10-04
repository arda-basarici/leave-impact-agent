"""The view a run concludes from when a model has stated facts: the structured projection of its
reads, plus the admitted statements, minus the readings that cannot stand together.

A harness that reads prose feeds the rules two things: what its structured reads returned
(``read_projection``) and what a model stated from the texts among them (``stated``). This
is the one function that joins them, in ``core`` for the reason the projection is: the
harness concludes over this view and the evaluator replays over it from the exported
statements, and the two may not import each other, so a join written twice could drift.

The join is total: no set of admitted statements makes it raise. That needs a rule, because
the fact base refuses one source holding two values for a single-valued predicate of one
subject, and a statement's source is its carrier's. A sealed world never plants such a pair
and a model's misreading can, and a misreading is behaviour to export and grade, never a
crash of the harness (the first point of the group's design pass). So, for a predicate that
holds one value, the statements of one subject from one source are settled in this order:

- *Two readings of one carrier* that differ are both left out. They are two readings of one
  sentence, never a conflict between sources, and the authority table is for sources.
- *Against a structured field of the same source*, the field stands: a statement naming
  another value is left out, and so is any statement where the record holds that field
  empty. A comment read as naming an owner does not outvote the ticket's own owner field.
- *Several carriers of one source* that still differ are all left out: nothing ranks one
  section over another.

Before any of that, *a carrier the reads withdrew* carries nothing. Two completed reads that
returned one record with different contents leave nothing to conclude from it
(``read_coverage``), and the projection derives no fact from it; a statement quoted from
such a ticket's comment, or from such a document's section, is left out the same way.
Without this the withdrawn ticket's owner field would be gone and a statement from its
own comment would stand in for it as the tracker's value (the group's batch review).

Statements that agree stay, each as its own fact with its own carrier, as corroboration.
Between sources nothing is settled here: a runbook's owner against the tracker's is a
conflict the authority table resolves, as it does for a sealed world. A predicate that
holds a set has nothing to settle among its values.

Nothing is dropped silently. Every admitted statement is in ``included`` or in
``excluded`` with its reason, and stays admitted in the trace either way; exclusion is a
fourth fact about a statement, after emission, admission and placement, and is decided
only here.

Every stated fact is dated to the run's day, as every structured one is: the view drops
what is dated after the day, and a carrier another scenario planted later is still a
record the run read.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.enums import Source, require_member
from leaveimpact.core.facts import FactBase, FactKey, FactView
from leaveimpact.core.predicates import predicate
from leaveimpact.core.read_projection import StructuredReads
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.stated import StatedFact
from leaveimpact.core.values import FactValue

_Slot = tuple[FactKey, Source]
"""One subject and predicate as one source holds it: what the fact base keeps to one value."""


class Exclusion(StrEnum):
    """Why an admitted statement is not in the view; a member is the wire format."""

    CARRIER_WITHDRAWN = "carrier_withdrawn"
    """Its carrier is a record the run's own reads returned two ways."""
    CONFLICTING_READINGS = "conflicting_readings"
    """Its carrier was read as stating two values of a predicate that holds one."""
    CONTRADICTS_STRUCTURED = "contradicts_structured"
    """A structured field of the same source holds another value, or holds none."""
    CONFLICTING_CARRIERS = "conflicting_carriers"
    """Carriers of one source were read as stating different values."""


@dataclass(frozen=True, slots=True)
class Excluded:
    """An admitted statement the view leaves out, with the reason."""

    fact: StatedFact
    reason: Exclusion

    def __post_init__(self) -> None:
        require_member(self.reason, Exclusion, "an exclusion's reason")
        if self.reason in _OF_ONE_VALUE and predicate(self.fact.predicate).multi_valued:
            raise ValueError(
                f"{self.fact.predicate.value} holds a set: nothing stated of it is "
                f"{self.reason.value}"
            )


_OF_ONE_VALUE = frozenset({Exclusion.CONFLICTING_READINGS, Exclusion.CONFLICTING_CARRIERS})
"""The reasons that exist only for a predicate that holds one value."""


@dataclass(frozen=True, slots=True)
class StatedView:
    """What a run concludes from, and what became of each admitted statement.

    ``view`` is what the rules are asked over. ``included`` are the statements in it and
    ``excluded`` the ones left out, each in the order admitted, a statement admitted twice
    from one carrier counted once.
    """

    view: FactView
    included: tuple[StatedFact, ...]
    excluded: tuple[Excluded, ...]


def view_with_stated(reads: StructuredReads, admitted: Iterable[StatedFact]) -> StatedView:
    """The view of ``reads`` with the ``admitted`` statements joined in.

    Raises nothing for what a model stated. With no statement the view is the projection's
    own.

    >>> from datetime import date
    >>> from leaveimpact.core.read_projection import project_reads
    >>> joined = view_with_stated(project_reads((), date(2026, 3, 2)), ())
    >>> (joined.view.facts, joined.included, joined.excluded)
    ((), (), ())
    """
    distinct: dict[tuple[FactKey, FactValue, EntityRef], StatedFact] = {}
    for stated in admitted:
        distinct.setdefault((_key(stated), stated.value, stated.carrier), stated)
    reasons = _exclusions(reads, tuple(distinct.values()))
    included = tuple(stated for stated in distinct.values() if stated not in reasons)
    excluded = tuple(
        Excluded(stated, reasons[stated]) for stated in distinct.values() if stated in reasons
    )
    facts = dict.fromkeys((*reads.facts, *(stated.as_fact(reads.today) for stated in included)))
    view = FactBase(tuple(facts), reads.gaps).observed(
        reads.today, reads.condition.condition, reads.coverage
    )
    return StatedView(view, included, excluded)


def _key(stated: StatedFact) -> FactKey:
    return (stated.subject, stated.predicate)


def _exclusions(
    reads: StructuredReads, statements: tuple[StatedFact, ...]
) -> dict[StatedFact, Exclusion]:
    """Each statement the view must leave out, with why; the module docstring's three steps."""
    structured: dict[_Slot, set[FactValue]] = {}
    for fact in reads.facts:
        structured.setdefault((fact.key, fact.source), set()).add(fact.value)
    empty: set[_Slot] = {(gap.key, gap.source) for gap in reads.gaps}

    reasons: dict[StatedFact, Exclusion] = {}
    by_slot: dict[_Slot, list[StatedFact]] = {}
    withdrawn = reads.coverage.unobserved
    for stated in statements:
        slot = (_key(stated), stated.source)
        if stated.carrier in withdrawn:
            reasons[stated] = Exclusion.CARRIER_WITHDRAWN
        elif slot in empty:
            # The base refuses a source that both holds a value and holds none, whatever
            # the predicate; no structured record of a prose source derives a gap today.
            reasons[stated] = Exclusion.CONTRADICTS_STRUCTURED
        elif not predicate(stated.predicate).multi_valued:
            by_slot.setdefault(slot, []).append(stated)

    for slot, group in by_slot.items():
        read_by_carrier: dict[EntityRef, set[FactValue]] = {}
        for stated in group:
            read_by_carrier.setdefault(stated.carrier, set()).add(stated.value)
        standing: list[StatedFact] = []
        for stated in group:
            if len(read_by_carrier[stated.carrier]) > 1:
                reasons[stated] = Exclusion.CONFLICTING_READINGS
            elif structured.get(slot, {stated.value}) != {stated.value}:
                reasons[stated] = Exclusion.CONTRADICTS_STRUCTURED
            else:
                standing.append(stated)
        if len({stated.value for stated in standing}) > 1:
            reasons.update(dict.fromkeys(standing, Exclusion.CONFLICTING_CARRIERS))
    return reasons


__all__ = ["Excluded", "Exclusion", "StatedView", "view_with_stated"]
