"""The capture client of the acceptance spike's provider probes: every send recorded at the wire.

The probes read what was sent and what came back, never the chat client's mapped fields: the
client defaults an absent cache counter to zero and drops the raw usage object, so absent
against zero survives only here. The recorder hangs on botocore's event system, the public
hook surface the chat client itself uses for its headers:

- ``before-send`` holds the prepared request. The body is written as sent, its SHA-256 is the
  request digest, and the send guards run here, before anything leaves the machine.
- ``before-parse`` holds a non-streamed response's complete body, written as received.
- ``after-call`` holds the parsed result. A streamed result's event stream is replaced by one
  that copies each parsed event as the caller consumes it, so the caller reads the stream
  normally and a stream that ends early or raises is recorded as far as it got.

Three things are kept apart. A *logical invocation* is one SDK call a probe makes, opened with
``Recorder.invocation``. A *send* is one HTTP request botocore made for it; retries are further
sends of the same invocation, each with its own evidence, and a request botocore refuses
before sending has none. An *outcome* is what is known of a send: a response, a service error,
or nothing at all, which stays unresolved and is never counted as zero usage.

The record is one append-only JSON-lines file across executions, a ``send`` line when a request
leaves and an ``outcome`` line when its result is known. The cumulative guard counts the
``send`` lines. Captures hold model requests and responses and live outside the repository:
the directory comes from ``LEAVE_IMPACT_SPIKE_CAPTURES`` and is refused if it resolves inside
the tree.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import boto3
from botocore.config import Config

REPOSITORY = Path(__file__).resolve().parents[2]
CAPTURES_VARIABLE = "LEAVE_IMPACT_SPIKE_CAPTURES"
OVERRIDE_VARIABLE = "LEAVE_IMPACT_SPIKE_OVERRIDE_CUMULATIVE"

SENDS_PER_EXECUTION = 150
CUMULATIVE_SENDS = 1_000
BODY_BYTES_CEILING = 400_000
OUTPUT_TOKENS_CEILING = 1_024

TRACING_VARIABLES = (
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGCHAIN_TRACING_V2",
)
"""Set to ``true``, any of these ships request bodies to a third party."""

USAGE_COUNTERS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheWriteInputTokens")
OPERATIONS = ("Converse", "ConverseStream")


class SendGuard(RuntimeError):
    """A send was stopped before it left: a guard against a loop bug, not a budget."""


# --- Pure helpers ---------------------------------------------------------------------------


def body_digest(body: bytes) -> str:
    """SHA-256 of the HTTP body as sent, headers excluded.

    >>> body_digest(b"{}")
    '44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'
    """
    return hashlib.sha256(body).hexdigest()


def counter_states(usage: object) -> dict[str, str]:
    """Each usage counter as ``present``, ``zero`` or ``absent`` in a raw usage object.

    >>> counter_states({"inputTokens": 12, "outputTokens": 0})["outputTokens"]
    'zero'
    >>> counter_states({"inputTokens": 12})["cacheReadInputTokens"]
    'absent'
    """
    held = usage if isinstance(usage, dict) else {}
    states: dict[str, str] = {}
    for name in USAGE_COUNTERS:
        if name not in held:
            states[name] = "absent"
        elif held[name] == 0:
            states[name] = "zero"
        else:
            states[name] = "present"
    return states


def model_in(url: str) -> str:
    """The model or profile a runtime URL addresses, which the body does not carry.

    >>> model_in("https://bedrock-runtime.eu-central-1.amazonaws.com/model/eu.a.b%3A0/converse")
    'eu.a.b:0'
    """
    parts = urlsplit(url).path.split("/")
    return unquote(parts[2]) if len(parts) > 2 and parts[1] == "model" else ""


def capture_root() -> Path:
    """The private capture directory, created; refused when it resolves inside the repository."""
    named = os.environ.get(CAPTURES_VARIABLE, "").strip()
    if not named:
        raise SystemExit(f"{CAPTURES_VARIABLE} names the private capture directory; it is unset")
    root = Path(named).resolve()
    if root == REPOSITORY or REPOSITORY in root.parents:
        raise SystemExit(f"captures are held outside the repository; {root} resolves inside it")
    root.mkdir(parents=True, exist_ok=True)
    return root


def require_tracing_off() -> None:
    """Refuse to start while any tracing variable is set, whatever its value."""
    held = [name for name in TRACING_VARIABLES if os.environ.get(name) is not None]
    if held:
        raise SystemExit(f"tracing variables are unset before any send, found {', '.join(held)}")


# --- The recorder ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Invocation:
    """One logical invocation as its sends left it: what a probe reads after the SDK call."""

    id: str
    probe: str
    label: str
    sends: tuple[str, ...]


@dataclass
class Recorder:
    """The sends of one execution, written under ``root`` as they happen.

    State with a lifecycle: the execution's counters, the invocation in progress, and the
    append-only record shared by every execution of the spike.
    """

    root: Path
    region: str
    execution: str = field(
        default_factory=lambda: (
            datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
        )
    )
    offline: bool = False
    sends_made: int = 0
    _invocations: int = 0
    _current: tuple[str, str, str] | None = None
    _current_sends: list[str] = field(default_factory=list[str])
    _streamed: set[str] = field(default_factory=set[str])
    finished: list[Invocation] = field(default_factory=list[Invocation])

    def __post_init__(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)

    @property
    def directory(self) -> Path:
        return self.root / self.execution

    @property
    def record(self) -> Path:
        return self.root / "sends.jsonl"

    def cumulative_sends(self) -> int:
        """Live sends recorded by every execution so far, this one included. A send an
        offline execution answered itself never left the machine and is not counted."""
        if not self.record.exists():
            return 0
        with self.record.open(encoding="utf-8") as lines:
            held = map(json.loads, lines)
            return sum(
                1 for line in held if line.get("event") == "send" and not line.get("offline")
            )

    @contextmanager
    def invocation(self, probe: str, label: str) -> Iterator[list[str]]:
        """One SDK call made for ``probe``; yields the list its send ids are appended to."""
        if self._current is not None:
            raise RuntimeError("an invocation holds one SDK call; one is already open")
        self._invocations += 1
        identifier = f"{self.execution}-i{self._invocations:03d}"
        self._current = (identifier, probe, label)
        self._current_sends = []
        try:
            yield self._current_sends
        finally:
            self.finished.append(Invocation(identifier, probe, label, tuple(self._current_sends)))
            self._current = None

    def attach(self, client: Any) -> None:
        """Register the three hooks on a runtime client for both Converse operations."""
        events = client.meta.events
        for operation in OPERATIONS:
            events.register(f"before-send.bedrock-runtime.{operation}", self._before_send)
            events.register(f"before-parse.bedrock-runtime.{operation}", self._before_parse)
            events.register(f"after-call.bedrock-runtime.{operation}", self._after_call)

    # --- Hooks ------------------------------------------------------------------------------

    def _before_send(self, request: Any, **_: Any) -> None:
        if self._current is None:
            raise SendGuard("a send belongs to an invocation; none is open")
        raw = request.body or b""
        body = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        self._guard(body)
        identifier, probe, label = self._current
        self.sends_made += 1
        send = f"{identifier}-s{len(self._current_sends) + 1}"
        self._current_sends.append(send)
        (self.directory / f"{send}.request.json").write_bytes(body)
        self._append(
            {
                "event": "send",
                "send": send,
                "invocation": identifier,
                "attempt": len(self._current_sends),
                "execution": self.execution,
                "offline": self.offline,
                "probe": probe,
                "label": label,
                "at": datetime.now(UTC).isoformat(),
                "operation": "ConverseStream" if request.url.endswith("-stream") else "Converse",
                "requested_model": model_in(request.url),
                "region": self.region,
                "body_sha256": body_digest(body),
                "body_bytes": len(body),
            }
        )

    def _guard(self, body: bytes) -> None:
        if self.sends_made >= SENDS_PER_EXECUTION:
            raise SendGuard(f"{SENDS_PER_EXECUTION} sends in one execution; stopping")
        if self.cumulative_sends() >= CUMULATIVE_SENDS and not os.environ.get(OVERRIDE_VARIABLE):
            raise SendGuard(
                f"{CUMULATIVE_SENDS} sends across executions; set {OVERRIDE_VARIABLE} to go on"
            )
        if len(body) > BODY_BYTES_CEILING:
            raise SendGuard(f"a request body of {len(body)} bytes is over {BODY_BYTES_CEILING}")
        limit = json.loads(body).get("inferenceConfig", {}).get("maxTokens")
        if not isinstance(limit, int) or limit > OUTPUT_TOKENS_CEILING:
            raise SendGuard(f"every request carries an output limit up to {OUTPUT_TOKENS_CEILING}")

    def _before_parse(self, response_dict: dict[str, Any], **_: Any) -> None:
        send = self._current_sends[-1]
        status = int(response_dict.get("status_code", 0))
        headers = {str(k).lower(): str(v) for k, v in dict(response_dict["headers"]).items()}
        body = response_dict.get("body")
        if not isinstance(body, bytes):
            # A stream's body is the open HTTP response; its outcome is written when the
            # caller has consumed the parsed events.
            self._streamed.add(send)
            return
        (self.directory / f"{send}.response.json").write_bytes(body)
        try:
            usage = json.loads(body).get("usage")
        except ValueError:
            usage = None
        self._outcome(send, "response" if status < 300 else "service_error", status, headers, usage)

    def _after_call(self, parsed: dict[str, Any], **_: Any) -> None:
        stream = parsed.get("stream")
        if stream is None:
            return
        send = self._current_sends[-1]
        metadata = parsed.get("ResponseMetadata", {})
        status = int(metadata.get("HTTPStatusCode", 0))
        headers = {str(k).lower(): str(v) for k, v in metadata.get("HTTPHeaders", {}).items()}
        parsed["stream"] = RecordedStream(
            stream,
            lambda events, error, stopped: self._stream_ended(
                send, status, headers, events, error, stopped
            ),
        )

    def _stream_ended(
        self,
        send: str,
        status: int,
        headers: dict[str, str],
        events: list[dict[str, Any]],
        error: BaseException | None,
        stopped: bool,
    ) -> None:
        document = {
            "events": events,
            "complete": any("messageStop" in event for event in events),
            "exception": None if error is None else f"{type(error).__name__}: {error}",
            "consumer_stopped": stopped,
        }
        text = json.dumps(document, ensure_ascii=False, default=repr)
        (self.directory / f"{send}.stream.json").write_text(text, encoding="utf-8")
        usage = next((e["metadata"].get("usage") for e in events if "metadata" in e), None)
        kind = "response" if document["complete"] and error is None else "partial_stream"
        self._outcome(send, kind, status, headers, usage)

    def _outcome(
        self, send: str, kind: str, status: int, headers: dict[str, str], usage: object
    ) -> None:
        self._append(
            {
                "event": "outcome",
                "send": send,
                "outcome": kind,
                "at": datetime.now(UTC).isoformat(),
                "http_status": status,
                "request_id": headers.get("x-amzn-requestid"),
                "response_headers": headers,
                "usage": usage,
                "counters": counter_states(usage) if isinstance(usage, dict) else None,
            }
        )

    def _append(self, line: dict[str, Any]) -> None:
        with self.record.open("a", encoding="utf-8") as record:
            record.write(json.dumps(line, ensure_ascii=False) + "\n")
            record.flush()
            os.fsync(record.fileno())

    # --- Reading back -----------------------------------------------------------------------

    def request_of(self, send: str) -> dict[str, Any]:
        """The request body of ``send``, JSON-decoded from the bytes that left."""
        return json.loads((self.directory / f"{send}.request.json").read_bytes())

    def response_of(self, send: str) -> dict[str, Any] | None:
        """The non-streamed response body of ``send`` as received, or ``None`` if there is none."""
        file = self.directory / f"{send}.response.json"
        return json.loads(file.read_bytes()) if file.exists() else None

    def stream_of(self, send: str) -> dict[str, Any] | None:
        """The recorded stream of ``send`` (its events and how it ended), or ``None``."""
        file = self.directory / f"{send}.stream.json"
        return json.loads(file.read_text(encoding="utf-8")) if file.exists() else None

    def lines_of(self, send: str) -> list[dict[str, Any]]:
        """The record's lines about ``send``: its ``send`` line, then its outcome if known."""
        with self.record.open(encoding="utf-8") as record:
            return [line for line in map(json.loads, record) if line.get("send") == send]

    def outcome_of(self, send: str) -> dict[str, Any] | None:
        """The outcome line of ``send``, or ``None`` while it is unresolved."""
        return next((line for line in self.lines_of(send) if line["event"] == "outcome"), None)


