"""The two prose models reached for real, structurally: the writer returns non-empty text and the
checker fills the forced tool with a JSON object. Deliberately weak — connectivity and schema
compatibility, never quality, which the materializer's gates and the hand audit judge. Skipped
when the process holds no AWS credentials at all; with credentials present an access refusal
fails, because that is a finding about the principal and not an absence of setup. The
authoritative run is the probe workflow under the generator role; this is the workstation's
convenience when its identity happens to be granted."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import boto3
import pytest

from leaveimpact.adapters.prose import (
    BedrockChecker,
    BedrockWriter,
    CheckerRequest,
    InferenceConfiguration,
    ToolSpec,
    WriterRequest,
    bedrock_client,
)

if TYPE_CHECKING:
    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

pytestmark = pytest.mark.live

REGION = os.environ.get("LEAVE_IMPACT_BEDROCK_REGION", "eu-central-1")
HAIKU = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
WRITER_MODEL = os.environ.get("LEAVE_IMPACT_PROSE_WRITER_MODEL", HAIKU)
CHECKER_MODEL = os.environ.get("LEAVE_IMPACT_PROSE_CHECKER_MODEL", "eu.amazon.nova-pro-v1:0")


@pytest.fixture(scope="module")
def client() -> BedrockRuntimeClient:
    if boto3.Session().get_credentials() is None:  # pyright: ignore[reportUnknownMemberType]
        pytest.skip("no AWS credentials in this process; the probe workflow is the live evidence")
    return bedrock_client(REGION)


def test_the_writer_answers_with_text(client: BedrockRuntimeClient) -> None:
    written = BedrockWriter(client, WRITER_MODEL).write(
        WriterRequest(
            "You answer in one short sentence.",
            "Say that the retry queue migration is on track.",
            InferenceConfiguration(0.7, 100),
        )
    )
    assert written.text.strip()
    assert written.usage.output_tokens > 0


def test_the_checker_fills_the_forced_tool(client: BedrockRuntimeClient) -> None:
    tool = ToolSpec(
        "record_words",
        "Record every capitalized word in the text.",
        {
            "type": "object",
            "properties": {"words": {"type": "array", "items": {"type": "string"}}},
            "required": ["words"],
        },
    )
    call = BedrockChecker(client, CHECKER_MODEL).extract(
        CheckerRequest(
            "You extract what the tool asks and call it exactly once.",
            "Deniz moved the Kafka topics to Frankfurt.",
            tool,
            InferenceConfiguration(0, 200),
        )
    )
    assert isinstance(call.input.get("words"), list)
