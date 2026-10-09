"""The live clients prove one send per call at the SDK's own hook, and map what arrives.

Every case answers at botocore's ``before-send`` hook on a real runtime client with stub
credentials, as the spike's offline mode did, so the SDK's signing, parsing and retry
handling all run and no byte leaves the machine (the session is network-blocked besides).
The claims: a throttling answer the SDK's default client retries four times is sent once by
each client here, and the configuration the SDK reports says why; a complete answer is kept
as it arrived with the metadata moved into the observation and the digest of the bytes
that left; a service error, a timeout, a lost connection and the SDK's own parameter
refusal each map to their observation, the message signed and the exception named by type;
and the counting client maps the same ways, a local error included.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Callable
from typing import Any

import boto3
import pytest
from botocore.awsrequest import AWSResponse
from botocore.compat import HTTPHeaders
from botocore.exceptions import EndpointConnectionError, ReadTimeoutError

from leaveimpact.adapters.inference import (
    TOTAL_ATTEMPTS,
    ConverseClient,
    CountingClient,
    inference_client,
)
from leaveimpact.core.counting_operations import (
    CountClientError,
    Counted,
    CountLocalError,
    CountServiceError,
)
from leaveimpact.core.model_calls import (
    ClientError,
    CompleteResponse,
    RefusedBeforeSend,
    ServiceError,
)
from leaveimpact.core.run_trace import ClientErrorKind

REGION = "eu-central-1"
PROFILE = "eu.vendor.model-v1"
BODY: dict[str, Any] = {
    "system": [{"text": "investigate"}],
    "messages": [{"role": "user", "content": [{"text": "turn 1"}]}],
    "inferenceConfig": {"maxTokens": 256, "temperature": 0},
}
ANSWER: dict[str, Any] = {
    "output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
    "stopReason": "end_turn",
    "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
    "metrics": {"latencyMs": 840},
}

Script = Callable[[Any], Any]


class _Raw(io.BytesIO):
    """The body of a canned response, with the one method botocore reads it through."""

    def stream(self, **_: Any) -> Any:
        yield self.getvalue()


def canned(status: int, body: dict[str, Any], *, error: str | None = None) -> Script:
    def answer(request: Any) -> AWSResponse:
        headers = HTTPHeaders()
        headers["content-type"] = "application/json"
        headers["x-amzn-requestid"] = "req-1"
        if error is not None:
            headers["x-amzn-errortype"] = f"{error}:http://internal.amazon.com/coral/"
        return AWSResponse(request.url, status, headers, _Raw(json.dumps(body).encode("utf-8")))

    return answer


def raising(error: Exception) -> Script:
    def answer(request: Any) -> Any:
        raise error

    return answer


class Wire:
    """What left for one operation, each request's bytes and URL, answered by a script."""

    def __init__(self, client: Any, operation: str, script: Script) -> None:
        self.bodies: list[bytes] = []
        self.urls: list[str] = []
        self._script = script
        client.meta.events.register(f"before-send.bedrock-runtime.{operation}", self._respond)

    def _respond(self, request: Any, **_: Any) -> Any:
        raw = request.body or b""
        self.bodies.append(raw.encode("utf-8") if isinstance(raw, str) else bytes(raw))
        self.urls.append(str(request.url))
        return self._script(request)


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "stub")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "stub")
    return inference_client(REGION)


THROTTLE = canned(429, {"message": "Too many requests"}, error="ThrottlingException")


# --- One send per call -------------------------------------------------------------------


def test_the_shared_client_is_configured_for_one_attempt_in_total(runtime: Any) -> None:
    assert runtime.meta.config.retries == {"mode": "standard", "total_max_attempts": 1}
    assert TOTAL_ATTEMPTS == 1


def test_a_throttled_dispatch_is_sent_once_where_the_sdks_default_client_sends_five(
    runtime: Any,
) -> None:
    """The control: the SDK's default client, answered by the same canned throttle, retries
    to its legacy maximum; the single-attempt client sends exactly once, and the error's
    own metadata shows no retry."""
    default = boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "bedrock-runtime", region_name=REGION
    )
    control = Wire(default, "Converse", THROTTLE)
    with pytest.raises(Exception, match="ThrottlingException"):
        default.converse(modelId=PROFILE, **BODY)
    assert len(control.bodies) == 5

    wire = Wire(runtime, "Converse", THROTTLE)
    sent = ConverseClient(runtime).send(PROFILE, dict(BODY))
    assert len(wire.bodies) == 1
    assert sent.observation == ServiceError(
        429, "ThrottlingException", None, "Too many requests", 0, "req-1"
    )
    assert sent.response is None
    assert sent.sent_body_digest == hashlib.sha256(wire.bodies[0]).hexdigest()


