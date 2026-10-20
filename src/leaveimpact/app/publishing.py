"""The operator's publication of a replay: what the command verifies against the log before
the store writes a row, pure over the loaded attempt.

A replay is a closed run of the served world, published once under a name the operator
chose (the demo milestone's publishability ruling, amended by the step's external read).
``draft_of`` loads the attempt the request names and refuses, by name, an attempt the log
does not hold, an attempt still open (a replay is a closed run; an unfinished live attempt's
row is the public start command's, in its admission transaction, at the live path's step),
and an attempt of a world other than the served one, which is where the embargoed
measurement world's runs are refused before any row exists. What passes becomes the draft
the store writes: the world version and scenario copied from the admission, never typed by
the operator, so the row's projection is the admission's by construction, and the read
model's comparison on every content read then holds unless the log itself changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.agent.log_transition import Rules
from leaveimpact.app.config import DemoConfiguration
from leaveimpact.app.public import PublicationDraft, PublicId
from leaveimpact.app.read_model import LogReads


@dataclass(frozen=True, slots=True)
class PublishRequest:
    """What the operator states: the attempt, its public name, a title for an introduced
    example, and who publishes."""

    run_id: str
    attempt: int
    public_id: PublicId
    title: str | None
    published_by: str


@dataclass(frozen=True, slots=True)
class PublishRefused:
    """Why the request writes nothing; the reason names the attempt and the rule."""

    reason: str


def draft_of(
    request: PublishRequest, configuration: DemoConfiguration, log: LogReads, rules: Rules
) -> PublicationDraft | PublishRefused:
    """The row to write for ``request``, or the refusal: no such attempt, an open attempt,
    or an attempt of a world the configuration does not serve."""
    where = f"run {request.run_id} attempt {request.attempt}"
    try:
        state = log.load(request.run_id, request.attempt, rules=rules)
    except ValueError as error:
        return PublishRefused(f"{where} cannot be loaded from the log: {error}")
    inputs = state.inputs
    if inputs is None:
        return PublishRefused(f"{where} has no admission in the log")
    if state.closed is None:
        return PublishRefused(f"{where} is open; a replay is a closed run")
    context = inputs.context
    if context.world_version != configuration.served_world_version:
        return PublishRefused(
            f"{where} is a run of world {context.world_version}, not the served world "
            f"{configuration.served_world_version}; only the served world is publishable"
        )
    return PublicationDraft(
        request.public_id,
        request.run_id,
        request.attempt,
        context.world_version,
        context.scenario_id,
        request.title,
        request.published_by,
    )
