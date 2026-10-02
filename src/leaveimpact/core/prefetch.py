"""The frozen structured prefetch: what every system reads before anything else, as data, with
the planner that turns a run's context and the leave it read into calls, and the digest a
run's record names the rule by.

Every system under measurement opens with the same structured reads, so that what the
rules-only baseline and the agent know before any model call is the same evidence and the
comparison between them is about what each does with it (the investigator milestone's
fifth build step, ruling 5). The plan is a dependent one: read the leave the context names;
if it is returned, enumerate the employees, read the leaves overlapping the leave's own
span, enumerate the components and the work items, and read the events overlapping that
span as instants in the reference zone. The returned leave, never a sealed truth, supplies
the span; the context carries no window. No team, point-record or corpus read belongs
here: those are a system's own choices and are measured as such.

The specification and the planner are here in ``core`` because two parties need the same
one and may not import each other: the harness that executes the plan, and the evaluator
that checks a trace's conformance to it (the step after this one). Execution, the stop
rule after a source's first unreachable result, and the recording of each operation are
the harness's.

The exact span is the window: measured over twenty worlds, the leave's own days give the
oracle's answer in every scenario and a margin adds nothing. A span longer than a tool's
declared bound is split chronologically by the same bound the tool's validation applies,
read off the tool's own argument declaration so planner and validator cannot disagree:
inclusive, non-overlapping date chunks, and adjacent half-open instant chunks measured in
elapsed time, which is what the validator measures, so a chunk of thirty-one local days
across a clock change is never planned. Every planned call passes the tool's validation
unchanged; a plan that produced one that did not would be a defect of this module.

The record's prefetch-rule field holds a stable identifier and a digest over the
planner-protocol version, the ordered specification, and the contract of every tool the
plan names, a contract being the tool's model-facing definition together with its method
facts (the port method, the source, the kind of record, the cardinality), since those are
what coverage credits an operation by and the definition alone omits them, together with
the tool-surface digest of those tools, which binds the validation protocol a planned call
is accepted under and the result codec. A semantic change to the planner raises the
protocol version even when the steps read the same; a changed description, bound, method
fact, validation protocol or result codec moves the digest on its own.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from leaveimpact.core.entities import Leave
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.core.run_record import PrefetchRule
from leaveimpact.core.timeshape import encode_date_span, encode_instant
from leaveimpact.core.tools import (
    TOOL_SPECIFICATIONS,
    DateSpanArgument,
    InstantSpanArgument,
    ToolSpecification,
    specification_named,
    tool_definition,
    tool_surface_digest,
)
from leaveimpact.core.worldtime import DateSpan, InstantSpan, RunContext, as_utc

PREFETCH_IDENTIFIER = "leave-span-prefetch"
"""The stable name a run's record carries; the digest beside it says which version."""

PREFETCH_PROTOCOL = ("leave-span-prefetch", 1)
"""The planner's protocol and its version: raised on a semantic change to how the steps
are planned, chunked or ordered, whether or not the steps' text changes."""

ENVELOPE_VERSION = 1
"""The shape of what the digest hashes; bumped when the envelope's own shape changes."""


class ArgumentSource(StrEnum):
    """Where a step's arguments come from; a member is the specification's wire form."""

    NONE = "none"
    """An enumeration: the tool takes no argument."""
    CONTEXT_LEAVE_ID = "context_leave_id"
    """The id of the leave the run context names."""
    LEAVE_DAYS = "leave_days"
    """The returned leave's span, as inclusive calendar days."""
    LEAVE_INSTANTS = "leave_instants"
    """The returned leave's span, as the instants its days cover in the reference zone."""


@dataclass(frozen=True, slots=True)
class PrefetchStep:
    """One step of the plan: the tool and where its arguments come from."""

    tool: str
    arguments: ArgumentSource

    def __post_init__(self) -> None:
        if specification_named(self.tool) is None:
            raise ValueError(f"a prefetch step names a declared tool, got {self.tool!r}")


