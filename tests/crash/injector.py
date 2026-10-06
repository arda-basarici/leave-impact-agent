"""The fault injector: one function at every crossing, which records it and, at the one
crossing it was told to, ends the process; and the witnesses of what the run did outside
the log.

The crash check kills the process and never raises (the acceptance spike's ruling 3): an
exception would let the framework's handlers run and the driver's handler classify it.
``os._exit`` ends the process from whichever thread reaches the crossing, the saver's
background thread included, with no handler, no cleanup and no flush of anything but what
was already synced.

A crossing is named by what was being done and the phase of doing it, never by an ordinal
over the run: the full identity is the name and its occurrence in this process,
``<kind>:<boundary>#<n>``, and occurrences restart with every process, so a recovering
child's first operation write is its ``operation:decided#1`` whatever the first process
did. The record is one append-only JSON-lines file outside both stores, never read by the
worker; it holds each crossing and each witnessed activity (a send leaving, a response
returned, a port read, a receipt the store gave for a held event), every line written under
one lock and synced before the call returns. With no record configured every function here
does nothing, which is how the reference child and the uninterrupted gate run.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

RECORD = "LEAVE_IMPACT_CRASH_RECORD"
TARGET = "LEAVE_IMPACT_CRASH_TARGET"
KILL_CODE = 86
"""The exit code of a child that died at its target; any other ending fails the row."""

_lock = threading.Lock()
_counts: dict[str, int] = {}
_started = time.monotonic()


def current_kind() -> str:
    """The event kind the store is writing on this thread, set by the crossing store."""
    return getattr(_state, "kind", "none")


def set_kind(kind: str) -> None:
    _state.kind = kind


_state = threading.local()


def cross(name: str) -> None:
    """Record the crossing ``name`` and die here if it is the target."""
    path = os.environ.get(RECORD)
    if not path:
        return
    with _lock:
        count = _counts.get(name, 0) + 1
        _counts[name] = count
        crossing = f"{name}#{count}"
        _write(path, {"process": os.getpid(), "ms": _ms(), "crossing": crossing})
    if crossing == os.environ.get(TARGET):
        os._exit(KILL_CODE)


def witness(what: str, **detail: Any) -> None:
    """Record an activity the log does not show: a send, a response, a port read, a receipt."""
    path = os.environ.get(RECORD)
    if not path:
        return
    with _lock:
        _write(path, {"process": os.getpid(), "ms": _ms(), "witness": what, **detail})


def read_record(path: Path) -> list[dict[str, Any]]:
    """Every line of the record, in the order the lock was taken."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def family(crossing: str) -> str:
    """``operation:decided`` of ``operation:decided#3``: the kill point's name without its
    occurrence, what the manifest forecasts."""
    return crossing.split("#", 1)[0]


def _ms() -> int:
    return int((time.monotonic() - _started) * 1000)


def _write(path: str, line: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as record:
        record.write(json.dumps(line, sort_keys=True) + "\n")
        record.flush()
        os.fsync(record.fileno())


__all__ = [
    "KILL_CODE",
    "RECORD",
    "TARGET",
    "cross",
    "current_kind",
    "family",
    "read_record",
    "set_kind",
    "witness",
]
