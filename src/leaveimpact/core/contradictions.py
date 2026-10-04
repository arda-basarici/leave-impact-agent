"""A source that contradicts itself within one run: which two reads disagree, and about what.

The world a run reads is static while it runs, so two complete reads of one structured
source that cannot both be true are never a state to conclude from. They are a defect of
the source or of its adapter, and the attempt ends there (the contract step's ruling on a
source that contradicts itself, extending the baseline step's ruling on the HR system).
Degrading instead would turn a broken vendor into plausible unknowns that are then graded
as a model's behaviour.

A contradiction is established only between the same record and reads that are equivalent
and complete. Four shapes, each between two operations whatever order they came in:

- *Returns differ*: two reads returned one record with different contents, a repeated read
  by id among them; or one read returned one record twice with different contents, which
  is the same fault found inside a single answer.
- *Returned and absent*: a read by id answered "no such record" for a record another read
  returned.
- *Omitted by an enumeration*: a read that returns every record of a kind did not return a
  record of that kind another read returned.
- *Omitted by a window*: a read of every leave or event overlapping a span did not return
  one that another read returned and whose own span overlaps it, by that port's rule:
  leaves by inclusive calendar days, events by half-open instants.

What establishes nothing: a failed or a refused read; a search, which is capped and says
nothing of what it left out; a window the record's own span does not overlap; an operation
that is not what its tool declares, by the same credit the coverage mapping gives
(``read_coverage``), so what is not an observation there is no witness here. Whether a
port's sequence is the whole answer is the port's contract and cannot be seen from a trace:
an adapter that returns a partial page as complete shows up here as an omission, loudly,
which is the intended outcome and a known way for a lagging index to stop runs.

The corpus is outside the rule, which is about structured sources. A document two reads
returned differently is withdrawn by the coverage mapping and what was stated from it is
left out of the view; that is a degrade the rule keeps. A malformed record of any source,
the corpus included, still fails a run at its operation: that is another defect and is
found where the outcome is.

The coverage mapping itself does not change: it still withdraws a record returned two ways,
because whoever replays an export must be total over anything an export can hold. A
harness asks this module first and fails before it concludes.

Both operations are the witness. The finder returns them typed, with the one a failure is
sited at: the later of the two, the read that made the disagreement visible, unless that
read answered "no such record". An absent answer is evidence and anchors no defect (the
export's standing rule on a failure's site), so the site is then the earlier operation,
the one that returned the record the later read denies. Either way the site is an
operation that returned records the harness could not accept, the other one is named in
the failure's reason, and anyone holding the trace recomputes the typed value with this
function.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.entities import CalendarEvent, Leave
from leaveimpact.core.enums import Source
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.read_coverage import Supplied, supplied_by, tool_mismatches
from leaveimpact.core.refs import SOURCE_BY_TARGET_KIND, EntityRef
from leaveimpact.core.run_trace import AbsentOutcome, Operation, OperationId


class ContradictionKind(StrEnum):
    """How two reads of one structured source disagree; a member is the wire format."""

    RETURNS_DIFFER = "returns_differ"
    RETURNED_AND_ABSENT = "returned_and_absent"
    OMITTED_BY_ENUMERATION = "omitted_by_enumeration"
    OMITTED_BY_WINDOW = "omitted_by_window"


@dataclass(frozen=True, slots=True)
class Contradiction:
    """Two operations of one run that cannot both be true, and the record they disagree
    about. ``earlier`` and ``later`` are in the trace's order, and are one operation when a
    single answer held the record twice. The disagreement is visible once ``later`` is
    logged; ``site`` is where a failure is anchored, ``later`` unless it answered "no such
    record", and then ``earlier``."""

    kind: ContradictionKind
    record: EntityRef
    earlier: OperationId
    later: OperationId
    site: OperationId


def self_contradictions(operations: Iterable[Operation]) -> tuple[Contradiction, ...]:
    """Every contradiction among ``operations``, ordered by the later operation's place in the
    trace, then the earlier one's; empty when the reads agree.

    >>> self_contradictions(())
    ()
    """
    witnesses: list[tuple[OperationId, Supplied]] = []
    found: dict[Contradiction, None] = {}
    for operation in operations:
        if tool_mismatches(operation):
            continue
        supplied = supplied_by(operation)
        for record in _twice_and_differing(supplied):
            found[
                Contradiction(
                    ContradictionKind.RETURNS_DIFFER,
                    record,
                    operation.id,
                    operation.id,
                    operation.id,
                )
            ] = None
        denies = isinstance(operation.outcome, AbsentOutcome)
        for earlier_id, earlier in witnesses:
            site = earlier_id if denies else operation.id
            for kind, record in (*_between(earlier, supplied), *_between(supplied, earlier)):
                found[Contradiction(kind, record, earlier_id, operation.id, site)] = None
        witnesses.append((operation.id, supplied))
    return tuple(found)


def _twice_and_differing(supplied: Supplied) -> list[EntityRef]:
    """The structured records one operation returned more than once with different contents."""
    first: dict[EntityRef, Observed[Entity]] = {}
    differing: dict[EntityRef, None] = {}
    for record in supplied.records:
        if not _structured(record.ref):
            continue
        if first.setdefault(record.ref, record).value != record.value:
            differing[record.ref] = None
    return list(differing)


def _between(one: Supplied, other: Supplied) -> list[tuple[ContradictionKind, EntityRef]]:
    """What ``one`` says that ``other``'s returned records contradict. The caller asks both
    ways round; differing returns are found from either side and are one finding there,
    the pair of operations being the same."""
    disagreements: list[tuple[ContradictionKind, EntityRef]] = []
    returned = {record.ref: record for record in one.records if _structured(record.ref)}
    for record in other.records:
        ref = record.ref
        if not _structured(ref):
            continue
        if ref in returned:
            if returned[ref].value != record.value:
                disagreements.append((ContradictionKind.RETURNS_DIFFER, ref))
            continue
        if one.absent == ref:
            disagreements.append((ContradictionKind.RETURNED_AND_ABSENT, ref))
        elif one.enumerated is ref.kind:
            disagreements.append((ContradictionKind.OMITTED_BY_ENUMERATION, ref))
        elif _inside_window(one, record):
            disagreements.append((ContradictionKind.OMITTED_BY_WINDOW, ref))
    return disagreements


def _inside_window(one: Supplied, record: Observed[Entity]) -> bool:
    """Whether ``one`` read a window that, by its port's overlap rule, owed ``record``."""
    value = record.value
    if isinstance(value, Leave) and one.day_window is not None:
        return value.span.overlaps(one.day_window)
    if isinstance(value, CalendarEvent) and one.instant_window is not None:
        return value.span.overlaps(one.instant_window)
    return False


def _structured(record: EntityRef) -> bool:
    return SOURCE_BY_TARGET_KIND[record.kind] is not Source.CORPUS


__all__ = ["Contradiction", "ContradictionKind", "self_contradictions"]
