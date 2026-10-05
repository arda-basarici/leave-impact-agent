"""The fact stages: how far each prose statement a scenario's answer needs got in one run, and
what every statement the run's model made was.

Some of what the rules conclude rests on facts only prose carries, and a system that reads
prose has a model state them. Between a needed statement and a report that rests on it are
four steps, and a run can lose the statement at each. This module says, per needed
statement, which steps it passed: the mechanism measure's four stages, which explain where
a system succeeded or failed on the way to its report and carry no headline claim (the
contract step's ruling on the mechanism measure; the evaluator group's first four points).

*Needed* is a property of the sealed scenario and the condition the run was assigned, never
of the run: the retrieval targets whose removal moves a key every report must hold
(``retrieval_targets``), given here by the caller. One statement is one target whatever
carries it.

*The stages are a funnel*, each requiring the one before it, so the four counts fall over
one denominator and a drop between two neighbours is a count of statements lost at that
step:

- *returned*: a completed operation returned one of the target's sealed carriers;
- *emitted*: an answer holds the target's statement, subject, predicate and value, stated
  from one of its sealed carriers, that carrier having come back with the sealed text in an
  operation logged before the answer. The quote and a requirement's span are no part of
  this: the gates judge the quote and the binding the span;
- *admitted*: the record admitted one such emission;
- *usable*: an admitted one is not among the composition's exclusions, and for a
  requirement one of its spans is placed on what the sealed world scopes its clause to. A
  requirement placed on another artifact is composed and graded as the model's wrong
  binding, and it is not the needed fact in the view.

The stages read what the export records (its admissions, its placements, its exclusions);
whether the record is what the gates and the composing rules give is ``fact_recheck``'s. A
failed attempt keeps its denominator and whatever its trace shows of the first three
stages, and nothing of it is usable, nothing having been composed: a system that fails
often must not show better stages than one that finishes.

*Every emission is classified*, each entry of each batch in exactly one class, by its
carrier first and by the sealed world's facts after:

- *malformed*: an input no statement could be made of; a batch the parser could not read
  is one such row, its entries being unknown;
- *unknown carrier*: the carrier is no comment or section of the sealed world;
- *unread carrier*: no operation logged before the answer returned it;
- *carrier not as sealed*: it came back with other content, so what it states cannot be
  vouched for;
- *needed*: a target's statement on a carrier that states it;
- *true and unneeded*: the carrier states it and no required row depends on it, valid
  context;
- *true on another carrier*: prose of the world states it, and this carrier does not;
- *true in a structured record*: no prose states it and a structured record holds it, a
  comment read as naming its own ticket's owner being the case a real model produced. It
  is a true statement the text may not make, and calling it false would count a model's
  restatement of a field as an invention;
- *false*: the world holds no such statement, in prose or in a record.

Beside the classes a run holds the outcome of each recorded placement against the sealed
scope and the reason of each recorded exclusion, the supporting detail a table shows
beside the stages.

Out of scope, and decided by the caller, which then holds no ``FactStages``: a system that
states no fact, a claim set a model authored, an assigned condition with no answer. Nothing
a run did raises here.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.entities import Comment, DocumentSection
from leaveimpact.core.ids import ClauseId
from leaveimpact.core.model_calls import MalformedBatch
from leaveimpact.core.predicates import PredicateName
from leaveimpact.core.read_coverage import supplied_by
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_record import TerminalStatus
from leaveimpact.core.run_trace import ModelCallId
from leaveimpact.core.stated import (
    Admitted,
    FactRefusal,
    PlacementState,
    Refused,
    RefusedInput,
    StatedFact,
)
from leaveimpact.core.stated_view import Exclusion
from leaveimpact.core.values import FactValue
from leaveimpact.evaluator.retrieval_targets import RetrievalTarget
from leaveimpact.evaluator.world_index import Statement, WorldIndex, parts_of, statement_of

STAGES: tuple[str, ...] = ("returned", "emitted", "admitted", "usable")
"""The four stages by name, in the funnel's order: the names a registration lists."""

_Stated = tuple[EntityRef, PredicateName, FactValue, EntityRef, str | None]
"""A statement as the join counts it once: subject, predicate, value, carrier, target span."""


