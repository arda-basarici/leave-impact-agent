"""The heartbeat module the worker service's healthcheck runs: it imports the standard
library alone, so the check costs a bare interpreter and not the worker's two seconds of
imports; run as a module it answers with its exit status from the environment's path and
the real clock; and ``main`` reads the path and the clock it is given."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from leaveimpact.app import heartbeat
from leaveimpact.app.heartbeat import HEARTBEAT_FILE, Heartbeat, main

MODULE = Path(heartbeat.__file__)


def test_the_module_imports_the_standard_library_alone() -> None:
    """The healthcheck's cost is the interpreter's start only while this holds; the worker
    module it was carved out of costs about two seconds a call through the sweeper and
    the agent (the worker service step's group 3), a steady eight percent of a vCPU at a
    thirty-second interval."""
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module is not None and node.level == 0
            imported.append(node.module)
    assert imported, "the scan found no imports; the module changed shape"
    foreign = [name for name in imported if name.split(".")[0] not in sys.stdlib_module_names]
    assert foreign == [], f"the healthcheck's module imports beyond the standard library: {foreign}"


def test_run_as_a_module_the_check_answers_with_its_exit_status(tmp_path: Path) -> None:
    """What the compose healthcheck runs, as a process: 1 with no heartbeat, 0 while the
    deadline is ahead of the real clock, 1 once it is behind."""
    beat = tmp_path / "beat.json"
    env = {**os.environ, HEARTBEAT_FILE: str(beat)}

    def check() -> int:
        return subprocess.run(
            [sys.executable, "-m", "leaveimpact.app.heartbeat"], env=env, check=False
        ).returncode

    assert check() == 1
    Heartbeat("idle", datetime.now(UTC) + timedelta(hours=1)).write(beat)
    assert check() == 0
    Heartbeat("working", datetime.now(UTC) - timedelta(seconds=1)).write(beat)
    assert check() == 1


def test_main_reads_the_path_from_the_environment_and_the_clock_given(tmp_path: Path) -> None:
    beat = tmp_path / "beat.json"
    now = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)
    env = {HEARTBEAT_FILE: str(beat)}
    assert main(env, lambda: now) == 1
    Heartbeat("idle", now + timedelta(seconds=6)).write(beat)
    assert main(env, lambda: now) == 0
    assert main(env, lambda: now + timedelta(seconds=6)) == 1
    beat.write_text("{not json", encoding="utf-8")
    assert main(env, lambda: now) == 1
