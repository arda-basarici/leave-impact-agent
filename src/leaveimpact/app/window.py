"""The per-address window of the public start: how many admissions one client address may
have in a UTC day, kept in the process's memory.

The daily cap bounds what the demo spends; this window bounds what one address may take
of it (the live-path commands step, fork 8): two admissions per address per UTC day, so a
stranger cannot spend the whole day's five from one chair. It counts admissions and
nothing else, since a refusal costs nothing and a repeat of a recorded start is answered
before the window is asked (group 4's design pass: a window checked on the route ahead of
the command refused the repeat that was owed its cookie). One worker process serves the
demo, so the process's memory is the window's whole state; a restart forgets it, which
costs nothing the daily cap does not already hold, and a durable column was not worth a
schema for a limit of this size. The window is consulted inside the start's serialized
block, so its reads and writes never interleave with another start's; the lock here is
for the honesty of the type, not a second serialization point.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

ADDRESS_ADMISSIONS_PER_DAY = 2
"""Fork 8's value: what one client address may be admitted in a UTC day."""


class AddressWindow(Protocol):
    """The window as the start consults it: whether ``address`` may be admitted again in the
    day that began at ``since``, and the note of an admission at ``at``."""

    def admits(self, address: str, *, since: datetime) -> bool: ...

    def note(self, address: str, at: datetime) -> None: ...


@dataclass
class MemoryWindow:
    """The window over a dictionary of admission instants per address; instants before the
    day asked about are dropped as they are read, so the memory holds at most a day."""

    limit: int = ADDRESS_ADMISSIONS_PER_DAY
    admissions: dict[str, list[datetime]] = field(default_factory=dict[str, list[datetime]])
    lock: threading.Lock = field(default_factory=threading.Lock)

    def admits(self, address: str, *, since: datetime) -> bool:
        """Whether fewer than the limit were admitted from ``address`` at or after ``since``.

        >>> from datetime import UTC
        >>> day = datetime(2026, 10, 27, tzinfo=UTC)
        >>> window = MemoryWindow(limit=1)
        >>> window.admits("203.0.113.7", since=day)
        True
        >>> window.note("203.0.113.7", datetime(2026, 10, 27, 9, tzinfo=UTC))
        >>> window.admits("203.0.113.7", since=day)
        False
        >>> window.admits("203.0.113.7", since=datetime(2026, 10, 28, tzinfo=UTC))
        True
        """
        with self.lock:
            kept = [at for at in self.admissions.get(address, ()) if at >= since]
            if kept:
                self.admissions[address] = kept
            else:
                self.admissions.pop(address, None)
            return len(kept) < self.limit

    def note(self, address: str, at: datetime) -> None:
        with self.lock:
            self.admissions.setdefault(address, []).append(at)


__all__ = ["ADDRESS_ADMISSIONS_PER_DAY", "AddressWindow", "MemoryWindow"]
