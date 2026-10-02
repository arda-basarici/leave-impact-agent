"""Coverage from reads: what a run's completed reads observed whole, slice by slice.

The mapping from "what was read" to "what may be concluded false" is one pure function
over a trace's operations, here in ``core``, because two parties need the same one and
may not import each other: the evaluator replaying what a run's reads support, and a
harness whose deterministic rules conclude from its own reads. One function cannot drift
between the grader and the graded (the investigator milestone's fourth build step,
ruling 2).

What covers a slice follows the read ports' shapes (the read module):

- *One record* is covered when any completed read returned it, by its id, inside an
  enumeration, a window or a search; when a read by its id answered that no such record
  exists; or when every record of its kind was enumerated, which shows it absent. A
  section is covered when a returned document holds it, a comment when a returned work
  item does.
- *Every record of a kind* is covered by the kind's enumeration, the read that takes no
  argument. Employees, work items and components have one. Documents, leaves, events
  and teams do not, so that slice is *unclosable*: a search returns what matched, a
  window what overlapped, and neither says what else exists.
- *A window* is covered when the completed windows of its read, taken together, contain
  it. A union of intervals is exact, and one window per question is not the only honest
  way to read a calendar.

A failed read covers nothing and a refused one was never a read. What a run observed
stays observed: coverage is a property of the set of completed reads, whatever order
they came in, so a record read before a source failed is still read, and the failure
makes only what was left unobserved at that source *failed* where it would have been
unread.

A record can also be withdrawn. Two completed reads that returned one record with
different contents, or one that returned it and one that found none by its id, leave
nothing to conclude from it, and it counts as never observed.
Its kind then cannot be said to have been observed whole either, nor a window of it, and
the same holds for the work items of a withdrawn comment and the documents of a
withdrawn section: the record in doubt is exactly where the missing evidence could be.
``excluding`` withdraws further records for a caller that has its own reason to doubt
one, as the evaluator has for a comment or a section whose text is not the sealed one.

An operation is credited with what its tool observes only when it is what the tool
declares, in every respect the method table states: the tool is one of the thirteen,
the arguments are the ones it accepts, the source is the one it reads, the outcome has
its cardinality (one record or none for a read by id, a sequence for the rest) and
every returned record is of the kind it returns. The operation type holds none of that
on purpose, so that an export which breaks it can be decoded and reported; here it is
the difference between an observation and a claim of one. An ``employee`` call recorded
against the tracker and answered "no such record" says nothing about the HR system,
and an ``employees`` call that returned leaves did not list the employees. An operation
that fails any of these contributes the records it returned and nothing else: no
absence, no enumeration, no window. Reporting it is its verifier's, not this
function's.

One mismatch the method table cannot state is kept for whoever reports it: a read by id
that came back with a record of another id. The record it returned was returned and
counts; the record it asked for was neither returned nor found missing, so it stays
unobserved by that read, and its reference is held in ``misanswered``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import timedelta
from types import MappingProxyType

from leaveimpact.core.coverage import KindSlice, RecordSlice, Slice, SliceStatus, WindowSlice
from leaveimpact.core.entities import Document, WorkItem
from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.refs import EntityRef, clause_ref, comment_ref
from leaveimpact.core.run_export_json import thawed_json
from leaveimpact.core.run_trace import (
    AbsentOutcome,
    Operation,
    RecordOutcome,
    RecordsOutcome,
    UnreachableOutcome,
)
from leaveimpact.core.tools import (
    TOOL_SPECIFICATIONS,
    Cardinality,
    DateSpanArgument,
    IdArgument,
    InstantSpanArgument,
    ToolSpecification,
    specification_named,
    validate_arguments,
)
from leaveimpact.core.worldtime import DateSpan, InstantSpan, as_utc

HELD_IN: Mapping[EntityKind, EntityKind] = MappingProxyType(
    {EntityKind.COMMENT: EntityKind.WORK_ITEM, EntityKind.CLAUSE: EntityKind.DOCUMENT}
)
"""The kind of record each part is read inside: no read returns a comment or a section alone."""

ENUMERABLE_KINDS: frozenset[EntityKind] = frozenset(
    specification.facts.entity_kind
    for specification in TOOL_SPECIFICATIONS
    if specification.facts.cardinality is Cardinality.SEQUENCE and not specification.arguments
)
"""The kinds a read returns every record of: the ones with a read that takes no argument."""


@dataclass(frozen=True, slots=True)
class ReadCoverage:
    """What a set of completed reads observed, asked slice by slice.

    ``returned`` holds every record a completed read returned, the sections and comments
    inside them included; ``absent`` the records a read by id found none of;
    ``enumerated`` the kinds read in full; the windows are the completed ones, merged
    where they touch; ``failed`` the sources a read found unreachable; ``unobserved``
    the records withdrawn, which count as never read. ``misanswered`` holds the records a
    read asked for by id and got another record instead of; it changes no status and is
    there to be reported.
    """

    returned: frozenset[EntityRef]
    absent: frozenset[EntityRef]
    misanswered: frozenset[EntityRef]
    enumerated: frozenset[EntityKind]
    day_windows: tuple[DateSpan, ...]
    instant_windows: tuple[InstantSpan, ...]
    failed: frozenset[Source]
    unobserved: frozenset[EntityRef]

    def status(self, where: Slice) -> SliceStatus:
        """Whether the reads observed ``where`` whole, and why not when they did not."""
        if self._observed_whole(where):
            return SliceStatus.COVERED
        if where.source in self.failed:
            return SliceStatus.FAILED
        if isinstance(where, KindSlice) and where.kind not in ENUMERABLE_KINDS:
            return SliceStatus.UNCLOSABLE
        return SliceStatus.UNREAD

    def excluding(self, records: Iterable[EntityRef]) -> ReadCoverage:
        """This coverage with ``records`` withdrawn as well: never observed, whatever returned
        them."""
        return replace(self, unobserved=self.unobserved | frozenset(records))

    def _observed_whole(self, where: Slice) -> bool:
        match where:
            case RecordSlice(record):
                if record in self.unobserved:
                    return False
                return (
                    record in self.returned
                    or record in self.absent
                    or record.kind in self.enumerated
                )
            case KindSlice(kind):
                return kind in self.enumerated and not self._in_doubt(kind)
            case WindowSlice(kind, span):
                if self._in_doubt(kind):
                    return False
                if isinstance(span, DateSpan):
                    return any(
                        window.start <= span.start and span.end <= window.end
                        for window in self.day_windows
                    )
                return any(
                    as_utc(window.start) <= as_utc(span.start)
                    and as_utc(span.end) <= as_utc(window.end)
                    for window in self.instant_windows
                )

    def _in_doubt(self, kind: EntityKind) -> bool:
        """Whether a withdrawn record is of ``kind`` or is read inside a record of it."""
        return any(
            kind in (record.kind, HELD_IN.get(record.kind)) for record in self.unobserved
        )


def coverage_from_reads(operations: Iterable[Operation]) -> ReadCoverage:
    """What ``operations`` observed, whatever order they came in.

    >>> coverage_from_reads(()).status(KindSlice(EntityKind.WORK_ITEM)).value
    'unread'
    >>> coverage_from_reads(()).status(KindSlice(EntityKind.DOCUMENT)).value
    'unclosable'
    """
    first_return: dict[EntityRef, Observed[Entity]] = {}
    returned: set[EntityRef] = set()
    absent: set[EntityRef] = set()
    misanswered: set[EntityRef] = set()
    enumerated: set[EntityKind] = set()
    day_windows: list[DateSpan] = []
    instant_windows: list[InstantSpan] = []
    failed: set[Source] = set()
    unobserved: set[EntityRef] = set()

    for operation in operations:
        outcome = operation.outcome
        if isinstance(outcome, UnreachableOutcome):
            failed.add(outcome.source)
            continue
        if isinstance(outcome, RecordOutcome):
            records: tuple[Observed[Entity], ...] = (outcome.record,)
        elif isinstance(outcome, RecordsOutcome):
            records = outcome.records
        elif isinstance(outcome, AbsentOutcome):
            records = ()
        else:
            continue
        for record in records:
            held = (record.ref, *_parts_of(record))
            returned.update(held)
            earlier = first_return.setdefault(record.ref, record)
            if earlier != record:
                unobserved.update((*held, *_parts_of(earlier)))

        asked = _what_was_asked(operation)
        if asked is None:
            continue
        specification, arguments = asked
        if isinstance(outcome, RecordsOutcome) and not specification.arguments:
            enumerated.add(specification.facts.entity_kind)
        for declared in specification.arguments:
            given = arguments[declared.name]
            if isinstance(declared, IdArgument) and isinstance(given, str):
                asked_for = EntityRef(declared.kind, given)
                if isinstance(outcome, AbsentOutcome):
                    absent.add(asked_for)
                elif isinstance(outcome, RecordOutcome) and outcome.record.ref != asked_for:
                    misanswered.add(asked_for)
            elif isinstance(outcome, RecordsOutcome):
                if isinstance(declared, DateSpanArgument) and isinstance(given, DateSpan):
                    day_windows.append(given)
                if isinstance(declared, InstantSpanArgument) and isinstance(given, InstantSpan):
                    instant_windows.append(given)

    for record in absent & first_return.keys():
        # Found by one read and found missing by another: nothing to conclude from either.
        unobserved.update((record, *_parts_of(first_return[record])))

    return ReadCoverage(
        returned=frozenset(returned),
        absent=frozenset(absent),
        misanswered=frozenset(misanswered),
        enumerated=frozenset(enumerated),
        day_windows=_merged_days(day_windows),
        instant_windows=_merged_instants(instant_windows),
        failed=frozenset(failed),
        unobserved=frozenset(unobserved),
    )


def _parts_of(record: Observed[Entity]) -> tuple[EntityRef, ...]:
    """The sections of a document and the comments of a work item: what a record carries that
    a fact can be read from and that has an id of its own."""
    value = record.value
    if isinstance(value, Document):
        return tuple(clause_ref(section.id) for section in value.sections)
    if isinstance(value, WorkItem):
        return tuple(comment_ref(comment.id) for comment in value.comments)
    return ()


def _what_was_asked(
    operation: Operation,
) -> tuple[ToolSpecification, Mapping[str, object]] | None:
    """The tool's specification and the call's arguments as domain values, or ``None`` when the
    operation is not a call of a declared tool, answered as that tool answers, with the
    arguments it declares."""
    specification = specification_named(operation.tool)
    if specification is None or not _answered_as_declared(operation, specification):
        return None
    try:
        return specification, validate_arguments(specification, thawed_json(operation.arguments))
    except ValueError:
        return None


def _answered_as_declared(operation: Operation, specification: ToolSpecification) -> bool:
    """Whether a completed ``operation`` read the source its tool reads and answered in the
    tool's shape: its cardinality, and records of the kind it returns."""
    declared = specification.facts
    outcome = operation.outcome
    if isinstance(outcome, RecordsOutcome):
        shape, records = Cardinality.SEQUENCE, outcome.records
    elif isinstance(outcome, RecordOutcome):
        shape, records = Cardinality.SINGLE, (outcome.record,)
    else:
        shape, records = Cardinality.SINGLE, ()
    return (
        operation.source is declared.source
        and declared.cardinality is shape
        and all(record.kind is declared.entity_kind for record in records)
    )


