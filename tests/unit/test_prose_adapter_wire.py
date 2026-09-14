"""The Converse translation against botocore's stub: the writer's request pinned whole, its text
read from the answer's blocks under an end_turn stop, a truncated or empty answer refused; the
checker's request carrying exactly one tool with the choice forced, its input returned as
filled, a missing, doubled or misnamed tool call refused; the service's codes mapped onto the
closed faults — throttling unreachable, access refused, validation misconfigured."""

from collections.abc import Callable
from functools import partial
from typing import Any

import boto3
import pytest
from botocore.stub import Stubber

from leaveimpact.adapters.prose import (
    BedrockChecker,
    BedrockWriter,
    CheckerRequest,
    InferenceConfiguration,
    ModelAccessRefused,
    ModelMisconfigured,
    ModelProtocolFault,
    ModelUnreachable,
    ToolSpec,
    WriterRequest,
)
from leaveimpact.world.prose import Setting

WRITER_MODEL = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
CHECKER_MODEL = "eu.amazon.nova-pro-v1:0"
WRITE = WriterRequest("You write ticket comments.", "Write one.", InferenceConfiguration(0.7, 400))
TOOL = ToolSpec(
    "record_propositions",
    "Every proposition the text makes.",
    {"type": "object", "properties": {"propositions": {"type": "array"}}},
)
CHECK = CheckerRequest("You read texts.", "Read this.", TOOL, InferenceConfiguration(0, 800))
USAGE = {"inputTokens": 120, "outputTokens": 45, "totalTokens": 165}
METRICS = {"latencyMs": 812}


def _client() -> Any:
    return boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "bedrock-runtime",
        region_name="eu-central-1",
        aws_access_key_id="stub",
        aws_secret_access_key="stub",
    )


def _writer() -> tuple[BedrockWriter, Stubber]:
    client = _client()
    return BedrockWriter(client, WRITER_MODEL), Stubber(client)


def _checker() -> tuple[BedrockChecker, Stubber]:
    client = _client()
    return BedrockChecker(client, CHECKER_MODEL), Stubber(client)


def _with[T](stub: Stubber, action: Callable[[], T]) -> T:
    with stub:
        result = action()
        stub.assert_no_pending_responses()
    return result


def _answer(content: list[dict[str, Any]], stop: str) -> dict[str, Any]:
    return {
        "output": {"message": {"role": "assistant", "content": content}},
        "stopReason": stop,
        "usage": USAGE,
        "metrics": METRICS,
    }


WRITER_PARAMS: dict[str, Any] = {
    "modelId": WRITER_MODEL,
    "system": [{"text": WRITE.system}],
    "messages": [{"role": "user", "content": [{"text": WRITE.message}]}],
    "inferenceConfig": {"temperature": 0.7, "maxTokens": 400},
}

CHECKER_PARAMS: dict[str, Any] = {
    "modelId": CHECKER_MODEL,
    "system": [{"text": CHECK.system}],
    "messages": [{"role": "user", "content": [{"text": CHECK.message}]}],
    "inferenceConfig": {"temperature": 0, "maxTokens": 800},
    "toolConfig": {
        "tools": [
            {
                "toolSpec": {
                    "name": TOOL.name,
                    "description": TOOL.description,
                    "inputSchema": {"json": TOOL.input_schema},
                }
            }
        ],
        "toolChoice": {"any": {}},
    },
}


# --- The writer -----------------------------------------------------------------------------


def test_the_writer_sends_exactly_the_request_and_reads_the_text_blocks_whole() -> None:
    writer, stub = _writer()
    stub.add_response(
        "converse",
        _answer([{"text": "Deniz ran "}, {"text": "the Kafka side."}], "end_turn"),
        WRITER_PARAMS,
    )
    written = _with(stub, partial(writer.write, WRITE))
    assert written.text == "Deniz ran the Kafka side."
    assert (written.usage.input_tokens, written.usage.output_tokens, written.usage.latency_ms) == (
        120,
        45,
        812,
    )