def test_a_throttled_count_is_sent_once(runtime: Any) -> None:
    wire = Wire(runtime, "CountTokens", THROTTLE)
    outcome = CountingClient(runtime).count("vendor.model-v1", {"messages": []})
    assert len(wire.bodies) == 1
    assert isinstance(outcome, CountServiceError)
    assert (outcome.http_status, outcome.code, outcome.message_signature) == (
        429,
        "ThrottlingException",
        "Too many requests",
    )
    assert outcome.provider_request_id == "req-1"


# --- The Converse client's mapping -------------------------------------------------------


def test_a_complete_answer_is_kept_as_it_arrived_with_the_metadata_in_the_observation(
    runtime: Any,
) -> None:
    wire = Wire(runtime, "Converse", canned(200, ANSWER))
    client = ConverseClient(runtime)
    assert (client.operation, client.client_region) == ("Converse", REGION)
    sent = client.send(PROFILE, dict(BODY))
    assert sent.observation == CompleteResponse("end_turn", 840, 0, "req-1")
    assert sent.response == ANSWER
    assert sent.sent_body_digest == hashlib.sha256(wire.bodies[0]).hexdigest()
    # The body left as the turns built it; the profile travels in the URL, not the body.
    assert json.loads(wire.bodies[0]) == BODY
    assert PROFILE in wire.urls[0]


def test_a_relayed_model_error_carries_its_original_status_and_a_signed_message(
    runtime: Any,
) -> None:
    Wire(
        runtime,
        "Converse",
        canned(
            424,
            {
                "message": "Model produced invalid sequence as part of ToolUse (req 8f3a9c2e4b1d)",
                "originalStatusCode": 400,
                "resourceName": "arn:aws:bedrock:eu-central-1:123456789012:model/x",
            },
            error="ModelErrorException",
        ),
    )
    sent = ConverseClient(runtime).send(PROFILE, dict(BODY))
    assert sent.observation == ServiceError(
        424,
        "ModelErrorException",
        400,
        "Model produced invalid sequence as part of ToolUse (req #)",
        0,
        "req-1",
    )


def test_a_timeout_and_a_lost_connection_are_client_errors_named_by_type(runtime: Any) -> None:
    Wire(runtime, "Converse", raising(ReadTimeoutError(endpoint_url="https://x.invalid")))
    timed_out = ConverseClient(runtime).send(PROFILE, dict(BODY))
    assert timed_out.observation == ClientError(
        ClientErrorKind.TIMEOUT, "botocore.exceptions.ReadTimeoutError"
    )
    # The bytes left before the read stalled, so the digest is held.
    assert timed_out.sent_body_digest is not None

    other = inference_client(REGION)
    Wire(other, "Converse", raising(EndpointConnectionError(endpoint_url="https://x.invalid")))
    lost = ConverseClient(other).send(PROFILE, dict(BODY))
    assert lost.observation == ClientError(
        ClientErrorKind.CONNECTION, "botocore.exceptions.EndpointConnectionError"
    )


def test_the_sdks_own_parameter_refusal_sends_nothing(runtime: Any) -> None:
    wire = Wire(runtime, "Converse", canned(200, ANSWER))
    sent = ConverseClient(runtime).send(PROFILE, {"messages": "not a list"})
    assert sent.observation == RefusedBeforeSend("botocore.exceptions.ParamValidationError")
    assert (sent.response, sent.sent_body_digest) == (None, None)
    assert wire.bodies == []


# --- The counting client's mapping -------------------------------------------------------


def test_a_count_is_the_services_number_with_its_request_id_and_a_measured_latency(
    runtime: Any,
) -> None:
    wire = Wire(runtime, "CountTokens", canned(200, {"inputTokens": 1234}))
    outcome = CountingClient(runtime).count("vendor.model-v1", {"messages": [], "system": []})
    assert isinstance(outcome, Counted)
    assert (outcome.input_tokens, outcome.provider_request_id) == (1234, "req-1")
    assert outcome.latency_ms >= 0
    assert json.loads(wire.bodies[0]) == {"input": {"converse": {"messages": [], "system": []}}}
    assert "vendor.model-v1" in wire.urls[0]


def test_a_counts_transport_failure_and_a_local_error_map_to_their_outcomes(
    runtime: Any,
) -> None:
    Wire(runtime, "CountTokens", raising(ReadTimeoutError(endpoint_url="https://x.invalid")))
    timed_out = CountingClient(runtime).count("vendor.model-v1", {"messages": []})
    assert isinstance(timed_out, CountClientError)
    assert timed_out.kind is ClientErrorKind.TIMEOUT

    local = inference_client(REGION)
    Wire(local, "CountTokens", raising(KeyError("a field the harness got wrong")))
    assert CountingClient(local).count("vendor.model-v1", {"messages": []}) == CountLocalError(
        "builtins.KeyError"
    )
