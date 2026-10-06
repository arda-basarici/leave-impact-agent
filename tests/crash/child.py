"""One process of the crash matrix: the real worker over the real store and saver, with the
injector at the store's boundaries, the saver's writes, the approval handoff and the wire.

The parent starts this script once per segment, in a schema it names, with the world it
prepared once (the run's context and the in-memory systems, pickled to a file). The record
and the kill target arrive in the environment (``injector``). On a normal exit it prints
one JSON line with the worker's ending; a child killed at its target prints nothing and
exits with the injector's code.

What is seamed, and how it is named: the store's ``boundary`` fires as ``<kind>:<point>``,
the kind being the event the command writes (``load:read`` for the worker's load); the
saver's two write methods as ``checkpoint:before``, ``checkpoint:after``, ``writes:before``
and ``writes:after``; the approval handoff's two points as the worker names them. Witnessed:
every send with the request's digest, every response returned, every port read with the
tool it served, and every receipt the store gave for a held event.
"""

from __future__ import annotations

import json
import os
import pickle
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row

from leaveimpact.agent.appender import LogCommands
from leaveimpact.agent.execution import ReadPorts
from leaveimpact.agent.graph import Sent
from leaveimpact.agent.log_events import (
    ClosingEvent,
    CommitOverride,
    Envelope,
    Event,
    Stamping,
    kind_of,
)
from leaveimpact.agent.log_store import LogStore
from leaveimpact.agent.log_transition import AttemptState, Received, Rules, Transition
from leaveimpact.agent.worker import AutomaticApproval, Worker, WorkerConfiguration
from leaveimpact.core.run_timing import HarnessRevision
from tests.crash import injector
from tests.unit import format_fixtures as cases
from tests.unit import log_histories as histories
from tests.unit import worker_support as support
from tests.unit.worker_support import ScriptedClient, ScriptedCounter

RUN, ATTEMPT = "run-12", 1
SCHEMA = "LEAVE_IMPACT_CRASH_SCHEMA"
WORLD = "LEAVE_IMPACT_CRASH_WORLD"
NONCE = "LEAVE_IMPACT_CRASH_NONCE"


def application_of(schema: str) -> str:
    """The name both of this child's connections carry, so the parent can see them end."""
    return f"crash-{schema}"


# --- The seamed pieces -----------------------------------------------------------------------


@dataclass
class CrossingStore:
    """The store with the kind of each writing command set for the boundary's name, and every
    receipt witnessed."""

    inner: LogStore

    def load(self, run_id: str, attempt: int, *, rules: Rules) -> AttemptState:
        injector.set_kind("load")
        return self.inner.load(run_id, attempt, rules=rules)

    def now(self) -> datetime:
        return self.inner.now()

    def claim(
        self,
        run_id: str,
        attempt: int,
        *,
        harness: HarnessRevision,
        nonce: str,
        launch: str,
        rules: Rules,
        override: CommitOverride | None = None,
        state: AttemptState | None = None,
    ) -> Transition:
        injector.set_kind("segment_started")
        return self._witnessed(
            self.inner.claim(
                run_id,
                attempt,
                harness=harness,
                nonce=nonce,
                launch=launch,
                rules=rules,
                override=override,
                state=state,
            ),
            "segment_started",
        )

    def append(
        self,
        run_id: str,
        attempt: int,
        envelope: Envelope | Stamping,
        event: Event,
        *,
        rules: Rules,
        state: AttemptState | None = None,
    ) -> Transition:
        kind = kind_of(event).value
        injector.set_kind(kind)
        return self._witnessed(
            self.inner.append(run_id, attempt, envelope, event, rules=rules, state=state), kind
        )

    def close_attempt(
        self,
        run_id: str,
        attempt: int,
        envelope: Envelope | Stamping,
        closing: ClosingEvent,
        *,
        rules: Rules,
        state: AttemptState | None = None,
    ) -> Transition:
        kind = kind_of(closing).value
        injector.set_kind(kind)
        return self._witnessed(
            self.inner.close_attempt(run_id, attempt, envelope, closing, rules=rules, state=state),
            kind,
        )

    def _witnessed(self, transition: Transition, kind: str) -> Transition:
        if isinstance(transition, Received):
            injector.witness("receipt", kind=kind, position=transition.position)
        return transition


