"""The fourteen read tools as declarations: the name, the arguments, the one port method each is.

A tool is one typed specification naming exactly one read-port method, the model's
schema generated from it, and the tool makes no domain decision (the investigator
milestone's second build step, ruling 6, after the M2-entry registry ruling). The
declarations live here in ``core`` as plain data because the harness that constructs
the tools and the evaluator that verifies a trace's operations against them may not
import each other; everything with an effect, the port binding, the logging, the
wrapper that renders a result, stays in ``agent`` and binds to these at the registry
step. What a specification holds is exactly what the model can see, which is why the
tool-surface digest below is a digest of the specifications' generated definitions.

One table is the authority for a method's facts: its family, the source it reads, the
kind of record it returns and whether it returns one or a sequence. A specification
names the method and adds the model-facing name, the description and the argument
declarations with their bounds, so no specification can contradict its method, and
ruling 3's per-operation source is derived from the table rather than stated twice.
The fourteen are declared in one explicit canonical order, the order a role's registry
preserves and sends, never the order a file happens to list them in.

Validation is one generic function over the declarations: an exact JSON object with
exactly the declared arguments, no coercion and no default (every argument is required,
the search limit included, so the arguments a call was accepted with are the arguments
it ran with), ids through the one id rule, dates and instants through the one spelling
rule, spans with their ordering and a maximum length, the query non-blank and bounded,
booleans never integers. A refusal names the argument. The bounds' numbers live in the
declarations and reach the preregistration through the digest, so a changed bound is a
visibly changed surface.

A refusal is typed (the registry step, fork 4): beside the detail that names the value
given, which the log and the export keep, it carries the one correction the model is
shown, built from the declaration and the argument's name and never from the value. A
model's argument is text the model chose, so a message that echoed it could carry
anything the model wrote back into its own context; the correction set is closed and
enumerable (``correction_messages``), which is what lets the request capture prove, not
sample, that nothing of the world reaches the model through an error.

The registry declares per role which methods become tools, so a tool list is constructed
and never prompted (DESIGN, the tool paragraph). Two roles exist. The reader, which the
two one-call baselines share, is shown no read tool at all. The investigator's list is the
ten without the four whole-table enumerations. Three of those the frozen
prefetch reads and the system's turns render into the model's context before the first
call, so a model call to one would be a whole-table re-read with nothing to discover (the
registry step, fork 1); that ties the list to the prefetch's steps on purpose and by name,
and a prefetch change that drops an enumeration reopens the list. The fourth, the corpus
enumeration, exists for the full-context baseline's one harness read (the baselines step,
fork 8) and would hand the investigator the whole corpus in one call, which is that
baseline and not the agent.

The tool-surface digest hashes a versioned envelope of what a role's model sees: its
ordered generated definitions, the definitions of the harness's own tools the role is
shown beside them (the fact tool, since the graph step), and the identifiers and versions
of the result codec and the validation protocol, since a change in how results are
rendered or calls are refused is a change the model sees as much as a changed description
is. It names the
semantic surface, not provider wire bytes, which a framework may translate before the
request leaves. Nothing invisible enters it.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import assert_never

from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.jsonshape import JsonObject, as_object, canonical_bytes, expect_fields
from leaveimpact.core.refs import PREFIX_BY_KIND, require_id, with_article
from leaveimpact.core.run_trace import require_integer, require_opaque_id
from leaveimpact.core.timeshape import decode_date_span, decode_instant
from leaveimpact.core.worldtime import InstantSpan

TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]*\Z")  # ``\Z``: ``$`` would admit a trailing newline

SURFACE_VERSION = 2
"""The envelope the digest hashes; bumped when the envelope's own shape changes (2: the
harness's own tool definitions joined it, the registry step)."""

RESULT_CODEC = ("observed-envelope", 1)
"""The identifier and version of how a result is rendered to the model: one envelope per
operation stamped with the run's ``now``, holding the entity codec's observed record, the
records, the absence or the unreachability (the registry step, fork 2; before it,
``observed-record`` 1 named the bare record); a change in that rendering is a change the
model sees."""

VALIDATION_PROTOCOL = ("exact-json-object", 2)
"""The identifier and version of how a call is accepted or refused (2: the refusal the
model is shown is the closed correction, not the detail that echoes the value)."""


# --- The method table ----------------------------------------------------------------


