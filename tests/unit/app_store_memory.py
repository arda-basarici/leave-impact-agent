"""The demo surface's store in memory: the publishable and the live rows as lists, the
store's reads over them, and the public start's critical section as one lock with the
store's boundary names, its writes staged and kept only when the section ends without an
exception, so a unit test of the start drives the lost rows of history 7 and the
serialization of history 8 the way the real store's tests do.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field

from leaveimpact.app.live import LiveDraft, LiveRow
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

    @contextmanager
    def start_section(self, ledger_id: str) -> Generator[MemorySection]:
        """The real store's section: the lock held for the block, the two boundary names,
        the staged rows kept when the block ends and dropped when an exception leaves it."""
        with self.lock:
            self.boundary("start-locked")
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
        for held in (*self.store.rows, *self.rows):
            if held.public_id == publishable.public_id or (held.run_id, held.attempt) == (
                publishable.run_id,
                publishable.attempt,
            ):
                raise MemoryAppStoreInvariant(f"a row holds {publishable.public_id} already")
        for held_live in (*self.store.live, *self.live):
            if held_live.key_digest == live.key_digest:
                raise MemoryAppStoreInvariant("a live row holds the key digest already")
        self.rows.append(
            PublishableRow(
                publishable.public_id,
                publishable.run_id,
                publishable.attempt,
                publishable.world_version,
                publishable.scenario_id,
                publishable.title,
                live.started_at,
                publishable.published_by,
            )
        )
        row = LiveRow(
            live.public_id, live.run_id, live.attempt, live.key_digest, live.started_at, None, None
        )
        self.live.append(row)
        return row


__all__ = ["MemoryAppStore", "MemoryAppStoreInvariant", "MemorySection"]
