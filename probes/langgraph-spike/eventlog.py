"""The spike's event log: one PostgreSQL table, appended to and never rewritten, that a run's
export is built from with no checkpoint in reach.

The log is the audit authority and the framework's checkpoint the execution cursor (the
acceptance spike's rulings 1, 3 and 5). A node appends what it did before it returns, the
framework writes its checkpoint afterwards on another thread, so the log is ahead of the
checkpoint by construction and the log wins. Everything an export needs is therefore an
event: the run's context and provenance (``run_started``), the process that executed a
stretch of it (``segment_started``, with the process id, the harness commit and the tree
state), each read (``tool_result``), each possible and each confirmed model invocation
(``model_intent``, ``model_outcome``), the approval, and the terminal state.

An event's identifier is deterministic: the run, the attempt, the kind and a position the
writer derives from what it is doing, never a random value, so a replay that reaches the same
point names the same event. An append of an identifier the log already holds is a no-op when
the content is identical and raises when it differs. Identical means equal in one canonical
form with sorted keys, compared by digest: the package's ``canonical_json`` keeps insertion
order, so two builders of one event would disagree under it. The segment and the offset are
the envelope of the first append and are not part of the comparison, since a replayed append
comes from a later process at a different offset.

Every event carries its segment and a monotonic offset from that segment's start. A killed
process never records its end, so a run's duration is evidenced active execution: each
segment contributes the offset of its last durable event.

The log has its own autocommit connection, apart from the saver's: one append is one
statement and is durable when it returns. The crash check's seams sit on either side of that
statement, named by the event's kind and position. One writer per run is assumed; two processes
resuming one run is the event log step's question, not the spike's.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psycopg
from seams import cross, witness

REPOSITORY = Path(__file__).resolve().parents[2]

RUN_STARTED = "run_started"
SEGMENT_STARTED = "segment_started"
TOOL_RESULT = "tool_result"
MODEL_INTENT = "model_intent"
MODEL_OUTCOME = "model_outcome"
APPROVAL = "approval"
RUN_TERMINAL = "run_terminal"

TABLE = "events"

_CREATE = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    seq bigint GENERATED ALWAYS AS IDENTITY,
    event_id text PRIMARY KEY,
    run_id text NOT NULL,
    attempt integer NOT NULL,
    kind text NOT NULL,
    position text NOT NULL,
    segment integer NOT NULL,
    offset_ms bigint NOT NULL,
    content text NOT NULL,
    content_sha256 text NOT NULL
)
"""

_COLUMNS = "seq, event_id, kind, position, segment, offset_ms, content, content_sha256"


class ConflictingAppend(RuntimeError):
    """An identifier the log already holds was appended with different content."""


@dataclass(frozen=True, slots=True)
class Event:
    """One durable event as the log holds it; ``content`` is the canonical text appended."""

    seq: int
    event_id: str
    kind: str
    position: str
    segment: int
    offset_ms: int
    content: str
    digest: str

    @property
    def data(self) -> dict[str, Any]:
        """The content as the JSON object it encodes."""
        return json.loads(self.content)


def sorted_canonical(content: object) -> str:
    """``content`` in the one form two builders of an event agree on: sorted keys, compact.

    >>> sorted_canonical({"b": 1, "a": ["ü", None]})
    '{"a":["ü",null],"b":1}'
    """
    return json.dumps(
        content, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )


def digest_of(text: str) -> str:
    """The SHA-256 of ``text`` as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def harness_revision() -> dict[str, str]:
    """The commit this process runs from and whether the tree differs from it."""
    commit = _git("rev-parse", "HEAD")
    return {"commit": commit, "tree": "dirty" if _git("status", "--porcelain") else "clean"}


def _git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments], cwd=REPOSITORY, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


APPLICATION = "leave-impact-spike"


def connect(
    url: str, schema: str, application: str = APPLICATION
) -> psycopg.Connection[tuple[Any, ...]]:
    """An autocommit connection whose unqualified names resolve in ``schema``, its session
    named ``application`` so a parent can tell when a killed child's sessions have ended."""
    return psycopg.connect(
        url, autocommit=True, options=f"-c search_path={schema}", application_name=application
    )