def _merged_days(windows: list[DateSpan]) -> tuple[DateSpan, ...]:
    """The windows as disjoint runs of days: two that share a day or are on consecutive days
    are one, since days are inclusive at both ends."""
    merged: list[DateSpan] = []
    for window in sorted(windows, key=lambda span: (span.start, span.end)):
        if merged and window.start <= merged[-1].end + timedelta(days=1):
            merged[-1] = DateSpan(merged[-1].start, max(merged[-1].end, window.end))
        else:
            merged.append(window)
    return tuple(merged)


def _merged_instants(windows: list[InstantSpan]) -> tuple[InstantSpan, ...]:
    """The windows as disjoint runs of time: two that overlap or touch are one, since a
    half-open span ends exactly where the next may begin."""
    merged: list[InstantSpan] = []
    for window in sorted(windows, key=lambda span: (as_utc(span.start), as_utc(span.end))):
        if merged and as_utc(window.start) <= as_utc(merged[-1].end):
            last = merged[-1]
            end = last.end if as_utc(last.end) >= as_utc(window.end) else window.end
            merged[-1] = InstantSpan(last.start, end)
        else:
            merged.append(window)
    return tuple(merged)


__all__ = ["ENUMERABLE_KINDS", "HELD_IN", "ReadCoverage", "coverage_from_reads"]
