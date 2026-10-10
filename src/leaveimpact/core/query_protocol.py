"""The single-shot baseline's query protocol: what its one search asks, written down before
any run, and the pure rendering that turns it into the search's text.

The single-shot system makes one harness-issued search over the shared prefetch and one
model call (DESIGN, the baselines passage; the baselines step, fork 5). Its query is
registered, never chosen at run time: either a *literal*, the same text for every run, or a
*template*, a short list of parts each of which is a literal text or the name of an input
the rendering fills from what the prefetch returned. The protocol's value is a field of the
registration since format 4 and one of the frozen inputs of an admission (the baselines
step, fork 12), so a recovering worker renders the same text a first process did and a
claim under a registration whose protocol differs is refused.

*What a template may read.* Only values the model is shown anyway in the prefetch blocks of
its first message: the leaver's name, the names of the components the leaver's work items
belong to, and the titles of the leaver's work items. Nothing of the scenario spec beyond
the leave id, nothing sealed, nothing of truth; the team is not among them because the
prefetch reads no team record. A template whose inputs find no value renders blank and the
registered fallback literal is sent instead, so a search is always made and its text is
always one the registration foresaw.

*How a rendering is joined.* The adapter parses a query with PostgreSQL's web-search
grammar, where plain words are conjoined and ``or`` is the disjunction, so parts and the
several values of one input are joined with `` or ``: a template that joined by spaces
would narrow with every input and return nothing. Each value is kept as the record spells
it; the rendered text is clipped to the search argument's maximum at a word boundary, since
a query the executor refuses would be this harness's defect and never the model's.

The selection between candidate protocols is a probe's, model-free, on development worlds
with the procedure fixed before any candidate is scored (the forks file); nothing here
chooses.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from leaveimpact.core.entities import Component, Employee, Leave, WorkItem
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    expect_fields,
    string_field,
)
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.tools import QueryArgument, specification_named

JOIN = " or "
"""How parts and values are joined: the web-search grammar's disjunction."""


def _query_length() -> int:
    search = specification_named("search")
    assert search is not None
    (query, _) = search.arguments
    assert isinstance(query, QueryArgument)
    return query.max_length


QUERY_MAX_LENGTH = _query_length()
"""The search argument's maximum, read off the declaration so the two cannot disagree."""


class QueryInput(StrEnum):
    """The values a template may read from the prefetch's returned records."""

    LEAVER_NAME = "leaver_name"
    COMPONENT_NAMES = "component_names"
    WORK_ITEM_TITLES = "work_item_titles"


@dataclass(frozen=True, slots=True)
class LiteralQuery:
    """One text, sent as written for every run."""

    text: str

    def __post_init__(self) -> None:
        _require_query_text(self.text, "a literal query")


@dataclass(frozen=True, slots=True)
class TemplateQuery:
    """Parts rendered over the prefetch and joined by ``JOIN``: each part a literal text or an
    input; ``fallback`` is the literal sent when every part renders blank.

    >>> TemplateQuery((QueryInput.COMPONENT_NAMES, "handover"), "handover or coverage").parts
    (<QueryInput.COMPONENT_NAMES: 'component_names'>, 'handover')
    >>> TemplateQuery((), "handover")
    Traceback (most recent call last):
    ...
    ValueError: a template has at least one part
    """

    parts: tuple[QueryInput | str, ...]
    fallback: str

    def __post_init__(self) -> None:
        if not self.parts:
            raise ValueError("a template has at least one part")
        for part in self.parts:
            if not isinstance(part, QueryInput):
                _require_query_text(part, "a template's literal part")
        _require_query_text(self.fallback, "a template's fallback")
        if not any(isinstance(part, QueryInput) for part in self.parts):
            raise ValueError("a template names at least one input; a text alone is a literal")


type QueryProtocol = LiteralQuery | TemplateQuery


def _require_query_text(text: str, what: str) -> None:
    if not text.strip():
        raise ValueError(f"{what} is non-blank")
    if len(text) > QUERY_MAX_LENGTH:
        raise ValueError(f"{what} is at most {QUERY_MAX_LENGTH} characters, got {len(text)}")
    if text != text.strip() or "  " in text:
        raise ValueError(f"{what} is written in its one form: no surrounding or doubled spaces")


# --- Rendering --------------------------------------------------------------------------------


