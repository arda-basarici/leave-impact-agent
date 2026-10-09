"""The one path for a declared tool call: validate, resolve the port and the method, call, record
one operation with one of the six outcomes, and remember which sources have stopped.

Every read a system makes goes through here, the frozen prefetch now and the model's tool
calls when the registry arrives (the investigator milestone's fifth build step, the build
design's third call): one executor, so the operation the trace records is made the same
way whoever asked, and the fault triad keeps its meanings in one place. The specifications,
the method table, the validation and the surface digest are ``core``'s; this module binds
them to live ports and has the effects.

What a call does, in order. The tool's specification is looked up by name; the arguments
are validated into domain values; the port is the one the method's family names and the
method the one the specification names; the answer becomes an outcome: a record, no
record, a sequence, the source unreachable, or a record the adapter could not translate.
Nothing else is caught, on purpose: ``SourceUnreachable`` and ``MalformedRecord`` share no
base so that no clause here can fold a defect into a legitimate unknown, and anything else
is a fault of this harness and propagates as one. One operation is appended with the
arguments exactly as they were given, so the accepted arguments are the effective ones,
and with the source the method table names, so an absent answer still says which source
it is absent from.

Who asked decides what a refusal is. A call the model made with an unknown tool, a tool
outside the surface it was given, or arguments the validation refuses is a refused call,
recorded as one and answered as one: the model's behaviour, graded. A call the frozen
prefetch made that fails validation is a defect of this harness and raises, since the
planner reads its bounds off the same declarations the validator applies and the two
cannot honestly disagree.

The surface is the executor's (the registry step, fork 9): the prefetch runs over the
harness's own, all thirteen, and the tools node builds its executor over the role's, so a
known tool the role is not shown is refused at execution and never resolved through the
global table. The recorded refusal is the detail, which names the tool or the value the
model gave; what the model is shown is the closed correction the rendering derives from
the same declarations (``agent.surface``).

The first unreachable outcome at a source stops it for the rest of the run (DESIGN's
runtime policy): facts already read stand, and no further operation is attempted against
it. The prefetch honours that by not asking. A model's call against a stopped source is
the graph's decision, made before this executor is asked: the tools node appends a skip
with the unreachable reason, durable and honoured on replay (the event log step), and the
rendering shows the model the source as unreachable. A call that reaches here against a
stopped source is therefore a caller's error and raises.

The prefetch runs over the executor as the plan says: the opening read of the leave the
context names; on the leave asked for, the remaining calls in order, each skipped when its
source has stopped, and none after a malformed record, since the run fails by defect at
that operation and the reads the plan would have made after it are not made; a leave not
returned, returned absent, or returned as another record ends the plan at the first
operation. What an ending means is the system's to conclude from the trace, not this
module's.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from itertools import count
from typing import cast

from leaveimpact.core.entities import Leave
from leaveimpact.core.enums import Source
from leaveimpact.core.ports.errors import MalformedRecord, SourceUnreachable
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.ports.read import (
    CalendarReader,
    DocumentReader,
    PeopleReader,
    WorkReader,
)
from leaveimpact.core.prefetch import PlannedCall, calls_after_leave, opening_call
from leaveimpact.core.run_trace import (
    AbsentOutcome,
    DefectOutcome,
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
from leaveimpact.core.tools import (
    TOOL_SPECIFICATIONS,
    PortFamily,
    ToolSpecification,
    specification_named,
    validate_arguments,
)
from leaveimpact.core.worldtime import RunContext


@dataclass(frozen=True, slots=True)
class ReadPorts:
    """The four readers a run reads through, one per system."""

    people: PeopleReader
    work: WorkReader
    calendar: CalendarReader
    documents: DocumentReader

    def port(self, family: PortFamily) -> object:
        """The reader a tool of ``family`` calls."""
        match family:
            case PortFamily.PEOPLE:
                return self.people
            case PortFamily.WORK:
                return self.work
            case PortFamily.CALENDAR:
                return self.calendar
            case PortFamily.DOCUMENT:
                return self.documents


def sequential_ids(prefix: str = "op") -> Callable[[], OperationId]:
    """Operation ids ``prefix-1``, ``prefix-2``, ... in call order: what a run uses until the
    event log assigns them."""
    numbers = count(1)
    return lambda: OperationId(f"{prefix}-{next(numbers)}")


@dataclass
class Executor:
    """The declared tool calls of one run, made against ``ports`` and kept in order.

    ``operations`` holds every call made, refused ones included, in the order made;
    ``stopped`` the sources whose first unreachable outcome has been seen.
    """

    ports: ReadPorts
    next_id: Callable[[], OperationId] = field(default_factory=sequential_ids)
    surface: tuple[ToolSpecification, ...] = field(default=TOOL_SPECIFICATIONS, kw_only=True)
    operations: list[Operation] = field(default_factory=list[Operation])
    stopped: set[Source] = field(default_factory=set[Source])

    def call(self, origin: Origin, tool: str, arguments: Mapping[str, object]) -> Outcome:
        """Make the call ``tool`` with ``arguments`` for ``origin``, record it, and answer with
        its outcome.

        Raises ``ValueError`` for a prefetch-origin call the validation refuses or whose tool
        is not in ``surface``, and for any call against a source that has stopped; a
        model-origin call with those faults is recorded as refused. Raises nothing for what a
        source answered.
        """
        given = dict(arguments)
        specification = specification_named(tool, self.surface)
        if specification is None:
            known = specification_named(tool) is not None
            detail = (
                f"{tool!r} is not one of this role's tools" if known else f"no tool named {tool!r}"
            )
            return self._record(origin, tool, None, given, self._refused(origin, detail))
        source = specification.facts.source
        try:
            accepted = validate_arguments(specification, given)
        except ValueError as refused:
            return self._record(origin, tool, source, given, self._refused(origin, str(refused)))
        if source in self.stopped:
            raise ValueError(f"{source.value} has stopped for this run; no call is made against it")
        outcome = self._ask(specification, accepted)
        if isinstance(outcome, UnreachableOutcome):
            self.stopped.add(source)
        return self._record(origin, tool, source, given, outcome)

    def _ask(self, specification: ToolSpecification, accepted: Mapping[str, object]) -> Outcome:
        method = getattr(self.ports.port(specification.facts.family), specification.method.value)
        try:
            answer: object = method(**accepted)
        except SourceUnreachable as unreachable:
            return UnreachableOutcome(unreachable.source, unreachable.reason)
        except MalformedRecord as malformed:
            return DefectOutcome(malformed.source, malformed.locator, malformed.reason)
        if answer is None:
            return AbsentOutcome()
        if isinstance(answer, tuple):
            records = cast("tuple[Observed[Entity], ...]", answer)
            return RecordsOutcome(tuple(_as_returned(record) for record in records))
        return RecordOutcome(_as_returned(cast("Observed[Entity]", answer)))

    def _refused(self, origin: Origin, reason: str) -> RefusedCallOutcome:
        if isinstance(origin, PrefetchOrigin):
            raise ValueError(f"the frozen prefetch made a call the surface refuses: {reason}")
        return RefusedCallOutcome(reason)

    def _record(
        self,
        origin: Origin,
        tool: str,
        source: Source | None,
        arguments: Mapping[str, object],
        outcome: Outcome,
    ) -> Outcome:
        # The position is the order the calls were made in, from one: what a run with no event
        # log has for it. A logged run's positions are the log's.
        position = len(self.operations) + 1
        self.operations.append(
            Operation(self.next_id(), origin, tool, source, arguments, outcome, position)
        )
        return outcome


def _as_returned(record: Observed[Entity]) -> Observed[Entity]:
    """``record`` typed as an operation's outcome holds it: any entity, from its source."""
    return Observed[Entity](record.value, record.source)


