"""The runner-side driver under a fake ``aws``: the lifecycle's sends in the order the
launcher's ``status`` answers dictate, each payload carrying the step's exports and the host
script, the identities derived from the workflow run, the threshold amounts from the
registration's own budget, and the ends the walk can reach (published, waiting, held, a
fault no re-send cures, an uncertain completion read before any re-send)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit.shell_support import (
    DRIVER_SCRIPT,
    HOST_SCRIPT,
    REPO_ROOT,
    FakeBinaries,
    fake_binaries,
    posix,
    run_script,
)

SHA = "a" * 40
REGISTRATION = REPO_ROOT / "preregistration" / "registration.json"

RUN_INPUTS = {
    "MODE": "run",
    "INPUT_WORLD_VERSION": "7" * 64,
    "INPUT_SCENARIO": "scn-development-3",
    "INPUT_SYSTEM": "agent",
    "INPUT_CONDITION": "normal",
    "INPUT_LEVEL": "base",
    "INPUT_APPROVAL": "automatic",
    "INPUT_FRAPPE_BASE_URL": "https://hr-w3.example.test",
    "INPUT_JIRA_BASE_URL": "https://api.atlassian.com/ex/jira/cloud-id",
}
CONTINUE_INPUTS = {
    "MODE": "continue",
    "INPUT_RUN_ID": "run-9",
    "INPUT_ATTEMPT": "2",
    "INPUT_LAUNCH": "launch-earlier",
    "INPUT_PAYLOAD_DIGEST": "d" * 64,
}


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """A throwaway repository holding the registration file in one commit: the driver
    cites the file's commit from the checkout it runs in, so the test owns that history
    instead of leaning on this repository's."""
    root = tmp_path / "checkout"
    (root / "preregistration").mkdir(parents=True)
    shutil.copy(REGISTRATION, root / "preregistration" / "registration.json")
    git = ["git", "-c", "user.name=test", "-c", "user.email=test@example.test"]
    subprocess.run([*git, "init", "-q"], cwd=root, check=True)
    subprocess.run([*git, "add", "."], cwd=root, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "the registration"], cwd=root, check=True)
    return root


