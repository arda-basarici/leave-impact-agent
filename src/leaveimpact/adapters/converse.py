"""The one translation from a provider-neutral tool definition to Bedrock Converse's wire shape.

A definition is what ``core`` generates for a read tool and what the prose checker builds
for its forced tool: a name, a description and a JSON schema under ``input_schema``. Converse
wants the same three under ``toolSpec`` with the schema wrapped in ``{"json": ...}``. Two
callers send tools, the generator's checker and the investigator's turns, and each kept its
own copy of that wrapping until the registry step; one function here is the copy they share,
and nothing else about a request (the tool choice, the messages, the inference settings) is
decided here, since the checker forces its one tool and the investigator does not, and that
is each caller's request policy.
"""

from __future__ import annotations

from leaveimpact.core.jsonshape import JsonObject, as_object, expect_fields, string_field


def converse_tool(definition: JsonObject) -> JsonObject:
    """The ``toolSpec`` entry of Converse's ``toolConfig.tools`` for ``definition``.

    >>> converse_tool({"name": "t", "description": "d", "input_schema": {"type": "object"}})
    {'toolSpec': {'name': 't', 'description': 'd', 'inputSchema': {'json': {'type': 'object'}}}}
    """
    data = as_object(definition, "a tool definition")
    expect_fields(data, ("name", "description", "input_schema"), "a tool definition")
    return {
        "toolSpec": {
            "name": string_field(data, "name"),
            "description": string_field(data, "description"),
            "inputSchema": {"json": as_object(data["input_schema"], "a tool's input schema")},
        }
    }
