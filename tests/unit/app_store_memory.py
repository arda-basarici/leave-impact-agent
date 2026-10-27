"""The demo surface's store in memory: the publishable and the live rows as lists, the
store's reads over them, and the start's section as one lock with the store's boundary
name before its commit, its writes staged and kept only when the section ends without an
exception, so a unit test of the start drives the lost rows of history 7 the way the real
store's tests do.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime

from leaveimpact.app.live import Decision, LiveDraft, LiveRow
from leaveimpact.app.public import PublicationDraft, PublicId, PublishableRow
from leaveimpact.core.ids import WorldVersion


class MemoryAppStoreInvariant(Exception):
    """A write the real store's constraints would refuse on the server."""


def _no_boundary(name: str) -> None:
    return None


@dataclass
class MemoryAppStore:
    """The two tables, the reads, and the start's section."""

    rows: list[PublishableRow] = field(default_factory=list[PublishableRow])
    live: list[LiveRow] = field(default_factory=list[LiveRow])
    boundary: Callable[[str], None] = _no_boundary
    lock: threading.Lock = field(default_factory=threading.Lock)

    def rows_for(self, world_version: WorldVersion) -> tuple[PublishableRow, ...]:
        with self.lock:
            return tuple(
                sorted(
                    (each for each in self.rows if each.world_version == world_version),
                    key=lambda each: (each.published_at, each.public_id),
                )
            )

    def row_of(self, public_id: PublicId) -> PublishableRow | None:
        with self.lock:
            return next((each for each in self.rows if each.public_id == public_id), None)

    def live_row_of(self, public_id: PublicId) -> LiveRow | None:
        with self.lock:
            return next((each for each in self.live if each.public_id == public_id), None)

    def live_row_of_attempt(self, run_id: str, attempt: int) -> LiveRow | None:
        with self.lock:
            return next(
                (each for each in self.live if (each.run_id, each.attempt) == (run_id, attempt)),
                None,
            )

    def record_decision(
        self, public_id: PublicId, decision: Decision, decided_at: datetime
    ) -> LiveRow:
        """The real store's unconditional write of the decision columns, the boundary name
        before it; no row under the id is the real store's invariant."""
        self.boundary("decide-before-record")
        with self.lock:
            index = next(
                (at for at, each in enumerate(self.live) if each.public_id == public_id), None
            )
            if index is None:
                raise MemoryAppStoreInvariant(f"no live row holds {public_id}")
            self.live[index] = replace(
                self.live[index], decision=decision, decided_at=decided_at
            )
            return self.live[index]

    @contextmanager
    def start_section(self) -> Generator[MemorySection]:
        """The real store's section: one transaction over the rows, the boundary name
        before its commit, the staged rows kept when the block ends and dropped when an
        exception leaves it."""
        with self.lock:
            section = MemorySection(self)
            yield section
            self.boundary("start-before-commit")
            self.rows.extend(section.rows)
            self.live.extend(section.live)


@dataclass
class MemorySection:
    """One section's staged writes over the store's rows."""

    store: MemoryAppStore
    rows: list[PublishableRow] = field(default_factory=list[PublishableRow])
    live: list[LiveRow] = field(default_factory=list[LiveRow])

    def live_row_of_attempt(self, run_id: str, attempt: int) -> LiveRow | None:
        return next(
            (
                each
                for each in (*self.store.live, *self.live)
                if (each.run_id, each.attempt) == (run_id, attempt)
            ),
            None,
        )

    def write(self, publishable: PublicationDraft, live: LiveDraft) -> LiveRow:
        if (publishable.public_id, publishable.run_id, publishable.attempt) != (
            live.public_id,
            live.run_id,
            live.attempt,
        ):
            raise ValueError("the publishable row and the live row name one attempt")
        expected = PublishableRow(
            publishable.public_id,
            publishable.run_id,
            publishable.attempt,
            publishable.world_version,
            publishable.scenario_id,
            publishable.title,
            live.started_at,
            publishable.published_by,
        )
        row = LiveRow(
            live.public_id, live.run_id, live.attempt, live.key_digest, live.started_at, None, None
        )
        # The real section's get-or-create: rows already held under the public id are the
        # receipt when they are this start's, and an invariant when they are another's.
        held = next(
            (each for each in (*self.store.rows, *self.rows) if each.public_id == row.public_id),
            None,
        )
        held_live = next(
            (each for each in (*self.store.live, *self.live) if each.public_id == row.public_id),
            None,
        )
        if held is not None or held_live is not None:
            if held != expected or held_live is None or (
                held_live.run_id,
                held_live.attempt,
                held_live.key_digest,
                held_live.started_at,
            ) != (row.run_id, row.attempt, row.key_digest, row.started_at):
                raise MemoryAppStoreInvariant(f"the rows under {row.public_id} are another's")
            return held_live
        for other in (*self.store.rows, *self.rows):
            if (other.run_id, other.attempt) == (publishable.run_id, publishable.attempt):
                raise MemoryAppStoreInvariant("another public id holds the attempt")
        for other_live in (*self.store.live, *self.live):
            if other_live.key_digest == live.key_digest:
                raise MemoryAppStoreInvariant("another live row holds the key digest")
        self.rows.append(expected)
        self.live.append(row)
        return row


__all__ = ["MemoryAppStore", "MemoryAppStoreInvariant", "MemorySection"]