def _head(checkout: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=checkout, capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def driver(tmp_path: Path, checkout: Path) -> tuple[FakeBinaries, dict[str, str]]:
    fakes = fake_binaries(tmp_path)
    env = fakes.environment(
        CHECKOUT=str(checkout),
        HOST_SCRIPT=posix(HOST_SCRIPT),
        GITHUB_SHA=SHA,
        GITHUB_RUN_ID="77",
        GITHUB_RUN_ATTEMPT="1",
        GITHUB_ACTOR="arda",
        LEDGER="ledger-development",
        RUNNER_TEMP=posix(tmp_path / "runner"),
        GITHUB_STEP_SUMMARY=posix(tmp_path / "summary.md"),
        POLL_SECONDS="0",
    )
    (tmp_path / "runner").mkdir()
    return fakes, env


def _script(fakes: FakeBinaries, *responses: tuple[str, int, str]) -> None:
    """The invocation reads the fake answers, one per send in order: status, exit code, output."""
    for n, (status, code, out) in enumerate(responses, start=1):
        (fakes.fake_dir / f"response-{n}.json").write_text(
            json.dumps({"Status": status, "Code": code, "Out": out, "Err": ""})
        )


def _words(fakes: FakeBinaries) -> list[str]:
    sends = int((fakes.fake_dir / "sends").read_text())
    return [fakes.payload_exports(n)["LIFECYCLE_COMMAND"] for n in range(1, sends + 1)]


def _run(fakes: FakeBinaries, env: dict[str, str], **inputs: str) -> tuple[int, str, str]:
    completed = run_script(DRIVER_SCRIPT, {**env, **inputs}, cwd=Path(env["CHECKOUT"]))
    return completed.returncode, completed.stdout, completed.stderr


OK = ("Success", 0, "")
LAUNCHED = ("Success", 0, "launch=launch-1\nrun=run-77\nreservation_pico_usd=3253360000000\n")


def test_a_run_walks_launch_work_status_publish_inventory_and_reports_the_inventory(
    driver: tuple[FakeBinaries, dict[str, str]], tmp_path: Path
) -> None:
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        ("Success", 0, "worked=run-77/1\nending=closed\n"),
        ("Success", 0, "attempt=closed\nnext=publish\n"),
        ("Success", 0, "publication=run-77/1\nstate=published\n"),
        ("Success", 0, "inventory_digest=" + "e" * 64 + "\n"),
    )
    status, out, err = _run(fakes, env, **RUN_INPUTS)
    assert status == 0, err
    assert _words(fakes) == ["launch", "work", "status", "publish", "inventory"]
    launch = fakes.payload_exports(1)
    budget = json.loads(REGISTRATION.read_text())["budget"]
    assert launch["RUN_SHA"] == SHA
    assert launch["RUN_ID"] == "run-77" and launch["ATTEMPT"] == "1"
    assert launch["REQUEST_ID"] == "req-run-77-a1"
    assert launch["THRESHOLD_PICO"] == str(budget["admission_threshold_usd"] * 10**12)
    assert launch["LIMIT_PICO"] == str(budget["admission_threshold_limit_usd"] * 10**12)
    assert (
        launch["ADMITTER"] == "workflow:investigate"
        and launch["AUTHORITY"] == "workflow:investigate"
    )
    assert launch["REGISTRATION_COMMIT"] == _head(Path(env["CHECKOUT"]))
    assert launch["SCENARIO"] == "scn-development-3"
    assert launch["FRAPPE_BASE_URL"] == "https://hr-w3.example.test"
    work = fakes.payload_exports(2)
    assert work["LAUNCH"] == "launch-1" and work["APPROVAL"] == "automatic"
    assert fakes.payload_exports(3)["RECOVERIES"] == "0"
    payload = json.loads((fakes.fake_dir / "payload-1.json").read_text())
    assert payload["commands"][0].endswith(HOST_SCRIPT.read_text())
    assert payload["executionTimeout"] == ["3600"]
    assert "inventory: inventory_digest=" + "e" * 64 in out
    assert "inventory_digest=" + "e" * 64 in (tmp_path / "summary.md").read_text()


def test_a_human_pause_ends_the_job_green_and_names_the_launch_for_the_continue_dispatch(
    driver: tuple[FakeBinaries, dict[str, str]], tmp_path: Path
) -> None:
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        ("Success", 0, "worked=run-77/1\nending=paused\n"),
        ("Success", 0, "next=wait\n"),
    )
    status, out, _ = _run(fakes, env, **{**RUN_INPUTS, "INPUT_APPROVAL": "human"})
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status"]
    assert fakes.payload_exports(3)["APPROVAL"] == "human"
    assert "waits for a human" in out
    assert "continue-run with launch=launch-1" in (tmp_path / "summary.md").read_text()


def test_recoveries_are_counted_to_the_status_command_and_a_hold_ends_the_job_red(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        OK,
        ("Success", 0, "next=recover\n"),
        OK,
        ("Success", 0, "next=recover\n"),
        OK,
        ("Success", 0, "next=hold\n"),
    )
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 1
    assert _words(fakes) == ["launch", "work", "status", "work", "status", "work", "status"]
    assert [fakes.payload_exports(n)["RECOVERIES"] for n in (3, 5, 7)] == ["0", "1", "2"]
    assert "held past the recovery bound" in out


def test_an_uncertain_completion_is_read_before_any_re_send(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        ("TimedOut", 0, ""),
        ("Success", 0, "next=recover\n"),
        OK,
        ("Success", 0, "next=publish\n"),
        OK,
        OK,
    )
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "work", "status", "publish", "inventory"]
    assert "the transport reported TimedOut; the state is read before anything is re-sent" in out


def test_a_work_process_that_exited_with_a_fault_ends_the_job_without_a_status_read(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(fakes, LAUNCHED, ("Failed", 2, ""))
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 1
    assert _words(fakes) == ["launch", "work"]
    assert "work failed with exit status 2, which no re-send cures" in out


def test_a_refused_work_reads_the_state_since_a_receipt_path_refuses_too(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        ("Failed", 1, "refused=run-77/1\nreason=closed_already\n"),
        ("Success", 0, "next=publish\n"),
        OK,
        OK,
    )
    status, _, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "publish", "inventory"]


