"""The investigator's two live clients over Bedrock: the Converse client a dispatch sends
through and the counting client a request is bounded by, each making one send per call.

A dispatch permits zero or one physical send (``core.model_calls``): the run's cost and cap
are counted in dispatches, and a retry beneath one would be a send the log never saw. The
SDK retries on its own unless told not to, and the prose clients let it (three standard
attempts, their faults being the materializer's to retry). The clients here share a runtime
client built with one total attempt, so a dispatch sends zero or once and every retry is
the logged re-dispatch policy's; the SDK reports the configuration back, and the transport
test reads it there and proves it at the SDK's own ``before-send`` hook, never on a network.

The Converse client sends the body as the turns built it and keeps the answer as the
service sent it: the SDK's response metadata, the retry count and the request id, moves into
the observation, and the rest is the response the answer parser reads. What arrived is
mapped to the observation types: a complete response; a service error with its status,
code, the original status a relayed model error carries and the message's signature; a
client-side failure, a timeout or a lost connection, recorded by the exception's qualified
type alone, since the job's log is public and a message can quote a value; and the SDK's
own parameter refusal, which sends nothing. Any other exception is none of these and
escapes to the driver's unhandled defect. A broken stream cannot occur under this client,
which does not stream. The attribution of each observation is the registered table's, read
by the graph, never here. The digest of the bytes that left comes from the ``before-send``
hook the spike's capture used, so the record can name what was sent and not only what was
built.

The counting client asks ``CountTokens`` for the projection the registered method counts,
under the counting identifier the role names (a base model id: the service counts for a
model and refuses an inference profile). The service reports no latency for a count, so the
client measures its own. Its failures map to the counting outcomes the same way, and an
exception that is neither a service answer nor a timeout nor a lost connection is the local
error the counting contract names, recorded by type and read as unclassified.
"""

from __future__ import annotations

import hashlib
import time
from typing import TYPE_CHECKING, Any, cast

import boto3
from botocore import exceptions as sdk
from botocore.config import Config

from leaveimpact.core.counting_operations import (
    CountClientError,
    Counted,
    CountLocalError,
    CountOutcome,
    CountServiceError,
)
from leaveimpact.core.jsonshape import JsonObject, integer_field, object_field, string_field
from leaveimpact.core.model_calls import (
    ClientError,
    CompleteResponse,
    Observation,
    RefusedBeforeSend,
    Sent,
    ServiceError,
    message_signature,
)
from leaveimpact.core.run_trace import ClientErrorKind

if TYPE_CHECKING:
    from collections.abc import Mapping

    from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

CONVERSE = "Converse"
"""The operation the Converse client names in every intent."""

TOTAL_ATTEMPTS = 1
"""The attempts the clients' SDK configuration allows in total, the first one counted."""


def inference_client(region: str) -> BedrockRuntimeClient:
    """The runtime client the two clients share, on the ambient credentials, with one total
    attempt so the SDK never sends twice beneath a dispatch or a count."""
    return boto3.client(  # pyright: ignore[reportUnknownMemberType]
        "bedrock-runtime",
        region_name=region,
        config=Config(retries={"mode": "standard", "total_max_attempts": TOTAL_ATTEMPTS}),
    )


class ConverseClient:
    """The graph's ``ModelClient`` over ``Converse``: the body as the turns built it, one
    send, the answer as it arrived."""

    def __init__(self, client: BedrockRuntimeClient) -> None:
        self._client = client
        self._sent_digest: str | None = None
        # Registered first so the digest is taken before any later hook answers or fails
        # the send; a hook that raises in its place would otherwise leave the bytes unseen.
        client.meta.events.register_first(
            f"before-send.bedrock-runtime.{CONVERSE}", self._before_send
        )

    @property
    def operation(self) -> str:
        return CONVERSE

    @property
    def client_region(self) -> str:
        return str(self._client.meta.region_name)

    def send(self, requested_profile: str, body: JsonObject) -> Sent:
        """One send of ``body`` to ``requested_profile``; the observation of what came back,
        the response when one did, and the digest of the bytes that left when any did."""
        self._sent_digest = None
        try:
            response = cast(
                "dict[str, Any]",
                self._client.converse(modelId=requested_profile, **body),  # type: ignore[arg-type]
            )
        except sdk.ClientError as error:
            return Sent(_service_error(error), None, self._sent_digest)
        except sdk.ParamValidationError as error:
            return Sent(RefusedBeforeSend(_qualified_type(error)), None, None)
        except (sdk.HTTPClientError, sdk.ConnectionError) as error:
            return Sent(_client_error(error), None, self._sent_digest)
        metadata = cast("dict[str, Any]", response.pop("ResponseMetadata", {}))
        return Sent(_complete(response, metadata), response, self._sent_digest)

    def _before_send(self, request: Any, **_: Any) -> None:
        raw = request.body or b""
        body = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        self._sent_digest = hashlib.sha256(body).hexdigest()


