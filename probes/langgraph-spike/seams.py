"""The fault injector's hook: one function at every seam, which records the crossing and, at the
one crossing it was told to, ends the process.

The crash check kills the process and never raises (the acceptance spike's ruling 3): an
exception would let the framework's handlers run and save state. ``os._exit`` ends the
process from whichever thread reaches the seam, the saver's background thread included,
with no handler, no cleanup and no flush of anything but what was already synced.

A crossing is named by what was being done and the phase of doing it, never by an ordinal
over the run: the order of a task's pending writes against the step's checkpoint is not
fixed, so a count of crossings would name different moments in different runs. A name can
recur within one process (a node rerun, a second checkpoint of one step), so the full
identity is the name and its occurrence in this process, ``<operation>:<phase>#<n>``.

The injector's record is one append-only JSON-lines file, outside both stores and never
read by the graph or by recovery. It holds each crossing and each witnessed activity (a
model request arriving, a response about to be returned, a tool dispatched to a port), every
line written under one lock and synced before the call returns, so the record survives the
kill and its order is the order the lock was taken in. Each line carries its process and
the milliseconds since this module was loaded there, a clock that starts before the event
log's segment clock does, so a segment's offsets can be bounded by its own process's lines.
With no record file configured every function here does nothing, which is how the
uninterrupted gate runs.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

RECORD_VARIABLE = "LEAVE_IMPACT_SPIKE_INJECTOR_RECORD"
KILL_VARIABLE = "LEAVE_IMPACT_SPIKE_KILL_AT"
KILL_EXIT_CODE = 77
"""What a child that died at its target exits with; any other code is another failure."""

PHASES = (
    "append:before",
    "append:after",
    "put:before",
    "put:after",
    "put_writes:before",
    "put_writes:after",
    "delivery:before",
    "node:resumed",
)
"""Every phase a seam is crossed in. An operation's name may itself hold a colon, so a
crossing is taken apart by its phase, from the right."""

_STARTED_NS = time.monotonic_ns()
_lock = threading.Lock()
_occurrences: dict[str, int] = {}


def cross(operation: str, phase: str) -> None:
    """Record the crossing of the seam ``phase`` of ``operation`` and, when it is the kill
    target, end the process."""
    path = os.environ.get(RECORD_VARIABLE)
    if not path:
        return
    name = f"{operation}:{phase}"
    with _lock:
        occurrence = _occurrences[name] = _occurrences.get(name, 0) + 1
        identity = f"{name}#{occurrence}"
        killed = os.environ.get(KILL_VARIABLE) == identity
        _write(path, {"kind": "crossing", "crossing": identity, "killed": killed})
        if killed:
            os._exit(KILL_EXIT_CODE)


def parts(crossing: str) -> tuple[str, str, int]:
    """The operation, the phase and the occurrence of a crossing's identity.

    >>> parts("writes/branch:to:prefetch+turn:put_writes:after#2")
    ('writes/branch:to:prefetch+turn', 'put_writes:after', 2)
    """
    name, _, occurrence = crossing.rpartition("#")
    for phase in PHASES:
        if name.endswith(f":{phase}"):
            return name[: -len(phase) - 1], phase, int(occurrence)
    raise ValueError(f"{crossing!r} ends in no known phase")


def witness(kind: str, **detail: Any) -> None:
    """Record an activity the stores cannot count: a model request, a response, a dispatch."""
    path = os.environ.get(RECORD_VARIABLE)
    if not path:
        return
    with _lock:
        _write(path, {"kind": kind, **detail})


def _write(path: str, line: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as record:
        stamp = {"pid": os.getpid(), "at_ms": (time.monotonic_ns() - _STARTED_NS) // 1_000_000}
        record.write(json.dumps({**stamp, **line}, ensure_ascii=False) + "\n")
        record.flush()
        os.fsync(record.fileno())


def read_record(path: str) -> list[dict[str, Any]]:
    """Every line of the injector's record, in order; none when the file does not exist."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as record:
        return [json.loads(line) for line in record if line.strip()]
