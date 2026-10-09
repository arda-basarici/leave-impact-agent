"""The smoke at the integration level (the step's fork 16): the real turns through the work
command over the real store and the synchronous saver, the export through the publish
command to the in-memory object store, and the real evaluator over that export, asserting
no finding of a kind the plumbing could cause.

The model is the stating script's content-scripted client, which is no measurement: the
test asserts that what the harness recorded and what the evaluator reads back of it agree
(the prefetch as planned, the admissions and the composition the recheck reproduces, the
ending, the counts, the account and the calls as the log states them, every citation
resolving, no self-contradiction among the reads) and nothing about quality.
"""

from __future__ import annotations

import pytest

from leaveimpact.adapters.wiring import run_export_publisher_over
from leaveimpact.agent.commands import PublishRequest, WorkRequest, publish, work
from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.agent.worker import WorkerEnding, WorkerEndingKind
from leaveimpact.core.run_export_json import decode_export_bytes
from leaveimpact.evaluator.grading import Graded
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.evaluator.trace_metrics import evaluate_run
from tests.integration.log_store_support import Rig, rig
from tests.integration.worker_rig import ATTEMPT, RULES, RUN, admitted, composition, saver_on
from tests.unit import format_fixtures as cases
from tests.unit import worker_support as support
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.throwaway_world import loaded_world

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def test_the_real_turns_run_publish_and_evaluate_with_no_finding_the_plumbing_could_cause(
    rig: Rig, world: SealedWorld
) -> None:
    script = support.SCRIPTS["stating"]
    store, inputs = admitted(rig, world, inputs_for=script.inputs)
    ending = work(
        WorkRequest(RUN, ATTEMPT, "nonce-1", "launch-1"),
        store,
        composition(inputs, world, saver_on(rig), script=script),
    )
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")

    memory = InMemoryObjectStore()
    record = publish(
        PublishRequest(RUN, ATTEMPT, cases.COMMIT),
        store,
        run_export_publisher_over(memory),
        rules=RULES,
    )
    assert isinstance(record, PublicationRecord) and record.object_identity is not None
    held = memory.get(record.object_identity)
    assert held is not None
    export = decode_export_bytes(held.content)
    assert len(export.trace.model_calls) == 3 and export.trace.claims
    assert export.trace.finalization_entered is not None

    evaluation = evaluate_run(
        world,
        export,
        table=RULES.table,
        redispatch=RULES.redispatch,
        retry=inputs.retry,
        counting_identifiers=dict(inputs.counting_identifiers),
    )
    metrics = evaluation.metrics
    assert metrics.prefetch.evaluated and metrics.prefetch.findings == ()
    assert metrics.recheck.admissions == 1 and metrics.recheck.composition_evaluated
    assert metrics.recheck.findings == ()
    assert metrics.ending.findings == ()
    assert metrics.cost.findings == ()
    assert metrics.counts.findings == ()
    assert metrics.account is not None and metrics.account.findings == ()
    assert metrics.calls is not None and metrics.calls.findings == ()
    assert metrics.attribution is not None and metrics.attribution.findings == ()
    assert evaluation.contradictions == ()
    outcome = evaluation.outcome
    assert isinstance(outcome, Graded) and outcome.grounding is not None
    assert outcome.grounding.citations
    assert all(citation.resolves for citation in outcome.grounding.citations)
