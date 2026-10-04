"""The scripted model: a chat model that answers from a fixed script, deterministic and free.

The persistence checks need a model whose answers cannot vary (the acceptance spike's ruling
1), so a recovered run can be compared with an uninterrupted one. It is a chat model of the
pinned core library, so the graph calls it through the same seam the bounded live run fills
with the Bedrock client.

Which turn to answer is read off the request, the count of assistant messages it already
holds, never off a counter of invocations: a second invocation with the same request gets
the same answer, in this process or a later one. That is also why equality of two exports
proves nothing about how many times the model ran. Each invocation therefore appends one
line to a count file, flushed and synced before the answer is returned, so the count survives
a killed process. The file is the injector's own record: the graph and recovery never read it.
Under the crash check the injector's record also gets a line when a request arrives and one
just before its response is returned, so a response that was returned and then lost before
its outcome was appended is counted as a response.

The message has the shape the pinned Bedrock client gives one, where that differs from the
plain shape: the content is a list of blocks whenever a tool call is present, a call the
client could not parse included, whose block holds the raw argument text, and the reported
latency is a one-item list. A response adapter that handles only the plain shape would pass
here and fail on the live path.

A turn carries text, tool calls or both. The spike's claims travel as the turn's text, the
claims codec's canonical array; one scripted turn carries claims beside a tool call. This
carrier sets no precedent for how the investigator emits claims.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from seams import witness

MODEL_ID = "scripted"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One tool call a turn makes: the tool and its arguments as a model would spell them."""

    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Turn:
    """One scripted response: its text, its tool calls, and the usage and latency it reports."""

    text: str
    tool_calls: tuple[ToolCall, ...]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    unparsed: tuple[tuple[str, str], ...] = ()
    """Tool calls whose arguments are not a JSON object, each the tool's name and the raw
    text, as the pinned client hands on a streamed call it could not parse."""

    @property
    def stop_reason(self) -> str:
        return "tool_use" if self.tool_calls or self.unparsed else "end_turn"


class ScriptedChatModel(BaseChatModel):
    """Answers the turn the request has reached, and records each invocation in ``count_file``."""

    turns: tuple[Turn, ...]
    count_file: str

    @property
    def _llm_type(self) -> str:
        return MODEL_ID

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        answered = sum(isinstance(message, AIMessage) for message in messages)
        if answered >= len(self.turns):
            raise ValueError(f"the script holds {len(self.turns)} turns, turn {answered + 1} asked")
        turn = self.turns[answered]
        self._count(answered + 1)
        witness("model_request", turn=answered + 1)
        calls = [
            {"name": call.tool, "args": call.arguments, "id": f"tooluse_{answered + 1}_{index}"}
            for index, call in enumerate(turn.tool_calls, start=1)
        ]
        blocks: list[str | dict[str, Any]] = (
            [{"type": "text", "text": turn.text}] if turn.text else []
        )
        blocks += [
            {"type": "tool_use", "name": call["name"], "input": call["args"], "id": call["id"]}
            for call in calls
        ]
        unparsed = [
            {
                "type": "invalid_tool_call",
                "name": name,
                "args": raw,
                "id": f"tooluse_{answered + 1}_u{index}",
                "error": None,
            }
            for index, (name, raw) in enumerate(turn.unparsed, start=1)
        ]
        blocks += [
            {"type": "tool_use", "name": call["name"], "input": call["args"], "id": call["id"]}
            for call in unparsed
        ]
        message = AIMessage(
            content=blocks if calls or unparsed else turn.text,
            tool_calls=calls,
            invalid_tool_calls=unparsed,
            response_metadata={
                "stopReason": turn.stop_reason,
                "metrics": {"latencyMs": [turn.latency_ms]},
            },
            usage_metadata={
                "input_tokens": turn.input_tokens,
                "output_tokens": turn.output_tokens,
                "total_tokens": turn.input_tokens + turn.output_tokens,
            },
        )
        witness("model_response", turn=answered + 1)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _count(self, turn: int) -> None:
        with open(self.count_file, "a", encoding="utf-8") as record:
            record.write(json.dumps({"turn": turn, "pid": os.getpid()}) + "\n")
            record.flush()
            os.fsync(record.fileno())


def reported_usage(message: AIMessage) -> dict[str, int] | None:
    """The counters the scripted provider reported for ``message``: its input and output tokens,
    which for this model are exactly what the turn declared."""
    usage = message.usage_metadata
    if usage is None:
        return None
    return {name: usage[name] for name in ("input_tokens", "output_tokens")}


def requests_counted(count_file: str) -> list[int]:
    """The turn of each invocation the count file records, in order; none when it is absent."""
    if not os.path.exists(count_file):
        return []
    with open(count_file, encoding="utf-8") as record:
        return [json.loads(line)["turn"] for line in record if line.strip()]
