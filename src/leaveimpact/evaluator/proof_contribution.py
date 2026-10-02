"""Proof contribution: which of a run's completed reads supplied something a conclusion about
its report rests on, and which did not.

The replay keeps, for every claim, the witnesses of the rules' own conclusion: what
supports a reproduced claim, what contradicts a contradicted one, what was seen and what
stopped the answer for an unsupported one. A witness names a record, a gap, or a slice of
a source; it never names an operation, so that the truth and a run give the same proof for
the same question. This module is where a witness meets the trace (the investigator
milestone's fourth build step, ruling 5).

One rule: *first supply*. Whatever a witness names is attributed to the earliest completed
operation that supplied it, and to no other.

- A fact or a gap names the record, the comment or the section it was read from: the first
  operation that returned it, a comment or a section inside its ticket or its document.
- A covered record names the record whose return, or whose absence, settled a negative.
  Three reads can observe one record: one that returned it, one by its id that found
  none, and the enumeration of its kind. The earliest of them supplied it.
- A covered kind names the enumeration: the first read of that kind in full.
- A covered window names days or instants. Each part of the question's span is attributed
  to the first window that covered it, so two windows that close a question between them
  both contribute, and one that covers only what an earlier window already had does not.
- A slice that was not covered (unread, failed, or one no read can close) names nothing a
  read supplied.

A negative that needs several slices has a witness for each, so every read it needed
contributes: a skill not held rests on the employee's record and on the tracker's
enumeration, and both are attributed.

A completed operation that supplied nothing any witness names is *extra*. Extra is a cost
that fed no conclusion about the report, and that is all it says: it is not a mistake,
since a read can be the reasonable thing to do and turn out to hold nothing, and it is no
judgment of what the system attended to, which a trace cannot show. A later read identical
to an earlier one is extra unless it first supplies something else, by the same rule and
with no special case. Failed and refused operations are neither: they completed nothing,
and their cost is in the tallies.

What an operation supplied is ``core``'s reading of it (``supplied_by``), the one the
coverage a proof was built on was gathered from. An operation that is not what its tool
declares supplied the records it returned and nothing else, here as there.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from leaveimpact.core.closure import Consulted, Witness
from leaveimpact.core.coverage import KindSlice, RecordSlice, SliceStatus, WindowSlice
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.read_coverage import supplied_by
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_trace import Operation, OperationId, is_completed_read
from leaveimpact.core.worldtime import DateSpan, InstantSpan, as_utc
from leaveimpact.evaluator.replay import ClaimGrounding


@dataclass(frozen=True, slots=True)
class ProofContribution:
    """A trace's completed operations, split by whether a witness names something each first
    supplied; both in the trace's order, together every completed operation once."""

    contributing: tuple[OperationId, ...]
    extra: tuple[OperationId, ...]


def proof_contribution(
    operations: Sequence[Operation], groundings: Iterable[ClaimGrounding]
) -> ProofContribution:
    """Which completed ``operations`` first supplied something a proof in ``groundings`` names.

    ``groundings`` are the replay's records of the report the same run ended with, every
    standing included.
    """
    supply = _Supply(operations)
    named: set[OperationId] = set()
    for witness in dict.fromkeys(witness for record in groundings for witness in record.proof):
        named.update(supply.suppliers_of(witness))
    completed = [op.id for op in operations if is_completed_read(op.outcome)]
    return ProofContribution(
        contributing=tuple(id for id in completed if id in named),
        extra=tuple(id for id in completed if id not in named),
    )


class _Supply:
    """What each completed operation of a trace was the first to supply."""

    def __init__(self, operations: Sequence[Operation]) -> None:
        self.order: dict[OperationId, int] = {}
        self.returned: dict[EntityRef, OperationId] = {}
        self.absent: dict[EntityRef, OperationId] = {}
        self.enumerated: dict[EntityKind, OperationId] = {}
        self.day_windows: list[tuple[OperationId, DateSpan]] = []
        self.instant_windows: list[tuple[OperationId, InstantSpan]] = []
        for position, operation in enumerate(operations):
            supplied = supplied_by(operation)
            self.order[operation.id] = position
            for ref in supplied.returned:
                self.returned.setdefault(ref, operation.id)
            if supplied.absent is not None:
                self.absent.setdefault(supplied.absent, operation.id)
            if supplied.enumerated is not None:
                self.enumerated.setdefault(supplied.enumerated, operation.id)
            if supplied.day_window is not None:
                self.day_windows.append((operation.id, supplied.day_window))
            if supplied.instant_window is not None:
                self.instant_windows.append((operation.id, supplied.instant_window))

    def suppliers_of(self, witness: Witness) -> tuple[OperationId, ...]:
        """The operations that first supplied what ``witness`` names; none when it names
        nothing a read supplied."""
        if not isinstance(witness, Consulted):
            return self._earliest(self.returned.get(witness.evidence.target))
        if witness.status is not SliceStatus.COVERED:
            return ()
        match witness.where:
            case RecordSlice(record):
                return self._earliest(
                    self.returned.get(record),
                    self.absent.get(record),
                    self.enumerated.get(record.kind),
                )
            case KindSlice(kind):
                return self._earliest(self.enumerated.get(kind))
            case WindowSlice(_, span):
                if isinstance(span, DateSpan):
                    return _first_to_cover_days(span, self.day_windows)
                return _first_to_cover_instants(span, self.instant_windows)

    def _earliest(self, *candidates: OperationId | None) -> tuple[OperationId, ...]:
        """The earliest of the operations that each supplied the same thing on its own."""
        held = [candidate for candidate in candidates if candidate is not None]
        return (min(held, key=self.order.__getitem__),) if held else ()


def _first_to_cover_days(
    span: DateSpan, windows: Sequence[tuple[OperationId, DateSpan]]
) -> tuple[OperationId, ...]:
    """The operations whose window was the first to cover some day of ``span``."""
    uncovered = {span.start.toordinal() + offset for offset in range(span.days)}
    first: list[OperationId] = []
    for operation, window in windows:
        covered = {
            day for day in uncovered if window.start.toordinal() <= day <= window.end.toordinal()
        }
        if covered:
            first.append(operation)
            uncovered -= covered
    return tuple(first)


def _first_to_cover_instants(
    span: InstantSpan, windows: Sequence[tuple[OperationId, InstantSpan]]
) -> tuple[OperationId, ...]:
    """The operations whose window was the first to cover some stretch of ``span``, both
    half-open."""
    uncovered: list[tuple[datetime, datetime]] = [(as_utc(span.start), as_utc(span.end))]
    first: list[OperationId] = []
    for operation, window in windows:
        start, end = as_utc(window.start), as_utc(window.end)
        left: list[tuple[datetime, datetime]] = []
        took = False
        for low, high in uncovered:
            if end <= low or high <= start:
                left.append((low, high))
                continue
            took = True
            if low < start:
                left.append((low, start))
            if end < high:
                left.append((end, high))
        if took:
            first.append(operation)
            uncovered = left
    return tuple(first)


__all__ = ["ProofContribution", "proof_contribution"]
