"""What every provider probe stands on: the two model families, one asked question, one finding.

A probe asks through the pinned chat client, which is the thing under test, and then reads
the recorder's captured bytes for what was sent and returned. ``ask`` wraps one SDK call in
one logical invocation and never raises for what the call did: the message, or the exception,
comes back beside the invocation's send ids, so a probe states its finding from evidence and a
fault is a row, not a traceback.

``--offline`` replaces the network with a canned answer at botocore's ``before-send`` hook.
It exists to exercise the recorder, the guards and the probes' own logic without a send; it
proves nothing about a provider, cannot stream, and its rows are labelled.
"""

from __future__ import annotations

import io
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from botocore.awsrequest import AWSResponse
from botocore.compat import HTTPHeaders
from capture import REPOSITORY, Recorder, clients
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, BaseMessage
from surface import Choice, Translation, tool_config

if str(REPOSITORY) not in sys.path:
    # The throwaway world is the tests' fixture; a probe building its own would be a second
    # implementation of it. The repository root makes `tests` importable from this folder.
    sys.path.insert(0, str(REPOSITORY))

PROFILES: dict[str, str] = {
    "haiku": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
    "nova": "eu.amazon.nova-pro-v1:0",
}
REGION = "eu-central-1"
SYSTEM = "You look up records in an organization's systems with the tools you are given."


@dataclass(frozen=True, slots=True)
class Row:
    """One finding. ``kind`` is ``must-pass`` or ``measured``; a must-pass row's ``verdict``
    is ``pass`` or ``fail``, a measured row's is ``finding``. ``sends`` are capture
    identifiers, the only reference to a capture a public row carries."""

    probe: str
    family: str
    cell: str
    kind: str
    verdict: str
    detail: dict[str, Any]
    sends: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Asked:
    """One SDK call's result: the message it returned or the exception it raised."""

    sends: tuple[str, ...]
    message: AIMessage | None
    error: BaseException | None

    @property
    def error_code(self) -> str:
        """The service's error code, the exception's type name when the service gave none."""
        if self.error is None:
            return ""
        response = getattr(self.error, "response", None)
        code = response.get("Error", {}).get("Code") if isinstance(response, dict) else None
        return str(code) if code else type(self.error).__name__


@dataclass
class Bench:
    """One execution's recorder and clients, and each family's effective surface once found."""

    recorder: Recorder
    runtime: Any
    control: Any
    offline: bool = False
    surfaces: dict[str, Translation] = field(default_factory=dict[str, Translation])
    rows: list[Row] = field(default_factory=list[Row])

    def chat(self, family: str, *, max_tokens: int = 256, runtime: Any = None) -> Any:
        """The pinned chat client on ``family``'s profile, over clients this probe built."""
        return ChatBedrockConverse(
            model=PROFILES[family],
            client=runtime or self.runtime,
            bedrock_client=self.control,
            region_name=self.recorder.region,
            temperature=0,
            max_tokens=max_tokens,
        )

    def bound(self, family: str, choice: Choice, *, max_tokens: int = 256) -> Any:
        """The chat client with ``family``'s effective surface and ``choice`` bound."""
        return self.chat(family, max_tokens=max_tokens).bind(
            toolConfig=tool_config(self.surfaces[family], choice)
        )

    def ask(
        self,
        probe: str,
        label: str,
        model: Any,
        messages: Sequence[BaseMessage],
        *,
        streamed: bool = False,
    ) -> Asked:
        """One SDK call for ``probe``, consumed the way a caller consumes it."""
        with self.recorder.invocation(probe, label) as sends:
            try:
                if streamed:
                    total: Any = None
                    for chunk in model.stream(list(messages)):
                        total = chunk if total is None else total + chunk
                    message = total
                else:
                    message = model.invoke(list(messages))
            except Exception as error:
                return Asked(tuple(sends), None, error)
        return Asked(tuple(sends), message, None)

    def add(self, row: Row) -> Row:
        """Keep ``row``, write it beside the captures and print it."""
        self.rows.append(row)
        line = {
            "probe": row.probe,
            "family": row.family,
            "cell": row.cell,
            "kind": row.kind,
            "verdict": row.verdict,
            "detail": row.detail,
            "sends": list(row.sends),
            "offline": self.offline,
        }
        with (self.recorder.directory / "findings.jsonl").open("a", encoding="utf-8") as out:
            out.write(json.dumps(line, ensure_ascii=False, default=repr) + "\n")
        mark = "offline " if self.offline else ""
        print(f"{mark}{row.kind:9} {row.verdict:7} {row.probe:22} {row.family:6} {row.cell}")
        print(f"          {json.dumps(row.detail, ensure_ascii=False, default=repr)[:600]}")
        return row


def open_bench(recorder: Recorder, *, offline: bool, employee: str) -> Bench:
    """The execution's bench: live clients, or the canned responder when ``offline``."""
    if offline:
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "offline")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "offline")
    runtime, control = clients(recorder)
    if offline:
        _answer_offline(runtime, employee)
    return Bench(recorder, runtime, control, offline)


# --- The offline responder ------------------------------------------------------------------


class _Raw(io.BytesIO):
    """The body of a canned response, with the one method botocore reads it through."""

    def stream(self, **_: Any) -> Any:
        yield self.getvalue()


def _answer_offline(runtime: Any, employee: str) -> None:
    def respond(request: Any, **_: Any) -> AWSResponse:
        body = json.loads(request.body)
        choice = body.get("toolConfig", {}).get("toolChoice", {})
        answered = any(
            "toolResult" in block
            for message in body.get("messages", [])
            for block in message.get("content", [])
        )
        if ("any" in choice or "tool" in choice) and not answered:
            name = choice.get("tool", {}).get("name", "employee")
            arguments = {"id": employee} if name == "employee" else {}
            content: list[dict[str, Any]] = [
                {"toolUse": {"toolUseId": "offline-1", "name": name, "input": arguments}}
            ]
            stop = "tool_use"
        else:
            content, stop = [{"text": "ok"}], "end_turn"
        answer = {
            "output": {"message": {"role": "assistant", "content": content}},
            "stopReason": stop,
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
            "metrics": {"latencyMs": 1},
        }
        headers = HTTPHeaders()
        headers["content-type"] = "application/json"
        headers["x-amzn-requestid"] = "offline"
        return AWSResponse(request.url, 200, headers, _Raw(json.dumps(answer).encode("utf-8")))

    runtime.meta.events.register("before-send.bedrock-runtime.Converse", respond)