class PortFamily(StrEnum):
    """The four read protocols, one per system."""

    PEOPLE = "people"
    WORK = "work"
    CALENDAR = "calendar"
    DOCUMENT = "document"


class Cardinality(StrEnum):
    """Whether a method answers with one record (or none) or with a sequence."""

    SINGLE = "single"
    SEQUENCE = "sequence"


class PortMethod(StrEnum):
    """The fourteen read-port methods, the closed set a tool may name."""

    EMPLOYEE = "employee"
    EMPLOYEES = "employees"
    TEAM = "team"
    LEAVE = "leave"
    LEAVES_WITHIN = "leaves_within"
    WORK_ITEM = "work_item"
    WORK_ITEMS = "work_items"
    COMPONENT = "component"
    COMPONENTS = "components"
    EVENT = "event"
    EVENTS_WITHIN = "events_within"
    DOCUMENT = "document"
    DOCUMENTS = "documents"
    SEARCH = "search"


@dataclass(frozen=True, slots=True)
class MethodFacts:
    """What a method is: its family, the source it reads, what it returns and how many."""

    family: PortFamily
    source: Source
    entity_kind: EntityKind
    cardinality: Cardinality


METHOD_TABLE: Mapping[PortMethod, MethodFacts] = MappingProxyType(
    {
        PortMethod.EMPLOYEE: MethodFacts(
            PortFamily.PEOPLE, Source.FRAPPE, EntityKind.EMPLOYEE, Cardinality.SINGLE
        ),
        PortMethod.EMPLOYEES: MethodFacts(
            PortFamily.PEOPLE, Source.FRAPPE, EntityKind.EMPLOYEE, Cardinality.SEQUENCE
        ),
        PortMethod.TEAM: MethodFacts(
            PortFamily.PEOPLE, Source.FRAPPE, EntityKind.TEAM, Cardinality.SINGLE
        ),
        PortMethod.LEAVE: MethodFacts(
            PortFamily.PEOPLE, Source.FRAPPE, EntityKind.LEAVE, Cardinality.SINGLE
        ),
        PortMethod.LEAVES_WITHIN: MethodFacts(
            PortFamily.PEOPLE, Source.FRAPPE, EntityKind.LEAVE, Cardinality.SEQUENCE
        ),
        PortMethod.WORK_ITEM: MethodFacts(
            PortFamily.WORK, Source.JIRA, EntityKind.WORK_ITEM, Cardinality.SINGLE
        ),
        PortMethod.WORK_ITEMS: MethodFacts(
            PortFamily.WORK, Source.JIRA, EntityKind.WORK_ITEM, Cardinality.SEQUENCE
        ),
        PortMethod.COMPONENT: MethodFacts(
            PortFamily.WORK, Source.JIRA, EntityKind.COMPONENT, Cardinality.SINGLE
        ),
        PortMethod.COMPONENTS: MethodFacts(
            PortFamily.WORK, Source.JIRA, EntityKind.COMPONENT, Cardinality.SEQUENCE
        ),
        PortMethod.EVENT: MethodFacts(
            PortFamily.CALENDAR, Source.CALENDAR, EntityKind.EVENT, Cardinality.SINGLE
        ),
        PortMethod.EVENTS_WITHIN: MethodFacts(
            PortFamily.CALENDAR, Source.CALENDAR, EntityKind.EVENT, Cardinality.SEQUENCE
        ),
        PortMethod.DOCUMENT: MethodFacts(
            PortFamily.DOCUMENT, Source.CORPUS, EntityKind.DOCUMENT, Cardinality.SINGLE
        ),
        PortMethod.DOCUMENTS: MethodFacts(
            PortFamily.DOCUMENT, Source.CORPUS, EntityKind.DOCUMENT, Cardinality.SEQUENCE
        ),
        PortMethod.SEARCH: MethodFacts(
            PortFamily.DOCUMENT, Source.CORPUS, EntityKind.DOCUMENT, Cardinality.SEQUENCE
        ),
    }
)
"""The single authority for each method's facts; a specification names a method and adds
nothing a reader could contradict with."""


# --- Argument declarations --------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdArgument:
    """An id of one entity kind, in that kind's namespace."""

    name: str
    kind: EntityKind


