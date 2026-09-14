"""The writer and the checker over Bedrock's Converse API: one translation, two callers.

Converse is the model-agnostic surface of Bedrock — the same request shape for an Anthropic
model and an Amazon one — which is what lets the writer's family and the checker's differ
without two adapters (the independence claim of the extraction check). A request becomes
one ``converse`` call: the system text, one user message, the inference configuration, and
for the checker a tool configuration with exactly one tool and the choice set to *any*, which
with one tool is a forced call. *Any* rather than naming the tool because it is the choice
every model family on the shortlist honours; naming a tool is honoured by some and refused by
others, and a forced call is the property wanted, not the spelling. Verified live from the
workstation on 2026-09-14 for both families on the shortlist (the ``live`` tests, under an
administrator identity); the generator role's own path is exercised by the probe workflow
of the step's last part, which is the authoritative run.

The answer is read strictly. The writer's text is the concatenation of the answer's text
blocks and must be non-empty under a stop reason of ``end_turn``; a ``max_tokens`` stop is a
truncated text and a fault, since a text the ceiling cut cannot be judged whole. The
checker's answer must stop on ``tool_use`` and carry one ``toolUse`` block naming the forced
tool, whose input is the JSON object the model filled; anything else is
``ModelProtocolFault``. Usage and latency come from the response's own fields.

The SDK's standard retries run first; what remains is classified by the service's error
codes, observed in the docs and to be confirmed by the probe: throttling, the service and
model failures and timeouts are ``ModelUnreachable``; ``AccessDeniedException`` is
``ModelAccessRefused``; a validation or not-found rejection and every other client-side
fault is ``ModelMisconfigured``. Credentials are ambient, from the role, never a parameter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError, HTTPClientError
from botocore.exceptions import ConnectionError as TransportConnectionError

from leaveimpact.adapters.prose.seam import (
    CheckerRequest,
    InferenceConfiguration,
    ModelAccessRefused,
    ModelMisconfigured,
    ModelProtocolFault,
    ModelUnreachable,
    ToolCall,
    ToolSpec,
    Usage,
    WriterRequest,
    WrittenText,
)
from leaveimpact.core.jsonshape import JsonObject

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

UNREACHABLE_CODES: frozenset[str] = frozenset(
    {
        "ThrottlingException",
        "ServiceUnavailableException",
        "InternalServerException",
        "ModelTimeoutException",
        "ModelNotReadyException",
        "ModelErrorException",
        "ServiceQuotaExceededException",
    }
)
"""The service's transient answers: the materializer's bounded retry is the response to them."""


def bedrock_client(region: str) -> BedrockRuntimeClient:
    """The runtime client on the ambient credentials, the SDK's standard retries on."""
    return boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "bedrock-runtime",
        region_name=region,
        config=Config(retries={"mode": "standard", "max_attempts": 3}),
    )


class BedrockWriter:
    """``ProseWriter`` over one model id."""

    def __init__(self, client: BedrockRuntimeClient, model_id: str) -> None:
        self._client = client
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def write(self, request: WriterRequest) -> WrittenText:
        response = _converse(
            self._client, self._model_id, request.system, request.message, request.inference, None
        )
        stop = _stop_reason(response)
        if stop == "max_tokens":
            raise ModelProtocolFault(self._model_id, "the text was cut at the token ceiling")
        if stop != "end_turn":
            raise ModelProtocolFault(self._model_id, f"stopped on {stop!r}, not end_turn")
        text = "".join(_text_blocks(response))
        if not text.strip():
            raise ModelProtocolFault(self._model_id, "the answer carries no text")
        return WrittenText(text, _usage(response))


