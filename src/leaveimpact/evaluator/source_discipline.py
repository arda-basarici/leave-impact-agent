"""Source discipline: what a run asked of each source, how each read ended, and which recorded
operations are not what their tool declares.

Read off the trace alone, for every export that decodes, a failed attempt as much as a
completed one: a read that failed was still asked, and an attempt that ended by a fault
still spent its calls (the investigator milestone's fourth build step, ruling 5). Nothing
here needs the sealed world; the one join with it, whether the sources a scenario's answer
depends on were asked and answered, takes the key's sources as an argument.

One row per operation, and nothing stored is a count. A row says who asked (the frozen
prefetch, the harness under a registered policy, or the model), which tool, which source,
and how it ended. Every table is a
reading of the rows, as the claim tables are of theirs:

- *The per-source tally.* Completed reads (a record, no record, a sequence), unreachable
  and malformed, each by who asked. A source was *attempted* when any of those is recorded
  against it and *succeeded* when one completed. A refused call counts for no source, even
  one the wrapper had resolved a source for: no source was asked.
- *Refused calls*, over the operations the model asked for. A call the wrapper refused is
  a malformed tool request, the model's; a refused call of the prefetch, or of a read
  the harness issued under a policy, is the harness's own and is reported as a finding,
  never as model behaviour.
- *Model calls* by how each stands and how its last dispatch was read: the state
  (answered, failed, unresolved) beside the attribution (behaviour, infrastructure, defect,
  unresolved), every pair present. A service error read as the model's behaviour is a
  failed call counted under behaviour, so the tally never has to choose between what
  arrived and how it was read. A refused operation is a tool request the wrapper stopped,
  an operation's ending and no model call's.
- *Repeats.* A completed read with the tool and the arguments of an earlier completed one
  names the first such read. Whether a repeat was wasteful is not judged here: a second
  read after a suspected change is a legitimate pattern, and the count is what a table
  shows.

*Findings* name the operations a conforming harness cannot record. The operation type
holds no agreement between a tool and what was recorded for it, so that a broken export
decodes and can be reported; the coverage mapping refuses to credit such an operation,
and this is where it is said (``tool_mismatches``, the same checks). Two more that the
method table cannot state: a search that returned more documents than its limit, and a
refused prefetch call. Each names the operation and a kind, never content.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from leaveimpact.core.enums import Source
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.model_calls import AttributionKind, CallState
from leaveimpact.core.read_coverage import ToolMismatch, tool_mismatches
from leaveimpact.core.run_export import RunTrace
from leaveimpact.core.run_export_json import thawed_json
from leaveimpact.core.run_trace import (
    AbsentOutcome,
    DefectOutcome,
    HarnessOrigin,
    ModelOrigin,
    Operation,
    OperationId,
    Origin,
    Outcome,
    PrefetchOrigin,
    RecordOutcome,
    RecordsOutcome,
    RefusedCallOutcome,
    UnreachableOutcome,
)
from leaveimpact.core.tools import SEARCH_LIMIT, PortMethod, specification_named


class OriginKind(StrEnum):
    """Who asked for a read; a member is the wire format."""

    PREFETCH = "prefetch"
    HARNESS = "harness"
    MODEL = "model"


def origin_kind(origin: Origin) -> OriginKind:
    """Who asked for the read ``origin`` records."""
    match origin:
        case PrefetchOrigin():
            return OriginKind.PREFETCH
        case HarnessOrigin():
            return OriginKind.HARNESS
        case ModelOrigin():
            return OriginKind.MODEL


class Ended(StrEnum):
    """How an operation ended, the trace's six outcomes by name."""

    RECORD = "record"
    ABSENT = "absent"
    RECORDS = "records"
    UNREACHABLE = "unreachable"
    DEFECT = "defect"
    REFUSED = "refused"

    @property
    def completed(self) -> bool:
        """Whether the source answered: a record, no record, or a sequence."""
        return self in (Ended.RECORD, Ended.ABSENT, Ended.RECORDS)

    @property
    def asked_a_source(self) -> bool:
        """Whether a source was asked at all; a refused call asked none."""
        return self is not Ended.REFUSED