class EmissionClass(StrEnum):
    """What one entry a model stated is, against the sealed world; a member is the wire
    format."""

    MALFORMED = "malformed"
    UNKNOWN_CARRIER = "unknown_carrier"
    UNREAD_CARRIER = "unread_carrier"
    CARRIER_NOT_AS_SEALED = "carrier_not_as_sealed"
    NEEDED = "needed"
    TRUE_UNNEEDED = "true_unneeded"
    TRUE_ON_ANOTHER_CARRIER = "true_on_another_carrier"
    TRUE_IN_A_STRUCTURED_RECORD = "true_in_a_structured_record"
    FALSE = "false"


class PlacementOutcome(StrEnum):
    """What a requirement's span bound to, against what the sealed world scopes its clause
    to; a member is the wire format."""

    ON_THE_SEALED_TARGET = "on_the_sealed_target"
    ELSEWHERE = "elsewhere"
    UNPLACED = "unplaced"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class EmissionRow:
    """One entry of one batch: where it is, its class, and the statement and the recorded
    admission when the entry is a stated fact.

    ``entry`` is ``None`` for a batch the parser could not read. ``fact`` is ``None`` for a
    malformed row. ``admitted`` and ``refusal`` are the record's: admitted, or refused under
    the reason, both unset for a malformed row.
    """

    model_call: ModelCallId
    batch: int
    entry: int | None
    emission_class: EmissionClass
    fact: StatedFact | None = None
    admitted: bool | None = None
    refusal: FactRefusal | None = None


@dataclass(frozen=True, slots=True)
class TargetStages:
    """One needed statement in one run and the stages it reached; construction refuses a
    stage reached without the one before it."""

    target: RetrievalTarget
    returned: bool
    emitted: bool
    admitted: bool
    usable: bool

    def __post_init__(self) -> None:
        reached = (self.returned, self.emitted, self.admitted, self.usable)
        if any(later and not earlier for earlier, later in zip(reached, reached[1:], strict=False)):
            raise ValueError("a stage is reached only through the one before it")

    @property
    def reached(self) -> tuple[bool, bool, bool, bool]:
        """The four stages in ``STAGES``' order."""
        return (self.returned, self.emitted, self.admitted, self.usable)

    @property
    def predicate(self) -> PredicateName:
        """The predicate of the needed statement."""
        return self.target.statement[1]


@dataclass(frozen=True, slots=True)
class FactStages:
    """One run against the statements its answer needs: a row per target in the targets'
    order, a row per emission in the trace's, and the recorded placements and exclusions
    read against the sealed world, in the composition's order."""

    targets: tuple[TargetStages, ...]
    emissions: tuple[EmissionRow, ...]
    placements: tuple[PlacementOutcome, ...]
    exclusions: tuple[Exclusion, ...]


def fact_stages(
    index: WorldIndex,
    export: RunExport,
    needed: Sequence[RetrievalTarget],
    held: Collection[Statement],
) -> FactStages:
    """The stages the run ``export`` records reached on each of ``needed``, and what each of
    its emissions was.

    ``needed`` are the targets that move a required key of the oracle's answer for the
    scenario under the assigned condition; ``index`` is the sealed world's; ``held`` are
    the statements the world's truth holds on the run's day with every source reachable,
    from prose or from a record, which is what tells a statement no prose makes and a
    record does from one the world does not hold at all.
    """
    trace = export.trace
    wanted = {target.statement for target in needed}
    emissions = _emissions(index, export, wanted, held)

    composed = export.record.status is not TerminalStatus.FAILED
    composition = trace.composition
    excluded = {_as_stated(entry.fact) for entry in composition.exclusions}
    on_target = {
        _as_stated(entry.fact)
        for entry in composition.placements
        if _outcome_of(index, entry.fact, entry.placement.state, entry.placement.artifact)
        is PlacementOutcome.ON_THE_SEALED_TARGET
    }

    came_back: set[EntityRef] = set()
    for operation in trace.operations:
        came_back.update(supplied_by(operation).returned)

    stated: dict[Statement, list[EmissionRow]] = {}
    for row in emissions:
        if row.emission_class is EmissionClass.NEEDED and row.fact is not None:
            stated.setdefault(row.fact.statement, []).append(row)

    targets: list[TargetStages] = []
    for target in needed:
        returned = any(carrier.part in came_back for carrier in target.carriers)
        rows = stated.get(target.statement, []) if returned else []
        let_in = [row.fact for row in rows if row.admitted and row.fact is not None]
        usable = composed and any(
            _as_stated(fact) not in excluded
            and (fact.predicate is not PredicateName.REQUIRES or _as_stated(fact) in on_target)
            for fact in let_in
        )
        targets.append(TargetStages(target, returned, bool(rows), bool(let_in), usable))

    return FactStages(
        tuple(targets),
        emissions,
        tuple(
            _outcome_of(index, entry.fact, entry.placement.state, entry.placement.artifact)
            for entry in composition.placements
        ),
        tuple(entry.reason for entry in composition.exclusions),
    )


