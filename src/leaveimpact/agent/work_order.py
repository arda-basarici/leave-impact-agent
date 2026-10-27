"""The work order: the composition of one worker execution over an admitted attempt, as
every composition root performs it, the agent's command line for an operator's run and the
demo's worker service for a visitor's.

An order states what the lifecycle's work line states and nothing a file holds: the attempt
with its nonce and launch identity, the registered cell (its system kind, condition and
level), the registration's commit, the filling of the one role the system runs (``None``
for rules only, which runs none), the region the clients call from, the harness revision
this code claims, and who approves. ``perform`` composes the investigator graph's real
fillings over it (the graph step, fork 17): the configuration the registration and this
code give the named cell (``registered.model_system_provenance``), the price basis from
the table, the vendor hosts from the environment, the world manifest from the world store
at the admitted version, the corpus reader from the admitted version and level before any
read (the registry step's forward), the live clients from the region, the turns over the
shipped prompts, the checkpoint saver on the run log's database, and the approval policy
the order names. A rules-only cell runs the same order through the same worker with no
role (the first live run's step, fork 4): its configuration is
``registered.rules_only_configuration``, its turns ask nothing, and the clients it is
handed refuse a send or a count as this harness's defect.

The attempt's state is read first, before anything beyond the run log is built: an
attempt whose log already holds its ending, a recorded stopping failure with its segment
still open or a closing, takes the terminal-only path (the first live run's step, fork 9,
extended to the closed attempt at the group's review) and is closed by that failure, or
found closed, through ``commands.finalize`` with no world store, corpus reader, vendor
reader or client composed, so a closing the log has already decided cannot fail for a
reason unrelated to the attempt. Otherwise the corpus reader runs its serving check before
any read port is built (``corpus_reader_for``), and the worker compares the composed
configuration with the admission's and claims nothing on a difference.

The registered outage is injected over the composed ports from the assignment the
admission recorded, never from the order's condition again (the outage step, forks 1 and
2): a recovering process injects what the first was admitted under. Every reader is built
as under the normal condition, the serving check included, and the scheduled-out ones are
wrapped in front of their adapters, so the wiring, the credentials it requires and the
closing are one path whatever the condition (fork 4). What is opened is closed before
``perform`` returns, in the reverse of its opening: the corpus reader, the vendor readers,
the SDK runtime client the two live clients share and the saver's connection; the
world-store reader holds nothing to close.

This module lived as the command line's private ``_work`` until the worker service's step
lifted it, so the operator's path and the visitor's compose one way and cannot drift. The
refusals it raises are the ones the command line prints: ``ValueError`` from the store, a
codec or the registration, naming ids, fields and digests; the corpus refusal; the object
reader's own faults; ``ConfigurationError`` for an environment that lacks the database.
The manifest codec's refusal quotes the fields it found and the job's log is public, so
that one is raised naming the key and the exception's type alone, after the handler has
ended (the first live run's review, second finding).
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import ExitStack, closing
from dataclasses import dataclass

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import DictRow, dict_row

from leaveimpact.adapters.inference import ConverseClient, CountingClient, inference_client
from leaveimpact.adapters.manifest import ManifestStage, WorldManifest, decode_manifest
from leaveimpact.adapters.object_store.layout import world_manifest_key
from leaveimpact.adapters.wiring import (
    ConfigurationError,
    build_readers,
    hosts_from_env,
    world_store_from_env,
    world_store_reader,
)
from leaveimpact.agent.commands import (
    TerminalComposition,
    WorkerComposition,
    WorkRequest,
    finalize,
    system_content,
    work,
)
from leaveimpact.agent.corpus import corpus_reader_for
from leaveimpact.agent.execution import ReadPorts, ports_under
from leaveimpact.agent.graph import ModelClient, TokenCounter
from leaveimpact.agent.log_store import LogStore
from leaveimpact.agent.log_transition import Rules
from leaveimpact.agent.registered import (
    RoleFilling,
    model_system_provenance,
    rules_only_configuration,
)
from leaveimpact.agent.rules_only import NoCounter, NoModelClient
from leaveimpact.agent.worker import ApprovalPolicy, WorkerEnding
from leaveimpact.core.pricing import PriceTable, basis_for
from leaveimpact.core.registration import Registration
from leaveimpact.core.run_record import SystemKind
from leaveimpact.core.run_timing import HarnessRevision

DATABASE = "DATABASE_URL"
"""The environment name of the run log's database, which the saver and the corpus reader
share with the log store."""


@dataclass(frozen=True, slots=True)
class WorkOrder:
    """One worker execution as a composition root states it: the attempt with its nonce and
    launch identity, the registered cell, the registration's commit, the role's filling or
    none, the region the clients call from, the harness revision this code claims, and who
    approves at the pause."""

    attempt: WorkRequest
    system: SystemKind
    condition: str
    level: str
    registration_commit: str
    role: RoleFilling | None
    region: str
    harness: HarnessRevision
    approval: ApprovalPolicy


def perform(
    order: WorkOrder,
    registration: Registration,
    prices: PriceTable,
    *,
    store: LogStore,
    rules: Rules,
    env: Mapping[str, str],
) -> WorkerEnding:
    """Bring the order's attempt as far as one process can, composed as the module says:
    the configuration from ``registration`` for the cell, the state read first with the
    terminal path for a stop or a closure, then the ports, the clients and the saver over
    ``env``, and the worker's ending."""
    turns, preparation = system_content(order.system)
    if order.role is None:
        configuration = rules_only_configuration(
            registration,
            order.condition,
            order.level,
            preregistration_commit=order.registration_commit,
            pricing=basis_for(prices, ()),
        )
    else:
        configuration = model_system_provenance(
            registration,
            order.system,
            order.condition,
            order.level,
            preregistration_commit=order.registration_commit,
            pricing=basis_for(prices, (order.role.pricing,)),
            role=order.role,
        )
    state = store.load(order.attempt.run_id, order.attempt.attempt, rules=rules)
    inputs = state.inputs
    if inputs is None:
        raise ValueError(
            f"run {order.attempt.run_id} attempt {order.attempt.attempt} holds no admission"
        )
    if state.closed is not None or state.stopped is not None:
        return finalize(
            order.attempt, store, TerminalComposition(configuration, order.harness, rules)
        )
    # Read as the entry reads it, not indexed: the entry validated the name before it built
    # the store, but a caller handing in a store under another environment reaches this line
    # first, and a missing name is a configuration fault, never an unexpected error (found
    # 2026-10-09).
    dsn = env.get(DATABASE, "").strip()
    if not dsn:
        raise ConfigurationError(f"{DATABASE} names the run log's database")
    world_reader = world_store_reader(world_store_from_env(env))
    version = inputs.context.world_version
    key = world_manifest_key(version)
    stored = world_reader.get(key)
    if stored is None:
        raise ValueError(f"the world store holds no manifest at {key}")
    manifest = _manifest_of(stored.content, key)
    if manifest.world_version != version:
        raise ValueError(
            f"the manifest at the keys of {version} describes world {manifest.world_version}"
        )
    with ExitStack() as opened:
        corpus = opened.enter_context(closing(corpus_reader_for(inputs, dsn=dsn)))
        hosts = hosts_from_env(env, jira_at_gateway=True)
        readers = opened.enter_context(closing(build_readers(hosts, manifest, world_reader)))
        # A rules-only run is handed no runtime: no client is built, and the two it gets
        # refuse a send or a count as this harness's defect.
        client: ModelClient = NoModelClient(order.region)
        counter: TokenCounter = NoCounter()
        if order.role is not None:
            runtime = opened.enter_context(closing(inference_client(order.region)))
            client, counter = ConverseClient(runtime), CountingClient(runtime)
        connection = opened.enter_context(closing(_saver_connection(dsn)))
        saver = PostgresSaver(connection)
        saver.setup()
        composition = WorkerComposition(
            configuration,
            order.harness,
            rules,
            turns,
            preparation,
            client,
            counter,
            ports_under(
                ReadPorts(readers.people, readers.work, readers.calendar, corpus),
                inputs.outage.scheduled_unreachable,
            ),
            order.approval,
            saver,
        )
        return work(order.attempt, store, composition)


def _manifest_of(content: bytes, key: str) -> WorldManifest:
    """The projected manifest ``content`` holds, the codec's refusal reduced to the key and
    the exception's type after the handler has ended, so no traceback carries the fields
    the codec quotes."""
    manifest: WorldManifest | None = None
    failure: str | None = None
    try:
        manifest = decode_manifest(content, stage=ManifestStage.PROJECTED)
    except ValueError as error:
        failure = type(error).__name__
    if manifest is None:
        raise ValueError(f"the world manifest at {key} does not decode ({failure})")
    return manifest


def _saver_connection(dsn: str) -> psycopg.Connection[DictRow]:
    """The checkpoint saver's own connection, in the configuration the acceptance spike
    settled: autocommit, no prepared statements, dictionary rows."""
    return psycopg.Connection[DictRow].connect(
        dsn, autocommit=True, prepare_threshold=0, row_factory=dict_row
    )


__all__ = ["DATABASE", "WorkOrder", "perform"]