def test_work_sends_are_bounded_when_the_state_never_progresses(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    never = ("Success", 0, "next=work\n")
    _script(fakes, LAUNCHED, OK, never, OK, never, OK, never, OK, never)
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 1
    assert _words(fakes).count("work") == 4
    assert "did not progress after 4 work sends" in out


def test_a_failed_launch_ends_the_job_at_once(driver: tuple[FakeBinaries, dict[str, str]]) -> None:
    fakes, env = driver
    _script(fakes, ("Failed", 1, "refused=run-77/1\nreason=over the threshold\n"))
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 1
    assert _words(fakes) == ["launch"]
    assert "launch: reason=over the threshold" in out


def test_a_pending_command_is_polled_and_never_re_sent(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(fakes, LAUNCHED, OK, ("Success", 0, "next=publish\n"), OK, OK)
    (fakes.fake_dir / "pending-2").write_text("3")
    status, _, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "publish", "inventory"]
    polls = [line for line in fakes.lines("invocation 2")]
    assert len(polls) >= 5, "three InProgress answers, the terminal status, the full read"


def test_an_approval_delivers_then_continues_from_the_state_under_the_human_policy(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(
        fakes,
        ("Success", 0, "approved=run-9/2\nposition=7\n"),
        ("Success", 0, "next=work\n"),
        OK,
        ("Success", 0, "next=publish\n"),
        OK,
        OK,
    )
    status, _, err = _run(fakes, env, **CONTINUE_INPUTS)
    assert status == 0, err
    assert _words(fakes) == ["deliver", "status", "work", "status", "publish", "inventory"]
    deliver = fakes.payload_exports(1)
    assert deliver["RUN_ID"] == "run-9" and deliver["ATTEMPT"] == "2"
    assert deliver["APPROVER"] == "github:arda" and deliver["PAYLOAD_DIGEST"] == "d" * 64
    assert fakes.payload_exports(2)["APPROVAL"] == "human"
    assert fakes.payload_exports(3)["LAUNCH"] == "launch-earlier"


def test_no_running_instance_ends_the_job_before_any_send(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    status, out, _ = _run(fakes, env, **{**RUN_INPUTS, "FAKE_NO_INSTANCE": "1"})
    assert status == 1
    assert "no running leave-agent-app instance" in out
    assert not (fakes.fake_dir / "sends").exists()


def test_a_running_container_after_an_uncertain_completion_is_read_again_and_never_re_sent(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        ("TimedOut", 137, ""),
        ("Success", 0, "container=running\nnext=recover\n"),
        ("Success", 0, "container=running\nnext=recover\n"),
        ("Success", 0, "container=none\nnext=publish\n"),
        OK,
        OK,
    )
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "status", "status", "publish", "inventory"]
    assert out.count("work container is still running") == 2
    assert [fakes.payload_exports(n)["RECOVERIES"] for n in (3, 4, 5)] == ["0", "0", "0"]


def test_a_work_the_host_refused_beside_a_running_container_is_not_a_counted_send(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        ("Failed", 4, ""),
        ("Success", 0, "container=none\nnext=recover\n"),
        OK,
        ("Success", 0, "container=none\nnext=publish\n"),
        OK,
        OK,
    )
    status, _, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "work", "status", "publish", "inventory"]
    assert fakes.payload_exports(5)["RECOVERIES"] == "1"


def test_a_continuation_without_a_delivery_starts_at_the_state_and_publishes_a_closed_attempt(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """The job that closed the attempt ended before its publish (the fourth live dispatch):
    the continuation reads the state, finds it closed, and publishes and lists it."""
    fakes, env = driver
    _script(fakes, ("Success", 0, "container=none\nnext=publish\n"), OK, OK)
    inputs = {**CONTINUE_INPUTS, "INPUT_PAYLOAD_DIGEST": ""}
    status, _, err = _run(fakes, env, **inputs)
    assert status == 0, err
    assert _words(fakes) == ["status", "publish", "inventory"]
    assert fakes.payload_exports(1)["APPROVAL"] == "human"
