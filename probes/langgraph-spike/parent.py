"""What the crash check's parent process does around its children: prepare the world once,
start a child and judge how it ended, wait for a dead child's database sessions to end, and
read both stores.

The parent holds everything a child must not influence. It names the schema, the injector's
record and the kill target; it decides from the exit code and the record whether the child
died at its target, and any other ending fails the row it belongs to. After a kill it waits
until PostgreSQL shows no session under the child's application name before it reads
anything: the process is gone at once, but a statement it had in flight can still finish on
the server, and a boundary read before that would describe a state that was about to change.

The checkpoint store is read through a plain saver of the pinned library, its public
``list``: every checkpoint of the thread with its channel values and its pending writes.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from eventlog import Event, connect, read_events
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.conninfo import make_conninfo
from psycopg.rows import DictRow, dict_row
from psycopg.sql import SQL, Identifier
from run_uninterrupted import ATTEMPT, RUN_ID, THREAD, scenario_and_baseline, script
from seams import KILL_EXIT_CODE, KILL_VARIABLE, RECORD_VARIABLE, read_record

from tests.unit.reads_fixture import systems_holding

CHILD = Path(__file__).with_name("child.py")
PARENT = "leave-impact-spike-parent"
"""The session name of the parent's own reads, never a child's."""
CHILD_TIMEOUT_SECONDS = 120
SESSIONS_TIMEOUT_SECONDS = 20


@dataclass(frozen=True, slots=True)
class World:
    """The world every child of one execution runs: the file, its digest, and what the parent
    keeps of it for its own comparisons."""

    path: Path
    sha256: str
    scenario: str
    turns: int


@dataclass(frozen=True, slots=True)
class Ended:
    """How one child ended: its exit code, what it printed on a normal exit, the lines it added
    to the injector's record, and the wall-clock bracket the parent took around it."""

    code: int
    report: dict[str, Any] | None
    lines: tuple[dict[str, Any], ...]
    bracket_ms: int
    stderr: str

    def died_at(self, target: str) -> bool:
        """Whether the child exited with the injector's code at exactly ``target``: the code
        is the injector's and its last recorded line is that crossing, marked killed."""
        if self.code != KILL_EXIT_CODE or not self.lines:
            return False
        last = self.lines[-1]
        return last.get("crossing") == target and last.get("killed") is True

    def crossings(self) -> list[str]:
        """The crossings the child made, in the order the injector's lock was taken."""
        return [line["crossing"] for line in self.lines if line["kind"] == "crossing"]


def prepare_world(directory: Path) -> World:
    """Serialize the scenario's context, the script's turns and the in-memory systems once."""
    context, baseline, leaver, world = scenario_and_baseline()
    turns = script(baseline.claims, leaver)
    serialized = pickle.dumps(
        {"context": context, "turns": turns, "systems": systems_holding(world)}
    )
    path = directory / "world.pickle"
    path.write_bytes(serialized)
    return World(path, hashlib.sha256(serialized).hexdigest(), context.scenario_id, len(turns))


def application_of(schema: str) -> str:
    """The session name of the children that run in ``schema``."""
    return schema[:63]


def start_child(
    schema: str, world: World, record: Path, count_file: Path, kill_at: str | None = None
) -> Ended:
    """Run one child in ``schema`` to its end, killed at ``kill_at`` when one is named."""
    environment = {**os.environ, RECORD_VARIABLE: str(record)}
    environment.pop(KILL_VARIABLE, None)
    if kill_at is not None:
        environment[KILL_VARIABLE] = kill_at
    before = len(read_record(str(record)))
    started = time.monotonic_ns()
    done = subprocess.run(
        [
            sys.executable,
            str(CHILD),
            "--schema",
            schema,
            "--application",
            application_of(schema),
            "--world",
            str(world.path),
            "--world-sha256",
            world.sha256,
            "--count-file",
            str(count_file),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=CHILD_TIMEOUT_SECONDS,
        check=False,
    )
    bracket_ms = (time.monotonic_ns() - started) // 1_000_000
    printed = done.stdout.strip().splitlines()
    report = json.loads(printed[-1]) if done.returncode == 0 and printed else None
    lines = tuple(read_record(str(record))[before:])
    return Ended(done.returncode, report, lines, bracket_ms, done.stderr[-2000:])


def sessions_ended(admin: psycopg.Connection[Any], schema: str) -> bool:
    """Wait until the server shows no session of ``schema``'s children; whether it got there."""
    deadline = time.monotonic() + SESSIONS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        row = admin.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE application_name = %s",
            (application_of(schema),),
        ).fetchone()
        if row is not None and row[0] == 0:
            return True
        time.sleep(0.05)
    return False


def create_schema(admin: psycopg.Connection[Any], schema: str) -> None:
    admin.execute(SQL("CREATE SCHEMA {}").format(Identifier(schema)))


def drop_schema(admin: psycopg.Connection[Any], schema: str) -> None:
    admin.execute(SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(Identifier(schema)))


def logged(url: str, schema: str) -> tuple[Event, ...]:
    """The attempt's events as the log holds them now; none when the table does not exist."""
    with connect(url, schema, PARENT) as connection:
        exists = connection.execute("SELECT to_regclass('events')").fetchone()
        if exists is None or exists[0] is None:
            return ()
        return read_events(connection, RUN_ID, ATTEMPT)


def by_task(pending: list[tuple[str, str, Any]]) -> list[list[tuple[str, Any]]]:
    """Pending writes grouped as the saver was handed them, one list per task."""
    tasks: dict[str, list[tuple[str, Any]]] = {}
    for task, channel, value in pending:
        tasks.setdefault(task, []).append((channel, value))
    return list(tasks.values())


def checkpoint_rows(url: str, schema: str) -> int | None:
    """The rows of the checkpoint table, or ``None`` when the table does not exist."""
    with connect(url, schema, PARENT) as connection:
        exists = connection.execute("SELECT to_regclass('checkpoints')").fetchone()
        if exists is None or exists[0] is None:
            return None
        row = connection.execute("SELECT count(*) FROM checkpoints").fetchone()
        return 0 if row is None else row[0]


def checkpointed(url: str, schema: str, thread: str = THREAD) -> list[dict[str, Any]]:
    """Every checkpoint of ``thread``, newest first: its step, the results its state holds,
    and its pending writes, one list of channel and value per task; none when the store's
    tables do not exist. The saver read through is constructed without its ``setup``, so
    reading the store never creates it."""
    if checkpoint_rows(url, schema) is None:
        return []
    connection = psycopg.Connection[DictRow].connect(
        make_conninfo(url, options=f"-c search_path={schema}", application_name=PARENT),
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    )
    saver = PostgresSaver(connection)
    try:
        held: list[dict[str, Any]] = []
        for found in saver.list({"configurable": {"thread_id": thread}}):
            held.append(
                {
                    "step": found.metadata.get("step"),
                    "results": dict(found.checkpoint["channel_values"].get("results", {})),
                    "pending": by_task(found.pending_writes or []),
                }
            )
        return held
    finally:
        saver.conn.close()
