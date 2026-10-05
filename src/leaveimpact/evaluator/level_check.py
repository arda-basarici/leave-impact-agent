"""The level check: every document a run was shown, held to the corpus level it was assigned.

A run is assigned a corpus level, the documents its systems may hold, and the levels are
compared with each other, so a run shown a document outside its level measured something
else than its arm says (the contract step's ruling on authorship, facts and level). The
level is read off the record and never inferred from what was read: inferring it would
make the check agree with whatever happened.

*Shown* is every document any operation returned, whoever asked: a search's results, a
read by id, the documents a harness put in front of a full-context call. That last surface
needs no rule of its own, since a dispatch's input reads are operations of the trace and
the trace refuses one it does not hold. An operation that is not what its tool declares
still showed what it returned, so the outcome is read as recorded and no credit rule is
applied.

A document outside the level is a finding naming the operation and the document, once per
pair. A document the sealed world does not hold at all is outside every level and is a
finding here as well as an integrity finding: the two say different things.

The membership is the sealed world's (``SealedWorld.level_documents``). For a level the
world seals no membership for, the check is not evaluated, and ``level_check`` answers
``None``: that is a different statement from a run with no finding.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.core.enums import EntityKind
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_trace import OperationId, RecordOutcome, RecordsOutcome
from leaveimpact.evaluator.sealed_world import SealedWorld


@dataclass(frozen=True, slots=True)
class LevelFinding:
    """One document an operation returned that the run's level does not hold."""

    operation: OperationId
    document: EntityRef


@dataclass(frozen=True, slots=True)
class LevelCheck:
    """A run's documents against the level its record assigns: the level, how many distinct
    documents the run was shown, and the ones outside the level, in the trace's order."""

    level: str
    documents: int
    findings: tuple[LevelFinding, ...]


def level_check(world: SealedWorld, export: RunExport) -> LevelCheck | None:
    """Every document the run ``export`` records was shown, against the membership ``world``
    seals for the level the record assigns; ``None`` when the world seals none for it.

    Raises nothing for what the run did.
    """
    level = export.record.corpus_level
    members = world.level_documents(level)
    if members is None:
        return None
    shown: dict[EntityRef, None] = {}
    findings: dict[LevelFinding, None] = {}
    for operation in export.trace.operations:
        outcome = operation.outcome
        if isinstance(outcome, RecordOutcome):
            records = (outcome.record,)
        elif isinstance(outcome, RecordsOutcome):
            records = outcome.records
        else:
            continue
        for record in records:
            if record.ref.kind is not EntityKind.DOCUMENT:
                continue
            shown[record.ref] = None
            if record.ref not in members:
                findings[LevelFinding(operation.id, record.ref)] = None
    return LevelCheck(level, len(shown), tuple(findings))


__all__ = ["LevelCheck", "LevelFinding", "level_check"]