def boundary(name: str) -> None:
    injector.cross(f"{injector.current_kind()}:{name}")


class SeamedSaver(PostgresSaver):
    """The accepted workaround's shape (the acceptance spike's ruling 6): public API only, a
    subclass that overrides the two write methods and calls the parent, crossing before and
    after each. ``put_writes`` keeps its ``task_path`` parameter because the framework
    inspects the signature for it."""

    def put(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        injector.cross("checkpoint:before")
        result = super().put(config, checkpoint, metadata, new_versions)
        injector.cross("checkpoint:after")
        return result

    def put_writes(self, config: Any, writes: Any, task_id: str, task_path: str = "") -> None:
        injector.cross("writes:before")
        super().put_writes(config, writes, task_id, task_path)
        injector.cross("writes:after")


class WitnessedClient(ScriptedClient):
    """The scripted client with each send and each returned response witnessed."""

    def send(self, requested_profile: str, body: Any) -> Sent:
        digest = support.request_digest(body)
        injector.witness("send", digest=digest)
        sent = super().send(requested_profile, body)
        injector.witness("response", digest=digest)
        return sent


class WitnessedPort:
    """A port whose every method call is witnessed with the method's name."""

    def __init__(self, inner: object, family: str) -> None:
        self._inner = inner
        self._family = family

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if not callable(attribute):
            return attribute

        def witnessed(*args: Any, **kwargs: Any) -> Any:
            injector.witness("read", port=self._family, method=name)
            return attribute(*args, **kwargs)

        return witnessed


def witnessed_ports(ports: ReadPorts) -> ReadPorts:
    return ReadPorts(
        WitnessedPort(ports.people, "people"),  # type: ignore[arg-type]
        WitnessedPort(ports.work, "work"),  # type: ignore[arg-type]
        WitnessedPort(ports.calendar, "calendar"),  # type: ignore[arg-type]
        WitnessedPort(ports.documents, "documents"),  # type: ignore[arg-type]
    )


# --- The connections -------------------------------------------------------------------------


def connect_in(
    schema: str, application: str | None = None
) -> Callable[[str], psycopg.Connection[Any]]:
    """A connect seam into ``schema`` under ``application``'s name, the child's by default;
    the parent names its own connections apart so a child's can be seen to end."""
    name = application_of(schema) if application is None else application

    def connect(dsn: str) -> psycopg.Connection[Any]:
        return psycopg.connect(
            make_conninfo(dsn, options=f"-c search_path={schema}", application_name=name),
            connect_timeout=10,
            autocommit=True,
        )

    return connect


def saver_in(url: str, schema: str) -> SeamedSaver:
    connection = psycopg.Connection[DictRow].connect(
        make_conninfo(
            url, options=f"-c search_path={schema}", application_name=application_of(schema)
        ),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    saver = SeamedSaver(connection)
    saver.setup()
    return saver


# --- The process -----------------------------------------------------------------------------


def main() -> int:
    url = os.environ["DATABASE_URL"]
    schema = os.environ[SCHEMA]
    nonce = os.environ[NONCE]
    with Path(os.environ[WORLD]).open("rb") as held:
        context, systems = pickle.load(held)  # noqa: S301 - the parent wrote it this execution
    store = LogStore(dsn=url, connect=connect_in(schema), boundary=boundary)
    commands: LogCommands = CrossingStore(store)
    inputs = commands.load(RUN, ATTEMPT, rules=histories.RULES).inputs
    assert inputs is not None
    turns, client = support.two_call_script(context)
    worker = Worker(
        commands,
        WorkerConfiguration.of(inputs),
        cases.REVISION,
        f"launch-{os.getpid()}",
        histories.RULES,
        turns,
        WitnessedClient(client.answers),
        ScriptedCounter(),
        witnessed_ports(systems.ports),
        AutomaticApproval(),
        saver_in(url, schema),
        boundary=injector.cross,
    )
    ending = worker.work(RUN, ATTEMPT, nonce=nonce)
    print(
        json.dumps(
            {
                "kind": ending.kind.value,
                "detail": ending.detail,
                "generation": ending.generation,
                "pid": os.getpid(),
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["NONCE", "SCHEMA", "WORLD", "application_of", "main"]