def _emissions(
    index: WorldIndex, export: RunExport, wanted: set[Statement], held: Collection[Statement]
) -> tuple[EmissionRow, ...]:
    """Every entry of every batch of the trace, classified."""
    trace = export.trace
    rows: list[EmissionRow] = []
    for call in trace.model_calls:
        if call.answer is None or not call.answer.fact_batches:
            continue
        answered_at = call.dispatches[-1].outcome_position
        assert answered_at is not None  # an answer is what a recorded response carried
        before = project_reads(
            (
                operation
                for operation in trace.operations
                if operation.position is not None and operation.position < answered_at
            ),
            export.context.today,
        )
        read: dict[EntityRef, Comment | DocumentSection] = {}
        for record in before.returned:
            for part, content in parts_of(record.value):
                read.setdefault(part, content)
        for batch_at, batch in enumerate(call.answer.fact_batches):
            if isinstance(batch, MalformedBatch):
                rows.append(EmissionRow(call.id, batch_at, None, EmissionClass.MALFORMED))
                continue
            for entry_at, entry in enumerate(batch.entries):
                if isinstance(entry, RefusedInput):
                    rows.append(EmissionRow(call.id, batch_at, entry_at, EmissionClass.MALFORMED))
                    continue
                rows.append(
                    EmissionRow(
                        call.id,
                        batch_at,
                        entry_at,
                        _class_of(index, entry.fact, read, wanted, held),
                        entry.fact,
                        isinstance(entry, Admitted),
                        entry.reason if isinstance(entry, Refused) else None,
                    )
                )
    return tuple(rows)


def _class_of(
    index: WorldIndex,
    fact: StatedFact,
    read: dict[EntityRef, Comment | DocumentSection],
    wanted: set[Statement],
    held: Collection[Statement],
) -> EmissionClass:
    sealed = index.parts.get(fact.carrier)
    if sealed is None:
        return EmissionClass.UNKNOWN_CARRIER
    if fact.carrier not in read:
        return EmissionClass.UNREAD_CARRIER
    if read[fact.carrier] != sealed.content:
        return EmissionClass.CARRIER_NOT_AS_SEALED
    statement = fact.statement
    if statement in {statement_of(held) for held in index.carried.get(fact.carrier, ())}:
        return EmissionClass.NEEDED if statement in wanted else EmissionClass.TRUE_UNNEEDED
    if statement in index.statements:
        return EmissionClass.TRUE_ON_ANOTHER_CARRIER
    if statement in held:
        return EmissionClass.TRUE_IN_A_STRUCTURED_RECORD
    return EmissionClass.FALSE


def _outcome_of(
    index: WorldIndex, fact: StatedFact, state: PlacementState, artifact: EntityRef | None
) -> PlacementOutcome:
    """A recorded placement against the sealed scope of its clause. A span that names a
    document names its one section, which is how the sealed world scopes a clause to one."""
    if state is PlacementState.UNPLACED:
        return PlacementOutcome.UNPLACED
    if state is PlacementState.AMBIGUOUS:
        return PlacementOutcome.AMBIGUOUS
    target = index.scope.get(ClauseId(fact.subject.id))
    if target is not None and artifact is not None:
        held = index.parts.get(target)
        if artifact == target or (held is not None and held.parent == artifact):
            return PlacementOutcome.ON_THE_SEALED_TARGET
    return PlacementOutcome.ELSEWHERE


def _as_stated(fact: StatedFact) -> _Stated:
    return (fact.subject, fact.predicate, fact.value, fact.carrier, fact.target_span)


__all__ = [
    "STAGES",
    "EmissionClass",
    "EmissionRow",
    "FactStages",
    "PlacementOutcome",
    "TargetStages",
    "fact_stages",
]
