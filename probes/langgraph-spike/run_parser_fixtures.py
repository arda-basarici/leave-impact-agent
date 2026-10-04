"""Bad tool calls as the pinned chat client hands them on: crafted Converse responses fed
through the client's own parser, with no network.

A bad call injected already parsed would miss whatever the client discards or repairs on the
way (the acceptance spike's ruling 5), so the fixtures enter where a provider's answer does:
a stub in place of the boto client returns a crafted ``converse`` response or a crafted
``converse_stream`` event sequence, and ``ChatBedrockConverse`` 's parser makes the message.
What a stub cannot show is botocore's own parsing of the wire; the provider half's captures
are the evidence for that layer.

Each fixture is one response holding one tool call, whole or streamed. For each the row
holds three readings side by side:

- *raw:* the tool name, the arguments as crafted (the object, or the streamed fragments
  joined), whether those arguments parse as JSON, and the stop reason;
- *client:* the tool calls and the invalid tool calls of the message the client returned;
- *harness:* how the spike's adapter classifies the response, and for a response it would
  dispatch, the outcome of each call through the package's executor over the throwaway
  world's ports, with the number of port calls counted.

Measured, no pass or fail: the point is where the client's reading and the raw answer
differ, which decides what the harness may trust. The streamed message is the sum of the
chunks ``stream`` yields, the aggregation ``invoke`` performs on a streaming model.

    uv run --group harness python probes/langgraph-spike/run_parser_fixtures.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

from eventlog import harness_revision
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, HumanMessage
from replay import classified, response_text

REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from leaveimpact.agent.execution import Executor, ReadPorts  # noqa: E402
from leaveimpact.core.run_export_json import (  # noqa: E402
    _encode_outcome,  # pyright: ignore[reportPrivateUsage]
)
from leaveimpact.core.run_trace import ModelCallId, ModelCallOutcome, ModelOrigin  # noqa: E402
from tests.unit.reads_fixture import systems_holding  # noqa: E402
from tests.unit.throwaway_world import loaded_world  # noqa: E402

PROFILE = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
USAGE = {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}


@dataclass(frozen=True, slots=True)
class Fixture:
    """One crafted answer: a tool call by ``name``, its arguments an object when whole or a
    sequence of text fragments when streamed, and the stop reason the provider gives."""

    label: str
    name: str
    whole: dict[str, Any] | None
    fragments: tuple[str, ...] | None
    stop_reason: str

    @property
    def streamed(self) -> bool:
        return self.fragments is not None


FIXTURES = (
    Fixture("whole, valid", "employee", {"id": "emp_001"}, None, "tool_use"),
    Fixture("whole, unknown tool name", "employe", {"id": "emp_001"}, None, "tool_use"),
    Fixture("whole, schema-violating arguments", "employee", {"id": "LIA-42"}, None, "tool_use"),
    Fixture("whole, surplus argument", "employee", {"id": "emp_001", "x": 1}, None, "tool_use"),
    Fixture("whole, no-argument tool", "employees", {}, None, "tool_use"),
    Fixture("whole, cut at the output limit", "employee", {}, None, "max_tokens"),
    Fixture(
        "streamed, valid in two fragments", "employee", None, ('{"id": "emp', '_001"}'), "tool_use"
    ),
    Fixture("streamed, unknown tool name", "employe", None, ('{"id": "emp_001"}',), "tool_use"),
    Fixture(
        "streamed, schema-violating arguments", "employee", None, ('{"id": "LIA-42"}',), "tool_use"
    ),
    Fixture(
        "streamed, arguments cut mid-string, stop tool_use",
        "employee",
        None,
        ('{"id": "emp_0',),
        "tool_use",
    ),
    Fixture(
        "streamed, arguments cut mid-string, stop max_tokens",
        "employee",
        None,
        ('{"id": "emp_0',),
        "max_tokens",
    ),
    Fixture(
        "streamed, arguments not JSON at all", "employee", None, ("id is emp_001",), "tool_use"
    ),
    Fixture("streamed, arguments a JSON array", "employee", None, ('["emp_001"]',), "tool_use"),
    Fixture("streamed, no-argument tool, no fragment", "employees", None, (), "tool_use"),
    Fixture("streamed, no-argument tool, one empty fragment", "employees", None, ("",), "tool_use"),
    Fixture("streamed, no-argument tool, an empty object", "employees", None, ("{}",), "tool_use"),
    Fixture("streamed, one empty fragment, stop max_tokens", "employee", None, ("",), "max_tokens"),
)


class StubClient:
    """Stands where the boto client does and answers every call with one fixture."""

    def __init__(self, fixture: Fixture) -> None:
        self.fixture = fixture

    def converse(self, **_: Any) -> dict[str, Any]:
        fixture = self.fixture
        use = {"toolUseId": "tooluse_fixture", "name": fixture.name, "input": fixture.whole}
        return {
            "ResponseMetadata": {"RequestId": "fixture", "HTTPStatusCode": 200},
            "output": {"message": {"role": "assistant", "content": [{"toolUse": use}]}},
            "stopReason": fixture.stop_reason,
            "usage": dict(USAGE),
            "metrics": {"latencyMs": 1},
        }

    def converse_stream(self, **_: Any) -> dict[str, Any]:
        fixture = self.fixture
        start = {"toolUse": {"toolUseId": "tooluse_fixture", "name": fixture.name}}
        events: list[dict[str, Any]] = [
            {"messageStart": {"role": "assistant"}},
            {"contentBlockStart": {"start": start, "contentBlockIndex": 0}},
        ]
        events += [
            {"contentBlockDelta": {"delta": {"toolUse": {"input": text}}, "contentBlockIndex": 0}}
            for text in fixture.fragments or ()
        ]
        events += [
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": fixture.stop_reason}},
            {"metadata": {"usage": dict(USAGE), "metrics": {"latencyMs": 1}}},
        ]
        return {"ResponseMetadata": {"RequestId": "fixture"}, "stream": iter(events)}


class CountingPort:
    """A reader that counts the calls reaching it."""

    def __init__(self, port: object, calls: list[str]) -> None:
        self._port = port
        self._calls = calls

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._port, name)
        if not callable(attribute):
            return attribute

        def dispatched(*arguments: Any, **named: Any) -> Any:
            self._calls.append(name)
            return attribute(*arguments, **named)

        return dispatched


def answered(fixture: Fixture) -> AIMessage:
    """The message the pinned client makes of ``fixture``."""
    model = ChatBedrockConverse(
        model=PROFILE,
        client=StubClient(fixture),
        bedrock_client=object(),
        region_name="eu-central-1",
        max_tokens=64,
        temperature=0,
    )
    asked = [HumanMessage("Look up the record.")]
    if not fixture.streamed:
        message = model.invoke(asked)
        assert isinstance(message, AIMessage)
        return message
    total = None
    for chunk in model.stream(asked):
        total = chunk if total is None else total + chunk
    assert isinstance(total, AIMessage)
    return total


def parses(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


def row(fixture: Fixture, ports: ReadPorts) -> dict[str, Any]:
    """The three readings of ``fixture``."""
    crafted = "".join(fixture.fragments) if fixture.fragments is not None else None
    try:
        message = answered(fixture)
    except Exception as raised:  # noqa: BLE001 - what the client raises is the finding
        return {
            "fixture": fixture.label,
            "raw": {"name": fixture.name, "arguments": crafted, "stop_reason": fixture.stop_reason},
            "client": {"raised": f"{type(raised).__name__}: {raised}"[:300]},
        }
    stop_reason = message.response_metadata.get("stopReason")
    outcome = classified(
        response_text(message), stop_reason, bool(message.tool_calls or message.invalid_tool_calls)
    )
    calls: list[str] = []
    counted = ReadPorts(
        *(
            CountingPort(port, calls)
            for port in (ports.people, ports.work, ports.calendar, ports.documents)
        )  # type: ignore[arg-type]
    )
    executed: list[dict[str, Any]] = []
    if outcome is ModelCallOutcome.TOOL_CALLS:
        # The graph's rule: only the calls the client parsed reach the executor.
        executor = Executor(counted)
        for call in message.tool_calls:
            result = executor.call(ModelOrigin(ModelCallId("mc-1")), call["name"], call["args"])
            encoded = _encode_outcome(result)
            executed.append({"kind": encoded["kind"], "reason": encoded.get("reason")})
    return {
        "fixture": fixture.label,
        "raw": {
            "name": fixture.name,
            "arguments": fixture.whole if crafted is None else crafted,
            "arguments_parse_as_json": None if crafted is None else parses(crafted),
            "stop_reason": fixture.stop_reason,
        },
        "client": {
            "stop_reason": stop_reason,
            "tool_calls": [{"name": c["name"], "args": c["args"]} for c in message.tool_calls],
            "invalid_tool_calls": [
                {"name": c.get("name"), "args": c.get("args"), "error": c.get("error")}
                for c in message.invalid_tool_calls
            ],
        },
        "harness": {
            "classified": outcome.value,
            "dispatched_to_the_executor": outcome is ModelCallOutcome.TOOL_CALLS,
            "executor_outcomes": executed,
            "port_calls": len(calls),
        },
    }


def main() -> int:
    ports = systems_holding(loaded_world()).ports
    summary = {
        "probe": "parser fixtures",
        "kind": "measured",
        "harness": harness_revision(),
        "versions": {name: version(name) for name in ("langchain-aws", "langchain-core")},
        "rows": [row(fixture, ports) for fixture in FIXTURES],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