@dataclass(frozen=True, slots=True)
class OperationRow:
    """One operation of a trace as source discipline reads it.

    ``source`` is the one the operation is recorded against, whatever its tool reads.
    ``repeat_of`` names the earliest completed operation with this one's tool and
    arguments, set only on a completed read.
    """

    operation: OperationId
    origin: OriginKind
    tool: str
    source: Source | None
    ended: Ended
    repeat_of: OperationId | None = None


class OperationFindingKind(StrEnum):
    """What a conforming harness cannot record of an operation; a member is the wire format."""

    UNKNOWN_TOOL = "unknown_tool"
    SOURCE_NOT_THE_TOOLS = "source_not_the_tools"
    CARDINALITY_NOT_THE_TOOLS = "cardinality_not_the_tools"
    RECORD_KIND_NOT_THE_TOOLS = "record_kind_not_the_tools"
    ARGUMENTS_NOT_THE_TOOLS = "arguments_not_the_tools"
    MORE_THAN_THE_LIMIT = "more_than_the_limit"
    REFUSED_PREFETCH = "refused_prefetch"


_BY_MISMATCH = {
    ToolMismatch.UNKNOWN_TOOL: OperationFindingKind.UNKNOWN_TOOL,
    ToolMismatch.SOURCE: OperationFindingKind.SOURCE_NOT_THE_TOOLS,
    ToolMismatch.CARDINALITY: OperationFindingKind.CARDINALITY_NOT_THE_TOOLS,
    ToolMismatch.RECORD_KIND: OperationFindingKind.RECORD_KIND_NOT_THE_TOOLS,
    ToolMismatch.ARGUMENTS: OperationFindingKind.ARGUMENTS_NOT_THE_TOOLS,
}


@dataclass(frozen=True, slots=True)
class OperationFinding:
    """One thing an operation records that a conforming harness could not have: a harness
    finding, the model having no way to cause it."""

    operation: OperationId
    kind: OperationFindingKind


@dataclass(frozen=True, slots=True)
class OriginCount:
    """A count split by who asked."""

    prefetch: int
    harness: int
    model: int

    @property
    def total(self) -> int:
        return self.prefetch + self.harness + self.model


@dataclass(frozen=True, slots=True)
class SourceTally:
    """One source's reads by how they ended and who asked."""

    source: Source
    completed: OriginCount
    unreachable: OriginCount
    defect: OriginCount

    @property
    def attempted(self) -> bool:
        """Whether the source was asked at all, whatever came back."""
        return bool(self.completed.total or self.unreachable.total or self.defect.total)

    @property
    def succeeded(self) -> bool:
        """Whether the source answered at least one read."""
        return bool(self.completed.total)


@dataclass(frozen=True, slots=True)
class RequiredSourceUse:
    """Whether a source the scenario's answer depends on was asked, and whether it answered."""

    source: Source
    attempted: bool
    succeeded: bool


@dataclass(frozen=True, slots=True)
class SourceDiscipline:
    """What one trace shows of its reads and its model calls.

    ``operations`` holds one row per operation in the trace's order; ``model_calls`` the
    number of logical calls by state and by the attribution of the last dispatch, every
    pair present, in the declared order of both; ``findings`` are in the trace's order, an
    operation's own in the order of the kinds.
    """

    operations: tuple[OperationRow, ...]
    model_calls: tuple[tuple[CallState, AttributionKind, int], ...]
    findings: tuple[OperationFinding, ...]

    def tally(self, source: Source) -> SourceTally:
        """The reads recorded against ``source``."""

        def count(*ended: Ended) -> OriginCount:
            rows = [row for row in self.operations if row.source is source and row.ended in ended]
            by = [sum(row.origin is kind for row in rows) for kind in OriginKind]
            return OriginCount(*by)

        return SourceTally(
            source,
            completed=count(Ended.RECORD, Ended.ABSENT, Ended.RECORDS),
            unreachable=count(Ended.UNREACHABLE),
            defect=count(Ended.DEFECT),
        )

    @property
    def model_operations(self) -> int:
        """How many operations the model asked for, refused ones included."""
        return sum(row.origin is OriginKind.MODEL for row in self.operations)

    @property
    def refused_by_the_wrapper(self) -> int:
        """How many of the model's tool requests the wrapper refused: its malformed calls."""
        return sum(
            row.origin is OriginKind.MODEL and row.ended is Ended.REFUSED for row in self.operations
        )

    @property
    def repeats(self) -> tuple[OperationRow, ...]:
        """The completed reads that repeat an earlier one."""
        return tuple(row for row in self.operations if row.repeat_of is not None)

    def required_source_use(self, required: Sequence[Source]) -> tuple[RequiredSourceUse, ...]:
        """For each source in ``required``, the sources a key says its answer depends on,
        whether this run asked it and whether it answered; in ``required``'s order."""
        tallies = [self.tally(source) for source in required]
        return tuple(
            RequiredSourceUse(tally.source, tally.attempted, tally.succeeded) for tally in tallies
        )