def read_events(
    connection: psycopg.Connection[tuple[Any, ...]], run_id: str, attempt: int
) -> tuple[Event, ...]:
    """Every event of the run attempt, in append order."""
    rows = connection.execute(
        f"SELECT {_COLUMNS} FROM {TABLE} WHERE run_id = %s AND attempt = %s ORDER BY seq",
        (run_id, attempt),
    ).fetchall()
    return tuple(Event(*row) for row in rows)


@dataclass
class EventLog:
    """One process's handle on a run attempt's log: it opens a segment and appends under it.

    ``open`` creates the table if it is absent, numbers this process's segment one past the
    segments already logged, starts the segment's clock and appends the segment's start.
    ``held_again`` lists the identifiers this process appended and the log already held: the
    log cannot hold a duplicate by construction, so a count of its rows says nothing about
    how often something was done, and this list is what says an append was a repeat.
    """

    connection: psycopg.Connection[tuple[Any, ...]]
    run_id: str
    attempt: int
    segment: int
    started_ns: int
    held_again: list[str] = field(default_factory=list[str])

    @classmethod
    def open(
        cls, connection: psycopg.Connection[tuple[Any, ...]], run_id: str, attempt: int
    ) -> EventLog:
        """The log of ``run_id``'s ``attempt`` with a new segment started for this process."""
        if "/" in run_id:
            raise ValueError(f"a run id holds no '/', the identifier's separator, got {run_id!r}")
        connection.execute(_CREATE)
        earlier = sum(e.kind == SEGMENT_STARTED for e in read_events(connection, run_id, attempt))
        log = cls(connection, run_id, attempt, earlier + 1, time.monotonic_ns())
        log.append(
            SEGMENT_STARTED,
            str(log.segment),
            {"segment": log.segment, "pid": os.getpid(), **harness_revision()},
        )
        return log

    def event_id(self, kind: str, position: str) -> str:
        """The deterministic identifier of the ``kind`` event at ``position`` of this attempt."""
        return f"{self.run_id}/{self.attempt}/{kind}/{position}"

    def append(self, kind: str, position: str, content: dict[str, Any]) -> Event:
        """Append the event and answer with it as held; an identical one already held is
        answered unchanged, with the envelope of its first append.

        Raises ``ConflictingAppend`` when the identifier is held with different content.
        """
        text = sorted_canonical(content)
        digest = digest_of(text)
        identifier = self.event_id(kind, position)
        offset_ms = (time.monotonic_ns() - self.started_ns) // 1_000_000
        cross(f"{kind}/{position}", "append:before")
        inserted = self.connection.execute(
            f"INSERT INTO {TABLE} (event_id, run_id, attempt, kind, position, segment, "
            "offset_ms, content, content_sha256) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (event_id) DO NOTHING RETURNING seq",
            (
                identifier,
                self.run_id,
                self.attempt,
                kind,
                position,
                self.segment,
                offset_ms,
                text,
                digest,
            ),
        ).fetchone()
        cross(f"{kind}/{position}", "append:after")
        if inserted is None:
            self.held_again.append(identifier)
            witness("repeated_append", event=identifier)
        held = self.find(kind, position)
        if held is None:
            raise RuntimeError(f"{identifier} was appended and cannot be read back")
        if held.digest != digest:
            raise ConflictingAppend(
                f"{identifier} is held with content {held.digest}, appended with {digest}"
            )
        return held

    def find(self, kind: str, position: str) -> Event | None:
        """The ``kind`` event at ``position``, or ``None`` when the log holds none."""
        row = self.connection.execute(
            f"SELECT {_COLUMNS} FROM {TABLE} WHERE event_id = %s",
            (self.event_id(kind, position),),
        ).fetchone()
        return None if row is None else Event(*row)

    def events(self, kind: str | None = None) -> tuple[Event, ...]:
        """The attempt's events in append order, of ``kind`` when one is named."""
        held = read_events(self.connection, self.run_id, self.attempt)
        return held if kind is None else tuple(e for e in held if e.kind == kind)