def input_values(
    name: QueryInput, returned: tuple[Observed[Entity], ...], leave: Leave
) -> tuple[str, ...]:
    """The values ``name`` takes from the records ``returned``, for the leaver ``leave`` names:
    distinct, non-blank, in the order first returned.

    The leaver is the employee record whose id the leave carries; the components are those
    of the leaver's work items, by the items' component ids; the titles are the leaver's
    work items'. A value is a record's field as spelled, never derived.
    """
    employees = {r.value.id: r.value for r in returned if isinstance(r.value, Employee)}
    items = [r.value for r in returned if isinstance(r.value, WorkItem)]
    owned = [item for item in items if item.owner_id == leave.employee_id]
    match name:
        case QueryInput.LEAVER_NAME:
            leaver = employees.get(leave.employee_id)
            values = [] if leaver is None else [leaver.name]
        case QueryInput.COMPONENT_NAMES:
            components = {
                r.value.id: r.value for r in returned if isinstance(r.value, Component)
            }
            wanted = {item.component_id for item in owned}
            values = [
                component.name for id, component in components.items() if id in wanted
            ]
        case QueryInput.WORK_ITEM_TITLES:
            values = [item.title for item in owned]
        case _:
            assert_never(name)
    distinct: dict[str, None] = {}
    for value in values:
        if value.strip():
            distinct[" ".join(value.split())] = None
    return tuple(distinct)


def render_query(
    protocol: QueryProtocol, returned: tuple[Observed[Entity], ...], leave: Leave
) -> str:
    """The text the single-shot search sends under ``protocol``, over the records the
    prefetch ``returned`` for the leaver ``leave`` names: a literal as written; a template's
    parts joined by ``JOIN`` with each input's values, blank parts dropped, the whole clipped
    to the search argument's maximum at a word boundary, and the fallback when nothing
    rendered.
    """
    match protocol:
        case LiteralQuery(text):
            return text
        case TemplateQuery(parts, fallback):
            pieces: list[str] = []
            for part in parts:
                if isinstance(part, QueryInput):
                    pieces.extend(input_values(part, returned, leave))
                else:
                    pieces.append(part)
            rendered = clip_query(JOIN.join(pieces))
            return rendered if rendered else fallback
        case _:
            assert_never(protocol)


def clip_query(text: str) -> str:
    """``text`` cut to the search argument's maximum at the last word boundary inside it, or
    hard at the maximum when a single word runs past it; trailing join words dropped.

    >>> clip_query("short")
    'short'
    >>> len(clip_query(" ".join(["word"] * 60))) <= QUERY_MAX_LENGTH
    True
    """
    if len(text) <= QUERY_MAX_LENGTH:
        return text
    cut = text[:QUERY_MAX_LENGTH]
    boundary = cut.rfind(" ")
    clipped = cut if boundary <= 0 else cut[:boundary]
    while clipped.endswith(" or"):
        clipped = clipped[: -len(" or")]
    return clipped.rstrip()


# --- Codec --------------------------------------------------------------------------------------

LITERAL = "literal"
TEMPLATE = "template"


def encode_query_protocol(protocol: QueryProtocol) -> JsonObject:
    """``protocol`` as the registration writes it.

    >>> encode_query_protocol(LiteralQuery("handover"))
    {'kind': 'literal', 'text': 'handover'}
    """
    match protocol:
        case LiteralQuery(text):
            return {"kind": LITERAL, "text": text}
        case TemplateQuery(parts, fallback):
            return {
                "kind": TEMPLATE,
                "parts": [
                    {"input": part.value} if isinstance(part, QueryInput) else {"text": part}
                    for part in parts
                ],
                "fallback": fallback,
            }
        case _:
            assert_never(protocol)


def decode_query_protocol(value: object) -> QueryProtocol:
    """The protocol ``value`` encodes; ``ValueError`` for any other shape.

    >>> decode_query_protocol({"kind": "literal", "text": "handover"})
    LiteralQuery(text='handover')
    """
    data = as_object(value, "a query protocol")
    kind = string_field(data, "kind")
    if kind == LITERAL:
        expect_fields(data, ("kind", "text"), "a literal query")
        return LiteralQuery(string_field(data, "text"))
    if kind == TEMPLATE:
        expect_fields(data, ("kind", "parts", "fallback"), "a template query")
        parts: list[QueryInput | str] = []
        for item in array_field(data, "parts"):
            part = as_object(item, "a template part")
            if set(part) == {"input"}:
                parts.append(QueryInput(string_field(part, "input")))
            elif set(part) == {"text"}:
                parts.append(string_field(part, "text"))
            else:
                raise ValueError(f"a template part is one of input or text, got {sorted(part)}")
        return TemplateQuery(tuple(parts), string_field(data, "fallback"))
    raise ValueError(f"a query protocol's kind is literal or template, got {kind!r}")


__all__ = [
    "JOIN",
    "QUERY_MAX_LENGTH",
    "LiteralQuery",
    "QueryInput",
    "QueryProtocol",
    "TemplateQuery",
    "clip_query",
    "decode_query_protocol",
    "encode_query_protocol",
    "input_values",
    "render_query",
]