PREFETCH_STEPS: tuple[PrefetchStep, ...] = (
    PrefetchStep("leave", ArgumentSource.CONTEXT_LEAVE_ID),
    PrefetchStep("employees", ArgumentSource.NONE),
    PrefetchStep("leaves_within", ArgumentSource.LEAVE_DAYS),
    PrefetchStep("components", ArgumentSource.NONE),
    PrefetchStep("work_items", ArgumentSource.NONE),
    PrefetchStep("events_within", ArgumentSource.LEAVE_INSTANTS),
)
"""The six, in the order they are made; the first decides whether the rest are."""


@dataclass(frozen=True, slots=True)
class PlannedCall:
    """One call the plan makes: which step it serves, the tool, and the arguments spelled as
    the call carries them, so the tool's validation applies to them unchanged. A step whose
    span exceeds its tool's bound is several calls that share the step."""

    step: int
    tool: str
    arguments: JsonObject


def opening_call(context: RunContext) -> PlannedCall:
    """The plan's first call: the leave the context names, read by its id.

    >>> from datetime import UTC, datetime
    >>> from leaveimpact.core.ids import LeaveId, ScenarioId, WorldVersion
    >>> context = RunContext(
    ...     ScenarioId("scenario_003"), WorldVersion("4f2c"), LeaveId("leave_005"),
    ...     datetime(2026, 9, 14, 22, 30, tzinfo=UTC), "Europe/Istanbul",
    ... )
    >>> opening_call(context)
    PlannedCall(step=0, tool='leave', arguments={'id': 'leave_005'})
    """
    step = PREFETCH_STEPS[0]
    if step.arguments is not ArgumentSource.CONTEXT_LEAVE_ID:
        raise ValueError("the plan opens with the leave the context names")
    return PlannedCall(0, step.tool, {"id": context.leave_id})


def calls_after_leave(leave: Leave, reference_timezone: str) -> tuple[PlannedCall, ...]:
    """The rest of the plan once ``leave`` was returned: the remaining steps in order, a
    windowed step chunked by its tool's bound, the span the leave's own.

    The caller asks only when the opening call returned a leave; when it did not, the plan
    ends there and nothing here is called.
    """
    calls: list[PlannedCall] = []
    for index, step in enumerate(PREFETCH_STEPS[1:], start=1):
        match step.arguments:
            case ArgumentSource.NONE:
                calls.append(PlannedCall(index, step.tool, {}))
            case ArgumentSource.LEAVE_DAYS:
                name, bound = _span_argument(step.tool)
                calls.extend(
                    PlannedCall(index, step.tool, {name: encode_date_span(chunk)})
                    for chunk in day_chunks(leave.span, bound)
                )
            case ArgumentSource.LEAVE_INSTANTS:
                name, bound = _span_argument(step.tool)
                instants = leave.span.instants_in(reference_timezone)
                calls.extend(
                    PlannedCall(index, step.tool, {name: _encoded_instants(chunk)})
                    for chunk in instant_chunks(instants, bound)
                )
            case ArgumentSource.CONTEXT_LEAVE_ID:
                raise ValueError(f"step {index}: only the opening step reads the context's leave")
    return tuple(calls)


def day_chunks(span: DateSpan, max_days: int) -> tuple[DateSpan, ...]:
    """``span`` as consecutive, non-overlapping spans of at most ``max_days`` days each,
    inclusive at both ends, the first starting and the last ending where ``span`` does.

    >>> from datetime import date
    >>> [c.days for c in day_chunks(DateSpan(date(2026, 1, 1), date(2026, 1, 10)), 4)]
    [4, 4, 2]
    """
    if max_days < 1:
        raise ValueError(f"a chunk holds at least one day, got a bound of {max_days}")
    chunks: list[DateSpan] = []
    start = span.start
    while start <= span.end:
        end = min(start + timedelta(days=max_days - 1), span.end)
        chunks.append(DateSpan(start, end))
        start = end + timedelta(days=1)
    return tuple(chunks)


