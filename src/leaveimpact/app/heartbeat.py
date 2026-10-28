"""The worker's heartbeat and the healthcheck that reads it, apart from the worker so the
check costs a bare interpreter.

The worker service's compose healthcheck runs ``python -m leaveimpact.app.heartbeat`` every
interval in the container's own cgroup. The worker module imports the sweeper and the agent,
about two seconds of CPU on the workstation (measured at the worker service step's group 3:
2.3 to 2.7 s for ``python -m leaveimpact.app worker-health`` over three runs, 0.15 s for the
interpreter with this package's init), which at a thirty-second interval is a steady eight
percent of a vCPU spent on reading one small file. This module imports the standard library
alone, so the check costs the interpreter's start; a test holds the import list to that,
since the cost returns the day a package import is added here.

The heartbeat is what the loop last said of itself (``app.worker``): a state and a deadline,
idle three intervals ahead and rewritten per tick, working the claim's instant plus the wall
plus the cleanup allowance. The check compares the clock with the deadline, one rule for both
states, so a loop that stopped ticking and a worker past its wall and its cleanup both read
unhealthy while an attempt lasting minutes reads healthy. The ``worker-health`` command of
``leaveimpact.app`` is the operator's word for the same read and calls ``worker_healthy``
too.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

HEARTBEAT_FILE = "LEAVEIMPACT_HEARTBEAT_FILE"
"""The environment name of the heartbeat's path."""

DEFAULT_HEARTBEAT_PATH = Path("/tmp/leaveimpact-worker-heartbeat.json")  # noqa: S108 - the container's own tmpfs, read by its healthcheck alone


@dataclass(frozen=True, slots=True)
class Heartbeat:
    """What the loop last said of itself: idle or working, and the instant past which the
    claim is stale."""

    state: str
    deadline: datetime

    def write(self, path: Path) -> None:
        """Written whole then moved into place, so a reader never sees a torn file."""
        staged = path.with_name(path.name + ".tmp")
        staged.write_text(
            json.dumps({"state": self.state, "deadline": self.deadline.isoformat()}),
            encoding="utf-8",
        )
        os.replace(staged, path)

    @classmethod
    def read(cls, path: Path) -> Heartbeat | None:
        """The heartbeat at ``path``, or ``None`` when absent or unreadable."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(str(data["state"]), datetime.fromisoformat(str(data["deadline"])))
        except (OSError, ValueError, KeyError, TypeError):
            return None


def worker_healthy(path: Path, now: datetime) -> bool:
    """The healthcheck's one bit: a heartbeat present whose deadline is still ahead."""
    beat = Heartbeat.read(path)
    return beat is not None and now < beat.deadline


def heartbeat_path(environment: Mapping[str, str]) -> Path:
    """The heartbeat's path: the one the environment names, or the container's default.

    >>> heartbeat_path({"LEAVEIMPACT_HEARTBEAT_FILE": " /run/beat.json "}).as_posix()
    '/run/beat.json'
    >>> heartbeat_path({}) == DEFAULT_HEARTBEAT_PATH
    True
    """
    named = environment.get(HEARTBEAT_FILE, "").strip()
    return Path(named) if named else DEFAULT_HEARTBEAT_PATH


def main(
    environment: Mapping[str, str] = os.environ,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """The check's exit status: 0 while the heartbeat at the environment's path has its
    deadline ahead of ``now``, 1 when it is stale, absent or unreadable."""
    return 0 if worker_healthy(heartbeat_path(environment), now()) else 1


if __name__ == "__main__":
    sys.exit(main())