@dataclass(frozen=True, slots=True)
class IntegerArgument:
    """An exact integer within inclusive bounds."""

    name: str
    minimum: int
    maximum: int

    def __post_init__(self) -> None:
        require_integer(self.minimum, f"{self.name}: minimum", minimum=None)
        require_integer(self.maximum, f"{self.name}: maximum", minimum=None)
        if self.minimum > self.maximum:
            raise ValueError(
                f"{self.name}: the bounds are ordered, got {self.minimum}..{self.maximum}"
            )


@dataclass(frozen=True, slots=True)
class DateSpanArgument:
    """A span of calendar days, inclusive at both ends, at most ``max_days`` long."""

    name: str
    max_days: int

    def __post_init__(self) -> None:
        require_integer(self.max_days, f"{self.name}: max_days", minimum=1)


@dataclass(frozen=True, slots=True)
class InstantSpanArgument:
    """A half-open span of instants in the canonical zoned shape, at most ``max_days`` long."""

    name: str
    max_days: int

    def __post_init__(self) -> None:
        require_integer(self.max_days, f"{self.name}: max_days", minimum=1)


@dataclass(frozen=True, slots=True)
class QueryArgument:
    """Free text for a search: non-blank, at most ``max_length`` characters."""

    name: str
    max_length: int

    def __post_init__(self) -> None:
        require_integer(self.max_length, f"{self.name}: max_length", minimum=1)


type Argument = (
    IdArgument | IntegerArgument | DateSpanArgument | InstantSpanArgument | QueryArgument
)


# --- The specification --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolSpecification:
    """One tool: its model-facing name and description, the method it is, its arguments.

    >>> ToolSpecification("Leave", "a leave by id", PortMethod.LEAVE, ())
    Traceback (most recent call last):
    ...
    ValueError: a tool name is lower-case words joined by underscores, got 'Leave'
    """

    name: str
    description: str
    method: PortMethod
    arguments: tuple[Argument, ...]

    def __post_init__(self) -> None:
        if not TOOL_NAME.match(self.name):
            raise ValueError(
                f"a tool name is lower-case words joined by underscores, got {self.name!r}"
            )
        if not self.description.strip():
            raise ValueError(f"{self.name}: a tool is described")
        names = [argument.name for argument in self.arguments]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.name}: an argument is declared once, got {names}")
        for name in names:
            require_opaque_id(name, f"{self.name}: an argument name")

    @property
    def facts(self) -> MethodFacts:
        """The method's facts from the one table."""
        return METHOD_TABLE[self.method]


SEARCH_LIMIT = IntegerArgument("limit", 1, 20)
"""The search's bounded top-k; the number is the specification's and reaches the
preregistration through the digest."""

TOOL_SPECIFICATIONS: tuple[ToolSpecification, ...] = (
    ToolSpecification(
        "employee",
        "One employee as the HR system records them, by employee id.",
        PortMethod.EMPLOYEE,
        (IdArgument("id", EntityKind.EMPLOYEE),),
    ),
    ToolSpecification(
        "employees",
        "Every employee the HR system holds.",
        PortMethod.EMPLOYEES,
        (),
    ),
    ToolSpecification(
        "team",
        "One organizational team, by team id.",
        PortMethod.TEAM,
        (IdArgument("id", EntityKind.TEAM),),
    ),
    ToolSpecification(
        "leave",
        "One leave record as the HR system holds it, by leave id.",
        PortMethod.LEAVE,
        (IdArgument("id", EntityKind.LEAVE),),
    ),
    ToolSpecification(
        "leaves_within",
        "Every leave overlapping a span of calendar days, inclusive at both ends.",
        PortMethod.LEAVES_WITHIN,
        (DateSpanArgument("span", 366),),
    ),
    ToolSpecification(
        "work_item",
        "One tracker work item with its comments, by work item id.",
        PortMethod.WORK_ITEM,
        (IdArgument("id", EntityKind.WORK_ITEM),),
    ),
    ToolSpecification(
        "work_items",
        "Every work item the tracker holds.",
        PortMethod.WORK_ITEMS,
        (),
    ),
    ToolSpecification(
        "component",
        "One tracker component with its member ids, by component id.",
        PortMethod.COMPONENT,
        (IdArgument("id", EntityKind.COMPONENT),),
    ),
    ToolSpecification(
        "components",
        "Every component the tracker holds.",
        PortMethod.COMPONENTS,
        (),
    ),
    ToolSpecification(
        "event",
        "One calendar event with its attendees, by event id.",
        PortMethod.EVENT,
        (IdArgument("id", EntityKind.EVENT),),
    ),
    ToolSpecification(
        "events_within",
        "Every calendar event overlapping a half-open span of instants.",
        PortMethod.EVENTS_WITHIN,
        (InstantSpanArgument("span", 31),),
    ),
    ToolSpecification(
        "document",
        "One corpus document with its sections, by document id.",
        PortMethod.DOCUMENT,
        (IdArgument("id", EntityKind.DOCUMENT),),
    ),
    ToolSpecification(
        "documents",
        "Every document the document store holds, each with its sections.",
        PortMethod.DOCUMENTS,
        (),
    ),
    ToolSpecification(
        "search",
        "The corpus documents whose sections best match a free-text query, up to a limit.",
        PortMethod.SEARCH,
        (QueryArgument("query", 200), SEARCH_LIMIT),
    ),
)
"""The fourteen, in the one canonical order a registry preserves and sends."""