def test_top_p_is_sent_only_when_set_and_every_setting_sent_is_recorded() -> None:
    writer, stub = _writer()
    request = WriterRequest(
        WRITE.system, WRITE.message, InferenceConfiguration(0.7, 400, top_p=0.9)
    )
    stub.add_response(
        "converse",
        _answer([{"text": "ok"}], "end_turn"),
        {**WRITER_PARAMS, "inferenceConfig": {"temperature": 0.7, "maxTokens": 400, "topP": 0.9}},
    )
    _with(stub, lambda: writer.write(request))
    assert request.inference.settings() == (
        Setting("temperature", 0.7),
        Setting("max_tokens", 400),
        Setting("top_p", 0.9),
    )
    assert WRITE.inference.settings() == (Setting("temperature", 0.7), Setting("max_tokens", 400))


def test_a_text_cut_at_the_ceiling_or_empty_is_a_protocol_fault() -> None:
    writer, stub = _writer()
    stub.add_response("converse", _answer([{"text": "Deniz ran the"}], "max_tokens"), WRITER_PARAMS)
    with pytest.raises(ModelProtocolFault, match="cut at the token ceiling"):
        _with(stub, partial(writer.write, WRITE))
    writer, stub = _writer()
    stub.add_response("converse", _answer([{"text": "   "}], "end_turn"), WRITER_PARAMS)
    with pytest.raises(ModelProtocolFault, match="carries no text"):
        _with(stub, partial(writer.write, WRITE))


# --- The checker ----------------------------------------------------------------------------


def _tool_use(name: str, payload: Any) -> dict[str, Any]:
    return {"toolUse": {"toolUseId": "tool-1", "name": name, "input": payload}}


def test_the_checker_forces_one_tool_and_returns_its_input_as_filled() -> None:
    checker, stub = _checker()
    filled = {"propositions": [{"subject": "emp_023", "predicate": "has_skill", "value": "kafka"}]}
    stub.add_response(
        "converse", _answer([_tool_use(TOOL.name, filled)], "tool_use"), CHECKER_PARAMS
    )
    call = _with(stub, partial(checker.extract, CHECK))
    assert call.input == filled
    assert call.usage.latency_ms == 812


def test_a_missing_doubled_or_misnamed_tool_call_is_a_protocol_fault() -> None:
    for content, stop, reason in (
        (
            [{"text": "I would rather explain."}],
            "end_turn",
            "stopped on 'end_turn' where a tool call was forced",
        ),
        (
            [_tool_use(TOOL.name, {}), _tool_use(TOOL.name, {})],
            "tool_use",
            "expected one tool call, got 2",
        ),
        ([_tool_use("other_tool", {})], "tool_use", "called 'other_tool'"),
        ([_tool_use(TOOL.name, "not an object")], "tool_use", "not a JSON object"),
    ):
        checker, stub = _checker()
        stub.add_response("converse", _answer(content, stop), CHECKER_PARAMS)
        with pytest.raises(ModelProtocolFault, match=reason):
            _with(stub, partial(checker.extract, CHECK))


# --- Faults ---------------------------------------------------------------------------------


def test_service_codes_map_onto_the_closed_faults() -> None:
    for code, status, fault in (
        ("ThrottlingException", 429, ModelUnreachable),
        ("ModelTimeoutException", 408, ModelUnreachable),
        ("InternalServerException", 500, ModelUnreachable),
        ("AccessDeniedException", 403, ModelAccessRefused),
        ("ValidationException", 400, ModelMisconfigured),
        ("ResourceNotFoundException", 404, ModelMisconfigured),
    ):
        writer, stub = _writer()
        stub.add_client_error(
            "converse",
            service_error_code=code,
            service_message=f"{code} happened",
            http_status_code=status,
            expected_params=WRITER_PARAMS,
        )
        with pytest.raises(fault):
            _with(stub, partial(writer.write, WRITE))


def test_a_request_is_not_blank_and_the_settings_are_bounded() -> None:
    with pytest.raises(ValueError, match="system text is not blank"):
        WriterRequest("  ", "hi", InferenceConfiguration(0.5, 10))
    with pytest.raises(ValueError, match="temperature lies in"):
        InferenceConfiguration(1.5, 10)
    with pytest.raises(ValueError, match="max_tokens is at least one"):
        InferenceConfiguration(0.5, 0)