def source_discipline(trace: RunTrace) -> SourceDiscipline:
    """What ``trace`` shows of its reads and its model calls.

    >>> from leaveimpact.core.run_ending import ClaimAuthor, ComposingPolicy, Composition
    >>> composed = Composition(ClaimAuthor.RULES, ComposingPolicy("policy", "0" * 64), (), ())
    >>> source_discipline(RunTrace((), (), (), composed)).tally(Source.JIRA).attempted
    False
    """
    rows: list[OperationRow] = []
    findings: list[OperationFinding] = []
    first_completed: dict[tuple[str, bytes], OperationId] = {}
    for operation in trace.operations:
        ended = _ended(operation.outcome)
        origin = origin_kind(operation.origin)
        repeat_of: OperationId | None = None
        if ended.completed:
            arguments = cast("JsonObject", thawed_json(operation.arguments))
            asked = (operation.tool, canonical_bytes(arguments))
            repeat_of = first_completed.get(asked)
            first_completed.setdefault(asked, operation.id)
        rows.append(
            OperationRow(operation.id, origin, operation.tool, operation.source, ended, repeat_of)
        )
        kinds = [_BY_MISMATCH[mismatch] for mismatch in tool_mismatches(operation)]
        if _returned_more_than_its_limit(operation):
            kinds.append(OperationFindingKind.MORE_THAN_THE_LIMIT)
        if ended is Ended.REFUSED and origin is not OriginKind.MODEL:
            kinds.append(OperationFindingKind.REFUSED_PREFETCH)
        findings.extend(OperationFinding(operation.id, kind) for kind in kinds)
    stands = [
        (call.state, call.dispatches[-1].attribution.kind) for call in trace.model_calls
    ]
    calls = tuple(
        (state, read_as, stands.count((state, read_as)))
        for state in CallState
        for read_as in AttributionKind
    )
    return SourceDiscipline(tuple(rows), calls, tuple(findings))


def _ended(outcome: Outcome) -> Ended:
    match outcome:
        case RecordOutcome():
            return Ended.RECORD
        case AbsentOutcome():
            return Ended.ABSENT
        case RecordsOutcome():
            return Ended.RECORDS
        case UnreachableOutcome():
            return Ended.UNREACHABLE
        case DefectOutcome():
            return Ended.DEFECT
        case RefusedCallOutcome():
            return Ended.REFUSED


def _returned_more_than_its_limit(operation: Operation) -> bool:
    """Whether a search came back with more documents than the limit it was called with."""
    specification = specification_named(operation.tool)
    outcome = operation.outcome
    if (
        specification is None
        or specification.method is not PortMethod.SEARCH
        or not isinstance(outcome, RecordsOutcome)
    ):
        return False
    limit = operation.arguments.get(SEARCH_LIMIT.name)
    return isinstance(limit, int) and not isinstance(limit, bool) and len(outcome.records) > limit


__all__ = [
    "Ended",
    "OperationFinding",
    "OperationFindingKind",
    "OperationRow",
    "OriginCount",
    "OriginKind",
    "RequiredSourceUse",
    "SourceDiscipline",
    "SourceTally",
    "origin_kind",
    "source_discipline",
]
