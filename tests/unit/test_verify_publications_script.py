"""The publication-digests sender under the fake ``aws``: the host script it sends puts the
three variables compose interpolates and runs the deploy's own compose line, a Success with
exit code 0 is the sender's 0 with the host's lines printed, a Failed is its 1 with the exit
code named, and every uncertain end (the poll deadline, a CLI that keeps failing, no running
host) is its 2 (the live-path step's group 3, its external read on the first sender). The
fakes answer what the script reads and record what it sent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.unit.shell_support import REPO_ROOT, FakeBinaries, fake_binaries, posix, run_script

SCRIPT = REPO_ROOT / "scripts" / "verify_publications.sh"
HOST_LINES = (
    "verify-publications: scenario-004: ok: run run-1 attempt 1: log format 3, export format 3, "
    "41 events: both digests reproduced\n"
    "verify-publications: 30 of 30 replays reproduce\n"
)


@pytest.fixture
def sender(tmp_path: Path) -> tuple[FakeBinaries, dict[str, str]]:
    fakes = fake_binaries(tmp_path)
    env = fakes.environment(POLL_SECONDS="0", OUT_DIR=posix(tmp_path / "out"), AWS_PROFILE="fake")
    return fakes, env


def _answer(fakes: FakeBinaries, status: str, code: int, out: str, err: str = "") -> None:
    (fakes.fake_dir / "response-1.json").write_text(
        json.dumps({"Status": status, "Code": code, "Out": out, "Err": err})
    )


def _sent_command(fakes: FakeBinaries) -> str:
    payload = json.loads((fakes.fake_dir / "payload-1.json").read_text())
    (command,) = payload["commands"]
    return command


def test_a_reproduced_set_is_the_senders_success_with_the_hosts_lines_and_one_send(
    sender: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = sender
    _answer(fakes, "Success", 0, HOST_LINES)
    completed = run_script(SCRIPT, env)
    assert completed.returncode == 0, completed.stderr
    assert "instance i-fake\n" in completed.stdout
    assert completed.stdout.endswith(HOST_LINES)
    assert (fakes.fake_dir / "sends").read_text().strip() == "1"
    command = _sent_command(fakes)
    assert "cd /srv/app" in command and "export PGDATA_HOST=/srv/pgdata" in command
    assert "--name /leave-agent/postgres-password" in command
    assert 'export APP_TAG="${image##*:}"' in command
    assert command.rstrip().endswith(
        "docker compose run --rm app python -m leaveimpact.app verify-publications"
    )
    payload = json.loads((fakes.fake_dir / "payload-1.json").read_text())
    assert payload["executionTimeout"] == ["900"]


def test_a_failed_check_is_the_senders_failure_with_the_exit_code_named(
    sender: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = sender
    moved = HOST_LINES.replace("30 of 30", "29 of 30")
    _answer(fakes, "Failed", 1, moved, "compose: something\n")
    completed = run_script(SCRIPT, env)
    assert completed.returncode == 1
    assert "29 of 30 replays reproduce" in completed.stdout
    assert "(stderr) compose: something" in completed.stderr
    assert "the host's check exited 1" in completed.stderr


def test_a_success_status_with_a_nonzero_code_is_uncertain(
    sender: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = sender
    _answer(fakes, "Success", 3, "")
    completed = run_script(SCRIPT, env)
    assert completed.returncode == 2
    assert "Success with exit code 3" in completed.stderr


def test_the_poll_deadline_ends_the_send_uncertain(
    sender: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = sender
    (fakes.fake_dir / "pending-1").write_text("100000")
    completed = run_script(SCRIPT, {**env, "DEADLINE_SECONDS": "1"})
    assert completed.returncode == 2
    assert "passed its deadline" in completed.stderr
    assert len(fakes.lines("invocation 1")) >= 1


def test_polls_that_keep_failing_end_the_send_uncertain(
    sender: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = sender
    _answer(fakes, "Success", 0, HOST_LINES)
    completed = run_script(SCRIPT, {**env, "FAKE_INVOCATION_FAIL_AFTER": "0"})
    assert completed.returncode == 2
    assert "6 polls in a row failed" in completed.stderr
    assert "ExpiredToken" in completed.stderr


def test_no_running_host_ends_the_send_before_anything_is_sent(
    sender: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = sender
    completed = run_script(SCRIPT, {**env, "FAKE_NO_INSTANCE": "1"})
    assert completed.returncode == 2
    assert "no running app host" in completed.stderr
    assert not (fakes.fake_dir / "sends").exists()