# --- The roles ----------------------------------------------------------------------------


class Role(StrEnum):
    """The roles a registry constructs a tool list for: the investigator, and the reader the
    two one-call baselines share (the baselines step, fork 3)."""

    INVESTIGATOR = "investigator"
    READER = "reader"


INVESTIGATOR_METHODS: frozenset[PortMethod] = frozenset(
    {
        PortMethod.EMPLOYEE,
        PortMethod.TEAM,
        PortMethod.LEAVE,
        PortMethod.LEAVES_WITHIN,
        PortMethod.WORK_ITEM,
        PortMethod.COMPONENT,
        PortMethod.EVENT,
        PortMethod.EVENTS_WITHIN,
        PortMethod.DOCUMENT,
        PortMethod.SEARCH,
    }
)
"""The ten the investigator is shown: every method but the four whole-table enumerations.
Three (``employees``, ``components``, ``work_items``) the frozen prefetch reads for every
run and the turns render before the first call (the registry step, fork 1); the fourth
(``documents``) is the full-context baseline's one harness read and never a tool of the
agent's (the baselines step, fork 8). Stated as the included set, so the list is a positive
claim and not what happens to be left over."""

READER_METHODS: frozenset[PortMethod] = frozenset()
"""The reader is shown no read tool: the single-shot and the full-context baselines make one
model call over what the harness read for them, and the fact tool is the one tool beside
(the baselines step, forks 2 and 3). Stated as the empty set so the list is a positive claim."""

ROLE_METHODS: Mapping[Role, frozenset[PortMethod]] = MappingProxyType(
    {Role.INVESTIGATOR: INVESTIGATOR_METHODS, Role.READER: READER_METHODS}
)


def role_surface(role: Role) -> tuple[ToolSpecification, ...]:
    """The specifications ``role`` is shown, in the canonical order.

    >>> [s.name for s in role_surface(Role.INVESTIGATOR)][:4]
    ['employee', 'team', 'leave', 'leaves_within']
    """
    methods = ROLE_METHODS[role]
    return tuple(s for s in TOOL_SPECIFICATIONS if s.method in methods)


# --- Validation -------------------------------------------------------------------------


class ArgumentsRefused(ValueError):
    """A call's arguments were refused before any source was asked.

    ``str()`` is the detail, which names the value given and is what the log and the
    export record; ``correction`` is the one message the model is shown, built from the
    declaration alone; ``argument`` is the argument refused, ``None`` when the object as a
    whole was (not an object, or not exactly the declared arguments).
    """

    def __init__(self, argument: str | None, correction: str, detail: str) -> None:
        super().__init__(detail)
        self.argument = argument
        self.correction = correction


def expected_shape(argument: Argument) -> str:
    """What ``argument`` must be, in the words a correction uses; from the declaration only.

    >>> expected_shape(IdArgument("id", EntityKind.EMPLOYEE))
    'an employee id of the form emp_NNN'
    >>> expected_shape(SEARCH_LIMIT)
    'an integer from 1 to 20'
    """
    match argument:
        case IdArgument():
            prefix = PREFIX_BY_KIND[argument.kind]
            return f"{with_article(argument.kind.value)} id of the form {prefix}_NNN"
        case IntegerArgument():
            return f"an integer from {argument.minimum} to {argument.maximum}"
        case DateSpanArgument():
            return (
                "an object with start and end as YYYY-MM-DD calendar days, start not after "
                f"end, at most {argument.max_days} days"
            )
        case InstantSpanArgument():
            return (
                "an object with start and end as instants {at, timezone}, start before end, "
                f"at most {argument.max_days} days apart"
            )
        case QueryArgument():
            return f"a non-blank string of at most {argument.max_length} characters"
        case _:
            assert_never(argument)


