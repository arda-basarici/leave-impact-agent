"""The observed-run view: the facts a run's own reads support, and whether those reads returned
the sealed world.

Grounding asks one thing of a run: do the rules, fed only what its completed reads
returned, conclude what its report claims. This module builds what the rules are fed. It
uses the sealed world for two purposes and no other. Prose carries facts no derivation can
read, so a sealed authored fact enters the view when the comment or the section that
carries it came back with the sealed text, and only then. And every returned record is
compared with the sealed one of its id, because a grade against the sealed truth means
nothing for a run that was shown something else. Truth enters only through what the run
read (the investigator milestone's fourth build step, ruling 1).

The view is the structured projection of the reads (``core``'s ``read_projection``: each
record as first returned, the facts and gaps of the usable ones dated to the run's day, the
coverage, the condition) with the sealed overlay this module adds. A harness that reads no
prose concludes from the projection alone, so what the graded concludes from is the
structured part of what the grader replays over, by construction (the fifth build step's
design). Over the projection:

- *Structured facts* are the projection's. A record that differs from the sealed one still
  derives its facts, with a finding: grounding asks what the run's reads support, and it
  read that record. This is the one place the view can hold something the sealed world
  does not.
- *Prose* is gated on content. A comment or a section is read as sealed when its content
  is the sealed content; then the facts it carries are admitted, re-dated to the run's
  day. A part whose content differs, a part the sealed record does not hold, and a
  sealed part the returned record lacks are each a finding and each withdrawn from the
  run's coverage: the evaluator can say what a part states, possibly nothing, only when
  its text is the sealed text, and a negative that could be hidden in a part it cannot
  vouch for is not grounded (``ReadCoverage.excluding``). The gate is on every part, not
  only on the ones that carry a fact.
- *A record returned two ways* by the run's own reads is withdrawn by the projection and
  derives nothing; here it is a finding. A record whose fields no fact can be made from is
  withdrawn there too, and is a finding here: a decodable export can hold one (a blank
  location), and nothing a run did raises in the evaluator.

The other direction is checked too: a sealed record that a completed enumeration, a
completed window or a read by its id should have returned and did not. The run observed
what it observed, so its coverage stands and the facts are what came back; the finding
says the systems no longer held the sealed world when the run read them. A read by id
that came back with a record of another id is a finding of its own, about the record
asked for, whether or not the sealed world holds it and whatever else returned it: the
source or its adapter answered a question it was not asked.

A finding names a kind and ids, never content, since the job that reports it logs in
public. Whether a run carrying one enters a reported table is the preregistration's; here
the run is observed all the same.

The fact base cannot refuse what this builds. The projection states identical facts once
and a gap and a value never come from one record's field, and the authored facts admitted
are a subset of the sealed ones, which the world's own base already holds together. If it
did refuse, that would be a defect of this module and should surface as one.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from leaveimpact.core.entities import CalendarEvent, Document, Leave, WorkItem
from leaveimpact.core.facts import Fact, FactBase, FactView
from leaveimpact.core.ports.observed import Entity
from leaveimpact.core.read_coverage import ReadCoverage
from leaveimpact.core.read_projection import project_reads
from leaveimpact.core.refs import EntityRef
from leaveimpact.core.run_export import RunExport
from leaveimpact.evaluator.world_index import WorldIndex, parts_of


class IntegrityKind(StrEnum):
    """How what a run read can differ from the sealed world; a member is the wire format."""

    UNKNOWN_RECORD = "unknown_record"
    RECORD_DIFFERS = "record_differs"
    PART_DIFFERS = "part_differs"
    PART_UNKNOWN = "part_unknown"
    PART_MISSING = "part_missing"
    RETURNS_DIFFER = "returns_differ"
    RECORD_NOT_DERIVABLE = "record_not_derivable"
    SEALED_RECORD_NOT_RETURNED = "sealed_record_not_returned"
    ANOTHER_RECORD_RETURNED = "another_record_returned"


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    """One difference between what a run read and the sealed world: its kind, the record it
    concerns, and the comment or section when it is about one."""

    kind: IntegrityKind
    record: EntityRef
    part: EntityRef | None = None


@dataclass(frozen=True, slots=True)
class ObservedRun:
    """What one run's completed reads observed.

    ``view`` is what the rules are asked over. ``coverage`` is the view's own, kept typed
    for the callers that ask which read supplied a slice. ``read_as_sealed`` holds the
    comments and sections that came back with the sealed content, the only parts through
    which anything sealed is admitted. ``findings`` are in a fixed order: by kind, record
    and part.
    """

    view: FactView
    coverage: ReadCoverage
    read_as_sealed: frozenset[EntityRef]
    findings: tuple[IntegrityFinding, ...]


def observe(index: WorldIndex, export: RunExport) -> ObservedRun:
    """What the run ``export`` records observed, checked against the sealed world ``index``.

    Raises nothing for what the run did or was shown.
    """
    today = export.context.today
    projection = project_reads(export.trace.operations, today)
    reads = projection.reads
    findings: list[IntegrityFinding] = []
    withdrawn: set[EntityRef] = set()
    read_as_sealed: set[EntityRef] = set()
    admitted: dict[Fact, None] = {}

    for record in projection.returned:
        ref = record.ref
        if ref in reads.unobserved:
            findings.append(IntegrityFinding(IntegrityKind.RETURNS_DIFFER, ref))
            continue
        entity = record.value
        sealed = index.records.get(ref)
        if sealed is None:
            findings.append(IntegrityFinding(IntegrityKind.UNKNOWN_RECORD, ref))
            withdrawn.update(part for part, _ in parts_of(entity))
        else:
            if _without_parts(entity) != _without_parts(sealed):
                findings.append(IntegrityFinding(IntegrityKind.RECORD_DIFFERS, ref))
            if entity == sealed:
                admitted.update(dict.fromkeys(index.carried.get(ref, ())))
            sealed_parts = dict(parts_of(sealed))
            returned_parts = dict(parts_of(entity))
            for part, content in returned_parts.items():
                if part not in sealed_parts:
                    kind = IntegrityKind.PART_UNKNOWN
                elif content != sealed_parts[part]:
                    kind = IntegrityKind.PART_DIFFERS
                else:
                    read_as_sealed.add(part)
                    admitted.update(dict.fromkeys(index.carried.get(part, ())))
                    continue
                findings.append(IntegrityFinding(kind, ref, part))
                withdrawn.add(part)
            for part in sealed_parts.keys() - returned_parts.keys():
                findings.append(IntegrityFinding(IntegrityKind.PART_MISSING, ref, part))
                withdrawn.add(part)

    findings.extend(
        IntegrityFinding(IntegrityKind.RECORD_NOT_DERIVABLE, ref) for ref in projection.underivable
    )
    findings.extend(
        IntegrityFinding(IntegrityKind.SEALED_RECORD_NOT_RETURNED, ref)
        for ref in _owed_and_not_returned(index, reads)
    )
    findings.extend(
        IntegrityFinding(IntegrityKind.ANOTHER_RECORD_RETURNED, ref) for ref in reads.misanswered
    )
    coverage = projection.coverage.excluding(withdrawn)
    facts = (*projection.facts, *(replace(fact, observable_from=today) for fact in admitted))
    view = FactBase(facts, projection.gaps).observed(
        today, projection.condition.condition, coverage
    )
    return ObservedRun(
        view=view,
        coverage=coverage,
        read_as_sealed=frozenset(read_as_sealed),
        findings=tuple(sorted(findings, key=_finding_order)),
    )


def _without_parts(entity: Entity) -> Entity:
    """``entity`` with its comments or sections set aside: they are compared one by one."""
    if isinstance(entity, WorkItem):
        return replace(entity, comments=())
    if isinstance(entity, Document):
        return replace(entity, sections=())
    return entity


def _owed_and_not_returned(index: WorldIndex, reads: ReadCoverage) -> list[EntityRef]:
    """The sealed records a completed read should have returned and none did: of a kind that
    was enumerated, inside a window that was read, or answered "no such record" by its id.

    A record the run's reads disagree about is left to that finding.
    """
    owed: list[EntityRef] = []
    for ref, sealed in index.records.items():
        if ref in reads.returned or ref in reads.unobserved:
            continue
        if ref in reads.absent or ref.kind in reads.enumerated:
            owed.append(ref)
        elif isinstance(sealed, Leave):
            if any(sealed.span.overlaps(window) for window in reads.day_windows):
                owed.append(ref)
        elif isinstance(sealed, CalendarEvent) and any(
            sealed.span.overlaps(window) for window in reads.instant_windows
        ):
            owed.append(ref)
    return owed


def _finding_order(finding: IntegrityFinding) -> tuple[str, str, str, str]:
    part = finding.part
    return (
        finding.kind.value,
        finding.record.kind.value,
        finding.record.id,
        "" if part is None else part.id,
    )


__all__ = ["IntegrityFinding", "IntegrityKind", "ObservedRun", "observe"]
