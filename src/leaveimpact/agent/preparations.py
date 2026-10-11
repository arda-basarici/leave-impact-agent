"""The two one-call baselines' preparations: the one read each issues between the prefetch
and its call, under the policy the record names for its kind (the baselines step, forks 7
and 8 as amended).

The single-shot system renders the registered query protocol over the records the prefetch
returned for the leave under investigation (``core.query_protocol``, one pure function, so a
recovering worker renders the same text a first process did and the logged executor holds
it to that) and issues one ``search`` with the registered limit under
``single_shot_query``. The full-context system issues one ``documents`` read, every corpus
document the run's level holds, under ``full_context_documents``. Neither reads anything
else, and the log refuses a second read under either policy for a system that issues one.

Both are asked only after the shared preconditions, so the leave is the opening read's
record and the protocol and the limit are frozen (a single-shot admission freezes them, the
frozen inputs' own rule). What a read meets is the fault policy applied to a harness read
(fork 7): an unreachable corpus is a recorded operation with the source stopped and the call
is still made with the failure shown; a malformed record is the stop the transition records
at that operation; a search the registered protocol rendered over the declarations the
executor validates against cannot be refused, since the rendering clips to the argument's
maximum, and a refusal would raise as this harness's defect.
"""

from __future__ import annotations

from dataclasses import dataclass

from leaveimpact.agent.admissions import trace_operations
from leaveimpact.agent.conclusion import leave_of
from leaveimpact.agent.graph import LoggedExecutor
from leaveimpact.agent.log_events import HarnessReadKey
from leaveimpact.agent.log_transition import AttemptState
from leaveimpact.agent.request_parts import frozen_inputs
from leaveimpact.core.query_protocol import render_query
from leaveimpact.core.run_record import FULL_CONTEXT_DOCUMENTS_POLICY, SINGLE_SHOT_QUERY_POLICY
from leaveimpact.core.run_trace import HarnessOrigin, records_of


@dataclass(frozen=True, slots=True)
class SingleShotPreparation:
    """One search of the registered query over the prefetch's records, at the registered
    limit, under ``single_shot_query``."""

    def prepare(self, executor: LoggedExecutor, state: AttemptState) -> None:
        inputs = frozen_inputs(state)
        protocol, limit = inputs.query_protocol, inputs.search_limit
        assert protocol is not None and limit is not None, "a single-shot admission freezes both"
        operations = trace_operations(state)
        leave = leave_of(operations, inputs.context)
        assert leave is not None, "the preparation follows the preconditions"
        returned = tuple(
            record for operation in operations for record in records_of(operation.outcome)
        )
        query = render_query(protocol, returned, leave)
        executor.resolve(
            HarnessReadKey(SINGLE_SHOT_QUERY_POLICY, 1),
            HarnessOrigin(SINGLE_SHOT_QUERY_POLICY),
            "search",
            {"query": query, "limit": limit},
        )


@dataclass(frozen=True, slots=True)
class FullContextPreparation:
    """One enumeration of the level's documents under ``full_context_documents``."""

    def prepare(self, executor: LoggedExecutor, state: AttemptState) -> None:
        executor.resolve(
            HarnessReadKey(FULL_CONTEXT_DOCUMENTS_POLICY, 1),
            HarnessOrigin(FULL_CONTEXT_DOCUMENTS_POLICY),
            "documents",
            {},
        )


__all__ = ["FullContextPreparation", "SingleShotPreparation"]