class RecordedStream:
    """An event stream that copies each parsed event as its consumer reads it.

    The copy is taken before the event is handed over, so nothing the consumer does to an
    event changes the record. ``ended`` is called once, when the stream is exhausted, raises,
    or is left: with the events seen, the exception that ended the stream if one did, and
    whether it was the consumer that stopped reading before the stream ran out. A consumer
    that stops is not a fault of the stream and is never recorded as its exception.
    """

    def __init__(
        self,
        stream: Any,
        ended: Callable[[list[dict[str, Any]], BaseException | None, bool], None],
    ) -> None:
        self._stream = stream
        self._ended = ended
        self._events: list[dict[str, Any]] = []
        self._reported = False

    def __iter__(self) -> Iterator[dict[str, Any]]:
        try:
            for event in self._stream:
                self._events.append(copy.deepcopy(event))
                yield event
        except GeneratorExit:
            self._report(None, stopped=True)
            raise
        except BaseException as error:
            self._report(error, stopped=False)
            raise
        self._report(None, stopped=False)

    def close(self) -> None:
        self._report(None, stopped=True)
        if hasattr(self._stream, "close"):
            self._stream.close()

    def _report(self, error: BaseException | None, *, stopped: bool) -> None:
        if not self._reported:
            self._reported = True
            self._ended(self._events, error, stopped)


# --- The clients ----------------------------------------------------------------------------


def clients(
    recorder: Recorder, *, total_max_attempts: int = 1, read_timeout: float = 60.0
) -> tuple[Any, Any]:
    """The runtime client with the recorder attached, and the control-plane client.

    Both are built here so that no client exists the probe did not build: the chat model
    creates a control-plane client of its own when it is not handed one. Retries are explicit:
    the standard mode, ``total_max_attempts`` counting the initial request, so 1 is no retry.
    Credentials are ambient (``AWS_PROFILE``), never a parameter.
    """
    session = boto3.Session(region_name=recorder.region)
    configuration = Config(
        retries={"mode": "standard", "total_max_attempts": total_max_attempts},
        read_timeout=read_timeout,
        connect_timeout=10,
    )
    runtime = session.client("bedrock-runtime", config=configuration)
    recorder.attach(runtime)
    control = session.client("bedrock", config=configuration)
    return runtime, control