@dataclass(frozen=True, slots=True)
class PrefetchResult:
    """How the prefetch ended: what the opening read of the leave returned, and the leave when
    the record returned is the one the context asked for."""

    opening: Outcome
    leave: Leave | None


def run_prefetch(
    executor: Executor, context: RunContext, *, halted: Callable[[], bool] = lambda: False
) -> PrefetchResult:
    """The frozen prefetch of ``context`` over ``executor``: the opening read, then on the leave
    asked for the planned calls in order, each at most once, none against a stopped source,
    none after a defect, since a malformed record fails the run at that operation, and none
    once ``halted`` answers true, which the graph reads off the log's recorded stop between
    calls so a defect the transition derives ends the prefetch before the next port call."""
    first = opening_call(context)
    opening = executor.call(PrefetchOrigin(), first.tool, first.arguments)
    leave = leave_asked_for(opening, context)
    if leave is None:
        return PrefetchResult(opening, None)
    for planned in calls_after_leave(leave, context.reference_timezone):
        if halted():
            break
        if _source_of(planned) in executor.stopped:
            continue
        outcome = executor.call(PrefetchOrigin(), planned.tool, planned.arguments)
        if isinstance(outcome, DefectOutcome):
            break
    return PrefetchResult(opening, leave)


def leave_asked_for(opening: Outcome, context: RunContext) -> Leave | None:
    """The leave ``context`` names when ``opening`` returned exactly that record: the
    one rule for what a run investigates, read by the prefetch here and by the
    conclusion module off the first logged operation."""
    if not isinstance(opening, RecordOutcome):
        return None
    record = opening.record.value
    if isinstance(record, Leave) and record.id == context.leave_id:
        return record
    return None


def _source_of(planned: PlannedCall) -> Source:
    specification = specification_named(planned.tool)
    assert specification is not None, planned.tool
    return specification.facts.source


__all__ = [
    "Executor",
    "PrefetchResult",
    "ReadPorts",
    "leave_asked_for",
    "run_prefetch",
    "sequential_ids",
]
