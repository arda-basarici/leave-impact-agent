"""What the integration tests compose a worker over the real store with: the ledger with its
threshold set and the reference run admitted, the synchronous saver on a connection of its
own in the rig's schema (the acceptance spike's accepted configuration), the worker's
composition over the scripted fillings, and the reference run worked to its closing
through the work command. The two-call script is the default throughout; the smoke
admits and composes under another (``worker_support.SCRIPTS``)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row

from leaveimpact.agent.commands import WorkerComposition, WorkRequest, work
from leaveimpact.agent.log_events import FrozenInputs
from leaveimpact.agent.log_store import AdmissionReceipt, AdmissionRequest, LogStore
from leaveimpact.agent.worker import (
    AutomaticApproval,
    WorkerConfiguration,
    WorkerEnding,
    WorkerEndingKind,
)
from leaveimpact.core.worldtime import RunContext
from leaveimpact.evaluator.sealed_world import SealedWorld
from tests.integration.log_store_support import Rig
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.reads_fixture import systems_holding

RULES = histories.RULES
LEDGER = "ledger-worker"
PLENTY = 10**15
RUN, ATTEMPT = "run-12", 1


def saver_on(rig: Rig) -> PostgresSaver:
    """The synchronous saver on a connection of its own, its tables in the rig's schema."""
    connection = psycopg.Connection[DictRow].connect(
        make_conninfo(
            rig.url, options=f"-c search_path={rig.schema}", application_name="worker-test-saver"
        ),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    rig.connections[-len(rig.connections) - 1] = connection
    saver = PostgresSaver(connection)
    saver.setup()
    return saver


def admitted(
    rig: Rig,
    world: SealedWorld,
    *,
    scenario: int = 0,
    inputs_for: Callable[[RunContext], FrozenInputs] = support.admitted_inputs,
) -> tuple[LogStore, FrozenInputs]:
    """A store over the rig with the ledger's threshold set and a run admitted for the
    world's ``scenario``-th scenario under ``inputs_for``'s frozen inputs, the fixtures'
    unless the run is the real turns'; the frozen inputs beside it."""
    store = rig.store()
    store.set_threshold(
        LEDGER,
        PLENTY,
        authority="operator:test",
        registration_commit=cases.COMMIT,
        limit_pico_usd=PLENTY,
    )
    inputs = inputs_for(world.context_of(world.scenarios[scenario]))
    receipt = store.admit(
        AdmissionRequest(f"req-{uuid4().hex[:12]}", inputs, support.ADMITTER, LEDGER, RULES)
    )
    assert isinstance(receipt, AdmissionReceipt)
    return store, inputs


def composition(
    inputs: FrozenInputs,
    world: SealedWorld,
    saver: Any,
    *,
    approval: Any = None,
    script: support.RunScript[Any] = support.SCRIPTS["two-call"],
) -> WorkerComposition:
    """The worker's composition over ``script`` (the two-call one by default) and the golden
    world's ports as the script runs over them; the automatic approval unless one is given."""
    turns, client = script.over(world, inputs.context)
    return WorkerComposition(
        WorkerConfiguration.of(inputs),
        cases.REVISION,
        RULES,
        turns,
        client,
        support.ScriptedCounter(),
        script.ports(systems_holding(world).ports),
        approval if approval is not None else AutomaticApproval(),
        saver,
    )


def completed(rig: Rig, world: SealedWorld) -> tuple[LogStore, FrozenInputs]:
    """The reference run worked to its closing through the work command."""
    store, inputs = admitted(rig, world)
    ending = work(
        WorkRequest(RUN, ATTEMPT, "nonce-1", "launch-1"),
        store,
        composition(inputs, world, saver_on(rig)),
    )
    assert ending == WorkerEnding(WorkerEndingKind.CLOSED, RUN, ATTEMPT, 1, "completed")
    return store, inputs