def instant_chunks(span: InstantSpan, max_days: int) -> tuple[InstantSpan, ...]:
    """``span`` as adjacent half-open spans of at most ``max_days`` days of elapsed time each,
    the first starting and the last ending where ``span`` does.

    Elapsed time, never wall-clock difference, which is how the tool's validation measures
    a span: a chunk cut by wall-clock days across a clock change could be an hour longer
    than the bound. Each chunk's ends are kept in ``span``'s own zone.
    """
    if max_days < 1:
        raise ValueError(f"a chunk holds at least one day, got a bound of {max_days}")
    chunks: list[InstantSpan] = []
    zone_of = span.start.tzinfo
    start = span.start
    end_utc = as_utc(span.end)
    while as_utc(start) < end_utc:
        end = min(as_utc(start) + timedelta(days=max_days), end_utc).astimezone(zone_of)
        chunks.append(InstantSpan(start, end))
        start = end
    return tuple(chunks)


def prefetch_digest(
    protocol: tuple[str, int],
    steps: Sequence[PrefetchStep],
    specifications: Sequence[ToolSpecification],
) -> str:
    """SHA-256 over the versioned envelope of the rule: the protocol, the ordered steps, the
    contract of each tool the steps name, in the order first named, and the tool-surface
    digest of those same tools.

    The surface digest carries what a contract's definition does not: the validation
    protocol a planned call is accepted under and the codec its result is rendered by,
    which a system's model sees of the prefetch. Only the named tools enter: a change to a
    tool the plan never calls is not a change to the plan. ``specifications`` must declare
    every tool the steps name.
    """
    declared = {specification.name: specification for specification in specifications}
    missing = [step.tool for step in steps if step.tool not in declared]
    if missing:
        raise ValueError(f"the prefetch names tools the surface does not declare: {missing}")
    named = list(dict.fromkeys(step.tool for step in steps))
    envelope: JsonObject = {
        "envelope_version": ENVELOPE_VERSION,
        "protocol": {"id": protocol[0], "version": protocol[1]},
        "steps": [{"tool": step.tool, "arguments": step.arguments.value} for step in steps],
        "tools": [_contract(declared[name]) for name in named],
        "surface": tool_surface_digest(tuple(declared[name] for name in named)),
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def prefetch_rule() -> PrefetchRule:
    """The rule as a run's record carries it: the identifier and the digest of the plan as it
    is declared here over the thirteen tools."""
    return PrefetchRule(
        PREFETCH_IDENTIFIER, prefetch_digest(PREFETCH_PROTOCOL, PREFETCH_STEPS, TOOL_SPECIFICATIONS)
    )


def _contract(specification: ToolSpecification) -> JsonObject:
    """What a tool is to the plan: its definition, and the method facts the definition omits."""
    facts = specification.facts
    return {
        "definition": tool_definition(specification),
        "method": {
            "port_method": specification.method.value,
            "family": facts.family.value,
            "source": facts.source.value,
            "entity_kind": facts.entity_kind.value,
            "cardinality": facts.cardinality.value,
        },
    }


def _span_argument(tool: str) -> tuple[str, int]:
    """The name and the bound of the one span argument of ``tool``, read off its declaration."""
    specification = specification_named(tool)
    assert specification is not None, tool
    spans = [
        argument
        for argument in specification.arguments
        if isinstance(argument, DateSpanArgument | InstantSpanArgument)
    ]
    if len(spans) != 1:
        raise ValueError(f"{tool}: a windowed step's tool declares one span argument")
    return spans[0].name, spans[0].max_days


def _encoded_instants(span: InstantSpan) -> JsonObject:
    return {"start": encode_instant(span.start), "end": encode_instant(span.end)}


__all__ = [
    "ENVELOPE_VERSION",
    "PREFETCH_IDENTIFIER",
    "PREFETCH_PROTOCOL",
    "PREFETCH_STEPS",
    "ArgumentSource",
    "PlannedCall",
    "PrefetchStep",
    "calls_after_leave",
    "day_chunks",
    "instant_chunks",
    "opening_call",
    "prefetch_digest",
    "prefetch_rule",
]