class CountingClient:
    """The graph's ``TokenCounter`` over ``CountTokens``: the projection counted under the
    role's counting identifier, one request, its latency measured here."""

    def __init__(self, client: BedrockRuntimeClient) -> None:
        self._client = client

    def count(self, counting_identifier: str, projection: Mapping[str, object]) -> CountOutcome:
        started = time.monotonic()
        try:
            response = cast(
                "dict[str, Any]",
                self._client.count_tokens(
                    modelId=counting_identifier,
                    input={"converse": dict(projection)},  # type: ignore[arg-type]
                ),
            )
        except sdk.ClientError as error:
            return _count_service_error(error, _elapsed_ms(started))
        except (sdk.HTTPClientError, sdk.ConnectionError) as error:
            return CountClientError(_client_error_kind(error), _elapsed_ms(started))
        except Exception as error:
            return CountLocalError(_qualified_type(error))
        metadata = cast("dict[str, Any]", response.get("ResponseMetadata", {}))
        return Counted(
            integer_field(response, "inputTokens"),
            _request_id(metadata),
            _elapsed_ms(started),
        )


# --- The mapping of what arrived ---------------------------------------------------------


def _complete(response: Mapping[str, object], metadata: Mapping[str, object]) -> Observation:
    metrics = object_field(response, "metrics")
    return CompleteResponse(
        string_field(response, "stopReason"),
        integer_field(metrics, "latencyMs"),
        _retry_count(metadata),
        _request_id(metadata),
    )


def _service_error(error: sdk.ClientError) -> ServiceError:
    response = cast("dict[str, Any]", error.response)
    held = cast("dict[str, Any]", response.get("Error", {}))
    metadata = cast("dict[str, Any]", response.get("ResponseMetadata", {}))
    original = response.get("originalStatusCode")
    return ServiceError(
        int(metadata.get("HTTPStatusCode", 0)),
        str(held.get("Code", "")),
        int(original) if isinstance(original, int) else None,
        message_signature(str(held.get("Message", ""))),
        _retry_count(metadata),
        _request_id(metadata),
    )


def _count_service_error(error: sdk.ClientError, latency_ms: int) -> CountServiceError:
    service = _service_error(error)
    return CountServiceError(
        service.http_status,
        service.code,
        service.message_signature,
        service.provider_request_id,
        latency_ms,
    )


def _client_error(error: Exception) -> ClientError:
    return ClientError(_client_error_kind(error), _qualified_type(error))


def _client_error_kind(error: Exception) -> ClientErrorKind:
    """A timeout is one the SDK names so, on connecting or on reading; every other transport
    failure is a connection one: whether the request ran is unknown either way."""
    if isinstance(error, sdk.ReadTimeoutError | sdk.ConnectTimeoutError):
        return ClientErrorKind.TIMEOUT
    return ClientErrorKind.CONNECTION


def _retry_count(metadata: Mapping[str, object]) -> int | None:
    value = metadata.get("RetryAttempts")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _request_id(metadata: Mapping[str, object]) -> str | None:
    value = metadata.get("RequestId")
    return value if isinstance(value, str) and value else None


def _qualified_type(error: BaseException) -> str:
    kind = type(error)
    return f"{kind.__module__}.{kind.__qualname__}"


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


__all__ = [
    "CONVERSE",
    "TOTAL_ATTEMPTS",
    "ConverseClient",
    "CountingClient",
    "inference_client",
]
