"""The two one-call baselines' turns: one request, flagged final, over the prefetch and the
reads the harness issued for the run; then nothing more. The single-shot and the
full-context systems share this module and the ``reader`` role, and differ only in the
preparation that issues their reads (the baselines step, forks 2, 3 and 9).

*The one request.* The first and only user message is the investigator's form, the opening,
the skill list and one text block per prefetch operation (``request_parts``), then one block
per harness operation in position order in the same form, the one search's result or the
level's documents, then the finalization text, so the message ends with the ask and two
user turns never follow each other. The request is flagged final: the graph appends the
finalization entry before the dispatch, the account authorizes the call as the finalization
against the whole caps with the reserve allowed, and the tool configuration is the
finalization's exactly, the fact tool alone and forced by name, so the output channel is the
investigator's own last turn (fork 2 as amended: no read tools, the shared fact-output tool
only; the comparison isolates what each system was shown). ``input_reads`` names the
prefetch operations and the harness operations, so the level check's third surface reads
off the dispatch as ruled. A harness read the corpus did not answer is shown as the surface
renders it, the error envelope naming the unreachable source, and the call is made all the
same (fork 7).

*After it.* Call 2 is never asked: once call 1 holds an outcome the turns answer ``None``
and the run goes to its approval, a call ended as behaviour included, since nothing arrived
and the model's own doing is graded as such. An abstention the prefetch decides asks no call
at all, as for the investigator: no count, no send, the approval with the empty payload. The
request of call 1 in progress is the same bytes, a function of the log below its first
intent and of nothing else, so a recovering worker restates it and the model node holds it
to that. When the finalization allocation does not fit the caps the account answers at-cap
and the run ends cap-exhausted through the approval of what it has: a rules-only answer under
that ending, as for an investigator whose first call never fit.

*The review payload* is the composed payload the investigator's run ends with.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.agent.assets import FINALIZATION, SYSTEM, PromptAssets
from leaveimpact.agent.graph import ReviewPayload, TurnRequest
from leaveimpact.agent.log_events import (
    HarnessReadKey,
    OperationEvent,
    OperationResult,
    operation_id,
)
from leaveimpact.agent.log_transition import (
    AttemptState,
    calls_of,
    derived_abstention,
    operations_of,
)
from leaveimpact.agent.request_parts import (
    append_text,
    composed_payload,
    configured,
    fact_forced_tool_config,
    frozen_inputs,
    inference_config,
    opening_message,
    operation_text,
)
from leaveimpact.core.jsonshape import JsonObject
from leaveimpact.core.run_trace import OperationId
from leaveimpact.core.tools import Role


@dataclass(frozen=True, slots=True)
class OneCallTurns:
    """The one-call systems' ``Turns``: see the module."""

    assets: PromptAssets
    role: Role = Role.READER

    def request_for(self, state: AttemptState, call: int) -> TurnRequest | None:
        """The one request for call 1, in progress or next; ``None`` on an abstention the
        prefetch decided and for every call after the first once it holds an outcome.
        ``ValueError`` when ``call`` is neither in progress nor the next, when call 1 holds
        no outcome and a later call is asked, or when the role's configuration holds a
        setting the request cannot carry."""
        inputs = frozen_inputs(state)
        calls = calls_of(state)
        if call == len(calls) + 1:
            boundary = state.last_position + 1
        elif 1 <= call <= len(calls):
            boundary = calls[call - 1].intents[0].position
        else:
            raise ValueError(f"call {call} is neither in progress nor the next; {len(calls)} held")
        if call > 1:
            if calls[0].last_outcome is None:
                raise ValueError("call 1 holds no outcome; no request follows it")
            return None
        if derived_abstention(state, below=boundary) is not None:
            return None
        shown: list[OperationId] = []
        message = opening_message(self.assets, state, boundary, shown)
        for logged in operations_of(state):
            if logged.position >= boundary:
                break
            event = logged.event
            assert isinstance(event, OperationEvent)
            if not isinstance(event.key, HarnessReadKey):
                continue
            result = event.resolution
            assert isinstance(result, OperationResult), "a preparation skips no read"
            append_text(message, operation_text(result, inputs.context))
            shown.append(operation_id(event.key))
        append_text(message, self.assets.text(FINALIZATION))
        body: JsonObject = {
            "system": [{"text": self.assets.text(SYSTEM)}],
            "messages": [message],
            "toolConfig": fact_forced_tool_config(),
            "inferenceConfig": inference_config(configured(inputs, self.role.value)),
        }
        return TurnRequest(self.role.value, body, tuple(shown), True)

    def payload_for(self, state: AttemptState) -> ReviewPayload:
        """The composed payload over everything the log holds (``request_parts``)."""
        return composed_payload(state)


__all__ = ["OneCallTurns"]