def object_correction(specification: ToolSpecification) -> str:
    """The correction for arguments that are not exactly ``specification``'s object."""
    names = ", ".join(argument.name for argument in specification.arguments)
    held = f"exactly: {names}" if names else "no fields"
    return f"{specification.name}'s arguments are a JSON object holding {held}"


def argument_correction(specification: ToolSpecification, argument: Argument) -> str:
    """The correction for ``argument`` of ``specification`` not being its declared shape."""
    return f"{specification.name}'s {argument.name} is {expected_shape(argument)}"


def surface_correction(surface: tuple[ToolSpecification, ...]) -> str:
    """The correction for a tool call naming no tool of ``surface``; the names are the
    declaration's, never the one the model wrote."""
    names = ", ".join(specification.name for specification in surface)
    return f"that is not one of this role's tools; the tools are: {names}"


def correction_messages(surface: tuple[ToolSpecification, ...]) -> frozenset[str]:
    """Every correction a call against ``surface`` can be answered with: the closed set a
    capture checks the rendered refusals against."""
    messages = {surface_correction(surface)}
    for specification in surface:
        messages.add(object_correction(specification))
        for argument in specification.arguments:
            messages.add(argument_correction(specification, argument))
    return frozenset(messages)


def validate_arguments(specification: ToolSpecification, value: object) -> Mapping[str, object]:
    """The domain values of a call's arguments, or ``ArgumentsRefused`` (a ``ValueError``)
    whose detail names the argument and the value refused and whose correction is the
    closed message the model may be shown.

    Exactly the declared arguments, each in its declared shape, nothing coerced and
    nothing defaulted, so the accepted raw arguments are the effective ones.

    >>> validate_arguments(TOOL_SPECIFICATIONS[0], {"id": "emp_017"})
    {'id': 'emp_017'}
    >>> validate_arguments(TOOL_SPECIFICATIONS[0], {"id": "LIA-42"})
    Traceback (most recent call last):
    ...
    leaveimpact.core.tools.ArgumentsRefused: an employee id has the form emp_NNN, got 'LIA-42'
    """
    what = f"{specification.name}'s arguments"
    try:
        data = as_object(value, what)
        expect_fields(data, tuple(argument.name for argument in specification.arguments), what)
    except ValueError as refused:
        raise ArgumentsRefused(None, object_correction(specification), str(refused)) from None
    accepted: dict[str, object] = {}
    for argument in specification.arguments:
        try:
            accepted[argument.name] = _validated(argument, data[argument.name])
        except ValueError as refused:
            raise ArgumentsRefused(
                argument.name, argument_correction(specification, argument), str(refused)
            ) from None
    return accepted


def _validated(argument: Argument, value: object) -> object:
    match argument:
        case IdArgument():
            if not isinstance(value, str):
                raise ValueError(f"{argument.name} is a string id, got {type(value).__name__}")
            return require_id(argument.kind, value)
        case IntegerArgument():
            held = require_integer(value, argument.name, minimum=argument.minimum)
            if held > argument.maximum:
                raise ValueError(f"{argument.name} is at most {argument.maximum}, got {held}")
            return held
        case DateSpanArgument():
            span = decode_date_span(value, argument.name)
            if span.days > argument.max_days:
                raise ValueError(
                    f"{argument.name} spans at most {argument.max_days} days, got {span.days}"
                )
            return span
        case InstantSpanArgument():
            data = as_object(value, argument.name)
            expect_fields(data, ("start", "end"), argument.name)
            span = InstantSpan(
                decode_instant(data["start"], f"{argument.name}.start"),
                decode_instant(data["end"], f"{argument.name}.end"),
            )
            # Elapsed time, never wall-clock difference: two ends in one zone subtract naively
            # in Python and a span across a clock change would be an hour off.
            if span.duration > timedelta(days=argument.max_days):
                raise ValueError(f"{argument.name} spans at most {argument.max_days} days")
            return span
        case QueryArgument():
            if not isinstance(value, str):
                raise ValueError(f"{argument.name} is a string, got {type(value).__name__}")
            if not value.strip():
                raise ValueError(f"{argument.name} is non-blank")
            if len(value) > argument.max_length:
                raise ValueError(
                    f"{argument.name} is at most {argument.max_length} characters, got {len(value)}"
                )
            return value
        case _:
            assert_never(argument)


