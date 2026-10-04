"""Scoping: from the requirements a run's view holds to the constraints the rules may apply.

A stated requirement says what covering something requires and names that thing by a span
of its quote. ``binding`` turns one span into a placement. This module takes every
requirement the join left standing, binds each span once over everything the run read, and
says which clause governs which artifact: the constraint keys the rules are given. It also
says which requirements cannot be used, and why (the composer group's first two points).

Per clause, over the statements of its requirement that still stand (they agree on the
count and the criteria, or the join would have left them out as conflicting readings):

- *No span placed*: no constraint. The placements are kept as the diagnostics a report
  shows; nothing is propagated, since a span naming no read artifact has no candidate to
  propagate to.
- *Spans placed on one artifact*, whatever else was stated beside them: the clause governs
  that artifact. A span that ran a word long, or one the guard held ambiguous, costs
  nothing when another emission of the same requirement placed.
- *Spans placed on two artifacts*: the clause was read with two scopes, and a clause has
  one. Neither is used: every statement of that clause's requirement is withheld from the
  view as ``conflicting_scopes``, whatever order they were stated in and whether or not
  either artifact matters to the leave at hand. Using both would lay a constraint on an
  artifact the clause never governed, and a wrong constraint moves verdicts silently;
  taking the first would make a report depend on emission order.

One wrong span alone is still bound and used: that is a wrong binding, the model's, and it
shows as a contradicted constraint when the run is replayed. Only a model contradicting
itself is settled here.

*A document.* A span that names a document means the document's one section: a
responsibility that lives in a document is an impact on its section, and a constraint
applies to what an impact is about. A document of one section gives a constraint on that
section. A document that holds any other number gives none, since nothing says which
section the clause governs, and the clause's statements are withheld as
``scope_without_one_section``. No sealed document a clause is scoped to holds several; a
later generator or unvetted filler could.

A span never names a component (only a ticket, a meeting or a document has a title), so no
constraint composed here is component-scoped.

What comes back keeps every placement, used or not: a withheld requirement stays placed in
the record, and its exclusion says why it was not used.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from leaveimpact.core.admission import carriers_read
from leaveimpact.core.binding import bind_span, titled_artifacts
from leaveimpact.core.claims import ConstraintKey
from leaveimpact.core.entities import Document
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import ClauseId
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.read_projection import StructuredReads
from leaveimpact.core.refs import EntityRef, clause_ref
from leaveimpact.core.run_ending import RequirementPlacement
from leaveimpact.core.stated import PlacementState, StatedFact
from leaveimpact.core.stated_view import Excluded, Exclusion


@dataclass(frozen=True, slots=True)
class Scoped:
    """What the standing requirements of a run scope to.

    ``placements`` holds one entry per requirement given, in the order given.
    ``constraints`` are the pairings the rules may apply, in the order their clauses were
    first stated. ``withheld`` are the requirements whose scope cannot be used, each with
    the reason, in the order given; the caller leaves them out of the view.
    """

    placements: tuple[RequirementPlacement, ...]
    constraints: tuple[ConstraintKey, ...]
    withheld: tuple[Excluded, ...]


def scope_requirements(reads: StructuredReads, requirements: Iterable[StatedFact]) -> Scoped:
    """The placements, the constraints and the withheld statements of ``requirements`` over
    everything ``reads`` returned.

    ``requirements`` are the ``requires`` statements a join included. Raises ``ValueError``
    for a statement of another predicate or one whose carrier ``reads`` never returned: an
    admitted statement's carrier was read, so either is the caller's error.
    """
    standing = tuple(requirements)
    titled = titled_artifacts(reads)
    carriers = carriers_read(reads)
    sections = {
        record.ref: tuple(clause_ref(section.id) for section in record.value.sections)
        for record in reads.returned
        if isinstance(record.value, Document)
    }

    placements: list[RequirementPlacement] = []
    by_clause: dict[EntityRef, list[RequirementPlacement]] = {}
    for stated in standing:
        if stated.predicate is not PredicateName.REQUIRES or stated.target_span is None:
            raise ValueError(f"only a requirement is scoped, got {stated.predicate.value}")
        carrier = carriers.get(stated.carrier)
        if carrier is None:
            raise ValueError(f"{stated.carrier.id} was not returned by these reads")
        entry = RequirementPlacement(stated, bind_span(stated.target_span, carrier.text, titled))
        placements.append(entry)
        by_clause.setdefault(stated.subject, []).append(entry)

    constraints: list[ConstraintKey] = []
    reasons: dict[StatedFact, Exclusion] = {}
    for clause, entries in by_clause.items():
        named = dict.fromkeys(
            entry.placement.artifact
            for entry in entries
            if entry.placement.state is PlacementState.PLACED
            and entry.placement.artifact is not None
        )
        if not named:
            continue
        if len(named) > 1:
            reasons.update((entry.fact, Exclusion.CONFLICTING_SCOPES) for entry in entries)
            continue
        (artifact,) = named
        target = artifact
        if artifact.kind is EntityKind.DOCUMENT:
            held = sections[artifact]
            if len(held) != 1:
                reasons.update(
                    (entry.fact, Exclusion.SCOPE_WITHOUT_ONE_SECTION) for entry in entries
                )
                continue
            target = held[0]
        constraints.append(ConstraintKey(ClauseId(clause.id), target))

    withheld = tuple(Excluded(stated, reasons[stated]) for stated in standing if stated in reasons)
    return Scoped(tuple(placements), tuple(constraints), withheld)


__all__ = ["Scoped", "scope_requirements"]
