"""What the model sees of its reads: the role's tool definitions as the client sends them, each
operation's result as one envelope stamped with the run's ``now``, and the correction a
refused call is answered with.

The specifications, the validation and the digest are ``core``'s declarations; this module
is the rendering the registry step owed (fork 2), with the effects of neither a port nor a
log: pure functions from the logged resolution of an operation to the content a Converse
``toolResult`` block carries, so the turns that build a request (the graph step's) and a
test that captures what leaves the machine compose the same bytes. It renders from the log's
own form of a resolution, never from an in-process outcome, so a request rebuilt by a
recovering worker is byte-equal to the one the first process sent; the executor appends
before it returns, and the logged form is always there.

*The stamp.* No tool takes a date and what a read returns is not filtered by date (DESIGN,
the tool paragraph); the envelope stamps every result with the admitted ``RunContext.now``,
the simulated observation time, so the model reads every record as of one instant and the
rules read the same stamp. A record, a sequence, an absence, an unreachable source and a
refusal carry the stamp alike (the step's rendering acceptance), each under its own key.

*What is never rendered.* A defect is not: the run fails at that operation and the model
gets no further turn. The adapter's reason for an unreachable source is not: it is the
vendor's text and may name a host. A model-chosen string is not: a refused call is answered
with the closed correction built from the declarations (fork 4), derived here by running the
validation again on the logged arguments, so first execution and recovery take one path
and the detail that echoes the value stays in the log; and the envelope names the tool only
when the role's surface declares it, so an unknown name the model wrote is not written back.

*The harness's own tool.* The fact tool's definition is generated from the parser's entry
schema, one object, so the schema the model is shown and the schema the parser reads cannot
differ (the graph step, fork 12); it joins the read tools in the surface digest. What the
harness answers a fact call with is the batch's derived admissions, per entry by index and
reason code and the count of each, never an entry's text; a payload that is no batch at all
is answered with the parser's one correction. An unparsed call (its input no object) is
answered with a fixed correction, and a call the stop reason or the cap left undispatched
with ``not_made`` and its reason, so every ``toolUse`` of an assistant message has its
``toolResult`` in the next user message (forks 5 and 6, amendment 4). Each is stamped and
derived from the log like a read's envelope, so recovery renders the same bytes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from leaveimpact.adapters.converse import converse_tool
from leaveimpact.agent.answer_parse import FACT_TOOL
from leaveimpact.agent.fact_entries import ENTRY_SCHEMA
from leaveimpact.agent.log_events import OperationResult, OperationSkip
from leaveimpact.core.entities_json import encode_observed
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.model_calls import (
    FactBatch,
    MalformedBatch,
    ParsedBatch,
    UndispatchedReason,
)
from leaveimpact.core.run_trace import (
    AbsentOutcome,
    DefectOutcome,
    RecordOutcome,
    RecordsOutcome,
    RefusedCallOutcome,
    UnreachableOutcome,
)
from leaveimpact.core.stated import Admitted, Refused, RefusedInput
from leaveimpact.core.timeshape import encode_instant
from leaveimpact.core.tools import (
    ArgumentsRefused,
    Role,
    ToolSpecification,
    role_surface,
    specification_named,
    surface_correction,
    tool_definition,
    tool_surface_digest,
    validate_arguments,
)
from leaveimpact.core.worldtime import RunContext

FACT_TOOL_DEFINITION: JsonObject = {
    "name": FACT_TOOL,
    "description": (
        "State every fact of the four kinds that the free text of the records asserts, each "
        "with the exact words that assert it."
    ),
    "input_schema": ENTRY_SCHEMA,
}
"""The fact tool as the model is given it: the parser's own schema under the one name, so
what is shown and what is parsed are one object. The description enters the surface digest
with the read tools' descriptions."""

HARNESS_TOOLS: tuple[JsonObject, ...] = (FACT_TOOL_DEFINITION,)
"""The definitions of the tools the harness answers itself, shown beside the read tools:
the fact tool."""

FACT_CORRECTION = f"{FACT_TOOL}'s arguments are a JSON object holding facts, a list of entries"
"""The one correction a fact call whose payload is no batch at all is answered with."""

ARGUMENTS_CORRECTION = "the arguments of a tool call are a JSON object"
"""The one correction an unparsed call is answered with; nothing of what it wrote is echoed."""


def converse_tools(role: Role) -> tuple[JsonObject, ...]:
    """``role``'s read tools as Converse ``toolConfig.tools`` entries, in the canonical order,
    the order the digest hashes."""
    return tuple(converse_tool(tool_definition(s)) for s in role_surface(role))


def converse_harness_tools() -> tuple[JsonObject, ...]:
    """The harness's own tools as Converse entries, in the order the digest hashes them."""
    return tuple(converse_tool(definition) for definition in HARNESS_TOOLS)


def surface_digest(role: Role) -> str:
    """The digest of what ``role``'s model sees, over the read tools and the harness tools."""
    return tool_surface_digest(role_surface(role), HARNESS_TOOLS)


@dataclass(frozen=True, slots=True)
class RenderedResult:
    """What one operation shows the model: the envelope, and whether Converse marks it an
    error (a refusal, an unreachable source, a call not made)."""

    content: JsonObject
    status: Literal["success", "error"]

    def block(self, tool_use_id: str) -> JsonObject:
        """The ``toolResult`` content block answering the ``toolUse`` with ``tool_use_id``, as
        the client sends it."""
        return {
            "toolResult": {
                "toolUseId": tool_use_id,
                "content": [{"json": self.content}],
                "status": self.status,
            }
        }