# --- The model's schema and the surface digest --------------------------------------------


def tool_definition(specification: ToolSpecification) -> JsonObject:
    """The provider-neutral definition the model is given: name, description, input schema."""
    return {
        "name": specification.name,
        "description": specification.description,
        "input_schema": {
            "type": "object",
            "properties": {
                argument.name: _schema(argument) for argument in specification.arguments
            },
            "required": [argument.name for argument in specification.arguments],
            "additionalProperties": False,
        },
    }


def _schema(argument: Argument) -> JsonObject:
    match argument:
        case IdArgument():
            prefix = PREFIX_BY_KIND[argument.kind]
            return {
                "type": "string",
                "pattern": f"^{prefix}_[0-9]{{3,}}$",
                "description": f"{argument.kind.value} id, {prefix}_NNN",
            }
        case IntegerArgument():
            return {"type": "integer", "minimum": argument.minimum, "maximum": argument.maximum}
        case DateSpanArgument():
            return {
                "type": "object",
                "properties": {"start": _date_schema(), "end": _date_schema()},
                "required": ["start", "end"],
                "additionalProperties": False,
                "description": f"Inclusive calendar days, at most {argument.max_days} long",
            }
        case InstantSpanArgument():
            return {
                "type": "object",
                "properties": {"start": _instant_schema(), "end": _instant_schema()},
                "required": ["start", "end"],
                "additionalProperties": False,
                "description": f"Half-open [start, end), at most {argument.max_days} days long",
            }
        case QueryArgument():
            # The pattern says what the wrapper enforces: at least one non-blank character.
            return {
                "type": "string",
                "minLength": 1,
                "maxLength": argument.max_length,
                "pattern": r"\S",
            }
        case _:
            assert_never(argument)


def _date_schema() -> JsonObject:
    return {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$", "description": "YYYY-MM-DD"}


def _instant_schema() -> JsonObject:
    return {
        "type": "object",
        "properties": {
            "at": {
                "type": "string",
                "description": "ISO 8601 with its UTC offset, e.g. 2026-09-14T09:00:00+03:00",
            },
            "timezone": {
                "type": ["string", "null"],
                "description": "The IANA zone the instant is read in, or null",
            },
        },
        "required": ["at", "timezone"],
        "additionalProperties": False,
    }


def tool_surface_digest(
    specifications: tuple[ToolSpecification, ...], harness_tools: tuple[JsonObject, ...] = ()
) -> str:
    """SHA-256 over the versioned envelope of what a role's model sees, in the order sent:
    the read tools' definitions, then ``harness_tools``, the definitions of the tools the
    harness answers itself (the fact tool), in the order they are sent.

    >>> tool_surface_digest(TOOL_SPECIFICATIONS) == tool_surface_digest(TOOL_SPECIFICATIONS)
    True
    >>> first_two, reversed_two = TOOL_SPECIFICATIONS[:2], TOOL_SPECIFICATIONS[1::-1]
    >>> tool_surface_digest(first_two) == tool_surface_digest(reversed_two)
    False
    """
    names = [specification.name for specification in specifications]
    names.extend(str(definition.get("name")) for definition in harness_tools)
    if len(set(names)) != len(names):
        raise ValueError(f"a surface names each tool once, got {names}")
    envelope: JsonObject = {
        "surface_version": SURFACE_VERSION,
        "tools": [tool_definition(specification) for specification in specifications],
        "harness_tools": list(harness_tools),
        "result_codec": {"id": RESULT_CODEC[0], "version": RESULT_CODEC[1]},
        "validation_protocol": {"id": VALIDATION_PROTOCOL[0], "version": VALIDATION_PROTOCOL[1]},
    }
    return hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def specification_named(
    name: str, among: tuple[ToolSpecification, ...] = TOOL_SPECIFICATIONS
) -> ToolSpecification | None:
    """The specification with ``name`` among ``among`` (the fourteen by default; a role's
    surface when a role's call is resolved), or ``None`` when no tool there is so named."""
    for specification in among:
        if specification.name == name:
            return specification
    return None
