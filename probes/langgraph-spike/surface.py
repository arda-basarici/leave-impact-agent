"""The tool surface the provider probes send: the generated definitions, and named translations.

The definitions come from ``core.tools.tool_definition`` and go out through the chat client's
``toolConfig`` binding, which passes them on untouched; ``bind_tools`` would rebuild each one
through a converter first. The unchanged surface is tried first. Amazon Nova documents a
narrower schema than the generated one (the top-level object takes ``type``, ``properties``
and ``required`` only), so the translations below form a ladder, each removing a little more,
and a family's *effective surface* is the first rung its endpoint accepts. A translation only
changes what the model is shown: the arguments a model returns are still validated by the
original specification.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from leaveimpact.core.tools import TOOL_SPECIFICATIONS, tool_definition

JsonObject = dict[str, Any]

Choice = str
"""``auto``, ``any``, or a tool's name for a forced call of that tool."""


def tool_choice(choice: Choice) -> JsonObject:
    """The Converse ``toolChoice`` for ``choice``, always stated, never left to a default.

    >>> tool_choice("any")
    {'any': {}}
    >>> tool_choice("employee")
    {'tool': {'name': 'employee'}}
    """
    if choice in ("auto", "any"):
        return {choice: {}}
    return {"tool": {"name": choice}}


# --- The ladder -----------------------------------------------------------------------------


def unchanged(schema: JsonObject) -> JsonObject:
    """The generated schema as it is."""
    return schema


def top_level_fields(schema: JsonObject) -> JsonObject:
    """The top-level object reduced to ``type``, ``properties`` and ``required``.

    >>> top_level_fields({"type": "object", "properties": {}, "required": [], "x": 1})
    {'type': 'object', 'properties': {}, 'required': []}
    """
    return {key: schema[key] for key in ("type", "properties", "required") if key in schema}


def no_additional_properties(schema: JsonObject) -> JsonObject:
    """``top_level_fields``, and ``additionalProperties`` removed at every depth.

    >>> nested = {"type": "object", "properties": {"a": {"type": "object",
    ...           "additionalProperties": False}}, "required": ["a"]}
    >>> no_additional_properties(nested)["properties"]["a"]
    {'type': 'object'}
    """
    return cast(JsonObject, _without(top_level_fields(schema), "additionalProperties"))


def structure_only(schema: JsonObject) -> JsonObject:
    """``no_additional_properties``, and every validation keyword removed: types, nesting,
    required names and descriptions are what is left. A nullable type list becomes its
    non-null type.

    >>> structure_only({"type": "object", "properties": {"z": {"type": ["string", "null"],
    ...                 "pattern": "x"}}, "required": ["z"]})["properties"]["z"]
    {'type': 'string'}
    """
    stripped = no_additional_properties(schema)
    for keyword in ("pattern", "minLength", "maxLength", "minimum", "maximum"):
        stripped = cast(JsonObject, _without(stripped, keyword))
    return cast(JsonObject, _single_types(stripped))


def _without(value: object, keyword: str) -> object:
    """``value`` with ``keyword`` removed from every schema object; a property that happens
    to be named ``keyword`` is kept, since the names under ``properties`` are not keywords."""
    if isinstance(value, list):
        return [_without(item, keyword) for item in cast("list[object]", value)]
    if not isinstance(value, dict):
        return value
    held = cast(JsonObject, value)
    result: JsonObject = {}
    for key, item in held.items():
        if key == "properties" and isinstance(item, dict):
            result[key] = {
                name: _without(sub, keyword) for name, sub in cast(JsonObject, item).items()
            }
        elif key != keyword:
            result[key] = _without(item, keyword)
    return result


def _single_types(value: object) -> object:
    if isinstance(value, list):
        return [_single_types(item) for item in cast("list[object]", value)]
    if not isinstance(value, dict):
        return value
    result: JsonObject = {}
    for key, item in cast(JsonObject, value).items():
        if key == "type" and isinstance(item, list):
            kept = [name for name in cast("list[str]", item) if name != "null"]
            result[key] = kept[0] if len(kept) == 1 else kept
        else:
            result[key] = _single_types(item)
    return result


@dataclass(frozen=True, slots=True)
class Translation:
    """A named, versioned rewriting of each tool's input schema."""

    name: str
    version: int
    rewrite: Callable[[JsonObject], JsonObject]


LADDER: tuple[Translation, ...] = (
    Translation("unchanged", 1, unchanged),
    Translation("top-level-fields", 1, top_level_fields),
    Translation("no-additional-properties", 1, no_additional_properties),
    Translation("structure-only", 1, structure_only),
)
"""Tried in this order; the first a family accepts is its effective surface."""


def tools_under(translation: Translation) -> list[JsonObject]:
    """The thirteen definitions as Converse ``toolSpec`` entries, in the canonical order."""
    tools: list[JsonObject] = []
    for specification in TOOL_SPECIFICATIONS:
        definition = tool_definition(specification)
        schema = cast(JsonObject, definition["input_schema"])
        tools.append(
            {
                "toolSpec": {
                    "name": definition["name"],
                    "description": definition["description"],
                    "inputSchema": {"json": translation.rewrite(schema)},
                }
            }
        )
    return tools


def tool_config(translation: Translation, choice: Choice) -> JsonObject:
    """The whole ``toolConfig`` a probe binds: the surface under ``translation``, the choice."""
    return {"tools": tools_under(translation), "toolChoice": tool_choice(choice)}