class BedrockChecker:
    """``ProseChecker`` over one model id: the forced tool's input, as the model filled it."""

    def __init__(self, client: BedrockRuntimeClient, model_id: str) -> None:
        self._client = client
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def extract(self, request: CheckerRequest) -> ToolCall:
        response = _converse(
            self._client,
            self._model_id,
            request.system,
            request.message,
            request.inference,
            request.tool,
        )
        stop = _stop_reason(response)
        if stop != "tool_use":
            raise ModelProtocolFault(
                self._model_id, f"stopped on {stop!r} where a tool call was forced"
            )
        calls = [_object(block, "toolUse") for block in _content(response) if "toolUse" in block]
        if len(calls) != 1:
            raise ModelProtocolFault(self._model_id, f"expected one tool call, got {len(calls)}")
        [call] = calls
        name = call.get("name")
        if name != request.tool.name:
            raise ModelProtocolFault(self._model_id, f"called {name!r}, not {request.tool.name!r}")
        payload = call.get("input")
        if not isinstance(payload, dict):
            raise ModelProtocolFault(self._model_id, "the tool input is not a JSON object")
        return ToolCall(cast(JsonObject, payload), _usage(response))


# --- The one translation --------------------------------------------------------------------


def _converse(
    client: BedrockRuntimeClient,
    model_id: str,
    system: str,
    message: str,
    inference: InferenceConfiguration,
    tool: ToolSpec | None,
) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "modelId": model_id,
        "system": [{"text": system}],
        "messages": [{"role": "user", "content": [{"text": message}]}],
        "inferenceConfig": _inference(inference),
    }
    if tool is not None:
        arguments["toolConfig"] = {
            "tools": [
                {
                    "toolSpec": {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": {"json": tool.input_schema},
                    }
                }
            ],
            "toolChoice": {"any": {}},
        }
    try:
        return cast(dict[str, Any], client.converse(**arguments))
    except ClientError as error:
        raise _client_fault(model_id, error) from error
    except (TransportConnectionError, HTTPClientError) as error:
        raise ModelUnreachable(model_id) from error
    except BotoCoreError as error:
        raise ModelMisconfigured(model_id, f"{type(error).__name__}: {error}") from error


def _inference(inference: InferenceConfiguration) -> dict[str, Any]:
    config: dict[str, Any] = {
        "temperature": inference.temperature,
        "maxTokens": inference.max_tokens,
    }
    if inference.top_p is not None:
        config["topP"] = inference.top_p
    return config


def _client_fault(model_id: str, error: ClientError) -> Exception:
    response = cast("dict[str, Any]", error.response)
    code = str(response.get("Error", {}).get("Code", ""))
    message = str(response.get("Error", {}).get("Message", code))
    if code == "AccessDeniedException":
        return ModelAccessRefused(model_id, message)
    if code in UNREACHABLE_CODES:
        return ModelUnreachable(model_id)
    status = int(response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0))
    if status >= 500:
        return ModelUnreachable(model_id)
    return ModelMisconfigured(model_id, f"{code}: {message}")


def _stop_reason(response: dict[str, Any]) -> str:
    return str(response.get("stopReason", ""))


def _object(data: dict[str, Any], key: str) -> dict[str, Any]:
    """The JSON object under ``key``, or an empty one; the SDK's answer is read defensively."""
    value = data.get(key)
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _content(response: dict[str, Any]) -> list[dict[str, Any]]:
    """The answer's content blocks that are objects, in order."""
    content = _object(_object(response, "output"), "message").get("content")
    if not isinstance(content, list):
        return []
    blocks = cast(list[Any], content)
    return [cast(dict[str, Any], block) for block in blocks if isinstance(block, dict)]


def _text_blocks(response: dict[str, Any]) -> list[str]:
    blocks = _content(response)
    return [str(block["text"]) for block in blocks if isinstance(block.get("text"), str)]


def _usage(response: dict[str, Any]) -> Usage:
    usage = _object(response, "usage")
    metrics = _object(response, "metrics")
    return Usage(
        int(usage.get("inputTokens", 0)),
        int(usage.get("outputTokens", 0)),
        int(metrics.get("latencyMs", 0)),
    )


__all__ = ["UNREACHABLE_CODES", "BedrockChecker", "BedrockWriter", "bedrock_client"]