def render_result(
    resolution: OperationResult | OperationSkip,
    *,
    tool: str,
    surface: tuple[ToolSpecification, ...],
    context: RunContext,
) -> RenderedResult:
    """The envelope for the call of ``tool`` the log resolved as ``resolution``, under the
    role's ``surface`` and the run's ``context``.

    ``ValueError`` for a defect (never rendered), for a result logged under another tool
    than ``tool``, and for a skip of a tool the surface does not declare (the tools node
    refuses such a call instead of skipping it).
    """
    specification = specification_named(tool, surface)
    envelope = _stamped(specification, context)
    match resolution:
        case OperationSkip(reason=reason):
            return render_undispatched(reason, tool=tool, surface=surface, context=context)
        case OperationResult():
            pass
    if resolution.tool != tool:
        raise ValueError(f"the result logged is {resolution.tool!r}'s, asked to render {tool!r}")
    envelope["source"] = None if resolution.source is None else resolution.source.value
    match resolution.outcome:
        case RecordOutcome(record=record):
            envelope["record"] = encode_observed(record)
            return RenderedResult(envelope, "success")
        case RecordsOutcome(records=records):
            envelope["records"] = [encode_observed(record) for record in records]
            return RenderedResult(envelope, "success")
        case AbsentOutcome():
            envelope["absent"] = True
            return RenderedResult(envelope, "success")
        case UnreachableOutcome(source=source):
            envelope["unreachable"] = {"source": source.value}
            return RenderedResult(envelope, "error")
        case RefusedCallOutcome():
            envelope["refused"] = {
                "correction": correction_for(surface, tool, resolution.arguments)
            }
            return RenderedResult(envelope, "error")
        case DefectOutcome():
            raise ValueError("a defect is never rendered: the run fails at that operation")


def render_undispatched(
    reason: UndispatchedReason,
    *,
    tool: str,
    surface: tuple[ToolSpecification, ...],
    context: RunContext,
) -> RenderedResult:
    """The envelope for a call of ``tool`` that was never dispatched for ``reason``: an
    unreachable source as the source, any other reason as ``not_made``. ``ValueError`` for
    an unreachable skip of a tool the surface does not declare (the tools node refuses such
    a call instead of skipping it)."""
    specification = specification_named(tool, surface)
    envelope = _stamped(specification, context)
    if reason is UndispatchedReason.SOURCE_UNREACHABLE:
        if specification is None:
            raise ValueError(f"a skip of a tool the surface does not declare: {tool!r}")
        source = specification.facts.source
        envelope["source"] = source.value
        envelope["unreachable"] = {"source": source.value}
        return RenderedResult(envelope, "error")
    envelope["not_made"] = {"reason": reason.value}
    return RenderedResult(envelope, "error")


def render_unparsed(
    *, tool: str, surface: tuple[ToolSpecification, ...], context: RunContext
) -> RenderedResult:
    """The envelope for a call of ``tool`` whose input was no object: the fixed correction,
    nothing of the input echoed."""
    envelope = _stamped(specification_named(tool, surface), context)
    envelope["refused"] = {"correction": ARGUMENTS_CORRECTION}
    return RenderedResult(envelope, "error")


def render_fact_result(batch: FactBatch, *, context: RunContext) -> RenderedResult:
    """The envelope for a fact call the harness handled as ``batch``: per entry, by index,
    whether it was admitted or the reason code it was refused under, and the count of each;
    never an entry's text. A malformed batch is an error with the parser's one correction."""
    envelope = _stamped(None, context)
    envelope["tool"] = FACT_TOOL
    match batch:
        case MalformedBatch():
            envelope["refused"] = {"correction": FACT_CORRECTION}
            return RenderedResult(envelope, "error")
        case ParsedBatch(entries=entries):
            pass
    rendered: list[JsonObject] = []
    counts: dict[str, int] = {}
    for index, entry in enumerate(entries):
        match entry:
            case Admitted():
                verdict = "admitted"
                rendered.append({"index": index, "admitted": True})
            case Refused(reason=reason) | RefusedInput(reason=reason):
                verdict = reason.value
                rendered.append({"index": index, "refused": verdict})
        counts[verdict] = counts.get(verdict, 0) + 1
    envelope["entries"] = rendered
    envelope["counts"] = dict(sorted(counts.items()))
    return RenderedResult(envelope, "success")


def _stamped(specification: ToolSpecification | None, context: RunContext) -> dict[str, object]:
    envelope: dict[str, object] = {"observed_at": encode_instant(context.now)}
    if specification is not None:
        envelope["tool"] = specification.name
    return envelope


def correction_for(
    surface: tuple[ToolSpecification, ...], tool: str, arguments: Mapping[str, object]
) -> str:
    """The one correction a refused call of ``tool`` with ``arguments`` is answered with: the
    surface's when the tool is not among it, else the validation's for the first argument
    refused. ``ValueError`` when the surface accepts the call, since a logged refusal the
    declarations do not reproduce means the two disagree."""
    specification = specification_named(tool, surface)
    if specification is None:
        return surface_correction(surface)
    try:
        validate_arguments(specification, dict(arguments))
    except ArgumentsRefused as refused:
        return refused.correction
    raise ValueError(
        f"the log holds a refusal of {tool!r} the declarations accept; the two disagree"
    )
