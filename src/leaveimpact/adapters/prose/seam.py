"""The request-shaped seam between the materializer and the models: what a call carries, what it
returns, the two protocols, and the faults a call can end in.

The seam is request-shaped on purpose (the step 14 rulings in DESIGN, "Materialization"): the
generator renders a brief into a system text and a message, names the tool it wants forced
and the inference settings it wants recorded, and the adapter sends exactly that. Nothing
here knows what a runbook, a guard or a required fact is, so a change of prompt policy never
touches the adapter and a change of provider never touches the generator. The checker's
answer is the forced tool's input as the model returned it, an untyped JSON object; parsing
it into propositions is the generator's, since the generator wrote the schema the model
filled.

Every call returns its usage — tokens in and out, the model's latency — because those are
the run metrics the step reports and never seals; the record of a text's acceptance keeps
digests and settings, not costs. The faults are closed and classified by what the caller
can do about them: ``ModelUnreachable`` is the transient class, what the materializer's own
bounded retry addresses after the SDK's have run; ``ModelAccessRefused`` is the principal's
grant, fixed in the platform stack and never by retrying; ``ModelMisconfigured`` is a request
the service rejected or a client that cannot be built; ``ModelProtocolFault`` is an answer
that arrived and is not the contract — no tool call where one was forced, a truncated text,
an empty one — which is the checker's failure and never the writer's refusal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.world.prose import Setting


@dataclass(frozen=True, slots=True)
class InferenceConfiguration:
    """The explicit inference settings of one call, and their record form.

    ``top_p`` is optional because a call that does not set it should not record a
    default it never sent; a setting recorded is a setting the model was called with.
    """

    temperature: float
    max_tokens: int
    top_p: float | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.temperature <= 1:
            raise ValueError(f"temperature lies in [0, 1], got {self.temperature}")
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens is at least one, got {self.max_tokens}")
        if self.top_p is not None and not 0 < self.top_p <= 1:
            raise ValueError(f"top_p lies in (0, 1], got {self.top_p}")

    def settings(self) -> tuple[Setting, ...]:
        """Every setting sent, as the materialization record stores them."""
        sent = [Setting("temperature", self.temperature), Setting("max_tokens", self.max_tokens)]
        if self.top_p is not None:
            sent.append(Setting("top_p", self.top_p))
        return tuple(sent)


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A tool the model is forced to call: its name, its purpose, the JSON schema of its input."""

    name: str
    description: str
    input_schema: JsonObject

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("a tool has a name")


@dataclass(frozen=True, slots=True)
class WriterRequest:
    """One call to the writer: the system text, the user message, the settings."""

    system: str
    message: str
    inference: InferenceConfiguration

    def __post_init__(self) -> None:
        _non_blank(self.system, "system text")
        _non_blank(self.message, "message")


@dataclass(frozen=True, slots=True)
class CheckerRequest:
    """One call to the checker: system text, message, the tool it must call, the settings."""

    system: str
    message: str
    tool: ToolSpec
    inference: InferenceConfiguration

    def __post_init__(self) -> None:
        _non_blank(self.system, "system text")
        _non_blank(self.message, "message")


def _non_blank(text: str, what: str) -> None:
    if not text.strip():
        raise ValueError(f"a request's {what} is not blank")


@dataclass(frozen=True, slots=True)
class Usage:
    """What one call cost: tokens in and out, and the model's own latency in milliseconds."""

    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass(frozen=True, slots=True)
class WrittenText:
    """The writer's answer: the text it produced, whole, and the call's usage."""

    text: str
    usage: Usage


@dataclass(frozen=True, slots=True)
class ToolCall:
    """The checker's answer: the forced tool's input as returned, and the call's usage."""

    input: JsonObject
    usage: Usage


class ProseWriter(Protocol):
    """Turns a rendered request into text; the fake at unit level, Bedrock under ``live``.

    ``model_id`` names what the record says wrote the text; a fake names itself.
    """

    @property
    def model_id(self) -> str: ...

    def write(self, request: WriterRequest) -> WrittenText: ...


class ProseChecker(Protocol):
    """Makes the model fill the forced tool over a rendered request; returns the input as is."""

    @property
    def model_id(self) -> str: ...

    def extract(self, request: CheckerRequest) -> ToolCall: ...


# --- Faults ---------------------------------------------------------------------------------


class ModelUnreachable(Exception):
    """The model did not answer, or the service throttled or failed; the cause is chained."""

    def __init__(self, model_id: str) -> None:
        super().__init__(f"model unreachable: {model_id}")
        self.model_id = model_id


class ModelAccessRefused(Exception):
    """The principal may not invoke the model: a grant, never a retry."""

    def __init__(self, model_id: str, reason: str) -> None:
        super().__init__(f"invoke refused on {model_id}: {reason}")
        self.model_id = model_id


class ModelMisconfigured(Exception):
    """The service rejected the request, or the client could not make it; the reason names why."""

    def __init__(self, model_id: str, reason: str) -> None:
        super().__init__(f"model call misconfigured for {model_id}: {reason}")
        self.model_id = model_id


class ModelProtocolFault(Exception):
    """The model answered and the answer is not the contract: its failure, never a refusal."""

    def __init__(self, model_id: str, reason: str) -> None:
        super().__init__(f"{model_id} broke the call's contract: {reason}")
        self.model_id = model_id


__all__ = [
    "CheckerRequest",
    "InferenceConfiguration",
    "ModelAccessRefused",
    "ModelMisconfigured",
    "ModelProtocolFault",
    "ModelUnreachable",
    "ProseChecker",
    "ProseWriter",
    "ToolCall",
    "ToolSpec",
    "Usage",
    "WriterRequest",
    "WrittenText",
]
