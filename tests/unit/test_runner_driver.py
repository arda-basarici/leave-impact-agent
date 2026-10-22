"""The runner-side driver under a fake ``aws`` and a fake ``gh``: the CI guard that reads
the dispatched commit's CI run before any send, the lifecycle's sends in the order the
launcher's ``status`` answers dictate, each payload carrying the step's exports and the
host script, the identities derived from the workflow run, the threshold amounts from the
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
REPOSITORY = "arda-basarici/leave-impact-agent"
CI_RUN, CI_ATTEMPT = 4242, 2
REQUIRED_JOBS = ("check", "sweeps", "crash-matrix", "image", "deploy")
GREEN: dict[str, tuple[str, str | None]] = {job: ("completed", "success") for job in REQUIRED_JOBS}

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
    "INPUT_APPROVAL": "human",
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


def _ci(
    fakes: FakeBinaries,
    jobs: dict[str, tuple[str, str | None]] = GREEN,
    *,
    runs: tuple[tuple[int, int, str, str], ...] = ((CI_RUN, CI_ATTEMPT, "push", "main"),),
) -> None:
    """What the fake Actions API answers: the CI workflow's runs at the dispatched sha (id,
    attempt, event, branch) and the latest attempt's jobs by name (status, conclusion)."""
    (fakes.fake_dir / "ci-runs.json").write_text(
        json.dumps(
            {
                "workflow_runs": [
                    {"id": run, "run_attempt": attempt, "event": event, "head_branch": branch}
                    for run, attempt, event, branch in runs
                ]
            }
        )
    )
    (fakes.fake_dir / "ci-jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {"name": name, "status": status, "conclusion": conclusion}
                    for name, (status, conclusion) in jobs.items()
                ]
            }
        )
    )


@pytest.fixture
def driver(tmp_path: Path, checkout: Path) -> tuple[FakeBinaries, dict[str, str]]:
    fakes = fake_binaries(tmp_path)
    _ci(fakes)
    env = fakes.environment(
        CHECKOUT=str(checkout),
        HOST_SCRIPT=posix(HOST_SCRIPT),
        GITHUB_SHA=SHA,
        GITHUB_REPOSITORY=REPOSITORY,
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
ADMITTED_WORLD = "5" * 64
ADMITTED_COMMIT = "a" * 40
ADMITTED = (
    f"world_version={ADMITTED_WORLD}\nregistration_commit={ADMITTED_COMMIT}\n"
    "ledger=ledger-development\n"
)
"""What status prints of the admission: the inventory's scope, which is the attempt's and
not the dispatch's inputs or the checkout's commit, and the ledger the attempt was
admitted against, which the host checks the job's ledger input against."""


def test_a_run_walks_launch_work_status_publish_inventory_and_reports_the_inventory(
    driver: tuple[FakeBinaries, dict[str, str]], tmp_path: Path
) -> None:
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        ("Success", 0, "worked=run-77/1\nending=closed\n"),
        ("Success", 0, "attempt=closed\n" + ADMITTED + "next=publish\n"),
        ("Success", 0, "publication=run-77/1\nstate=published\n"),
        ("Success", 0, "inventory_digest=" + "e" * 64 + "\n"),
    )
    status, out, err = _run(fakes, env, **RUN_INPUTS)
    assert status == 0, err
    # The CI guard read the run and its latest attempt before the first send.
    assert fakes.lines("gh api") == [
        f"gh api repos/{REPOSITORY}/actions/workflows/ci.yml/runs"
        f"?head_sha={SHA}&event=push&per_page=100",
        f"gh api repos/{REPOSITORY}/actions/runs/{CI_RUN}/jobs?filter=latest&per_page=100",
    ]
    jobs = " ".join(REQUIRED_JOBS)
    assert f"CI run {CI_RUN} attempt {CI_ATTEMPT} of {SHA}: {jobs} concluded success" in out
    assert _words(fakes) == ["launch", "work", "status", "publish", "inventory"]
    assert out.index("launch: sending") < out.index("launch: command"), (
        "the send is on the log before its response, for a reader of a lost one"
    )
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
    assert "RECOVERIES" not in fakes.payload_exports(3), "the count is the log's, not the job's"
    inventory = fakes.payload_exports(5)
    assert inventory["WORLD_VERSION"] == ADMITTED_WORLD != RUN_INPUTS["INPUT_WORLD_VERSION"]
    assert inventory["REGISTRATION_COMMIT"] == ADMITTED_COMMIT != _head(Path(env["CHECKOUT"]))
    assert inventory["LEDGER"] == "ledger-development"
    assert inventory["ADMITTED_LEDGER"] == "ledger-development", "status's line, for the host"
    payload = json.loads((fakes.fake_dir / "payload-1.json").read_text())
    assert payload["commands"][0].endswith(HOST_SCRIPT.read_text())
    assert payload["executionTimeout"] == ["3600"]
    assert "inventory: inventory_digest=" + "e" * 64 in out
    assert "inventory_digest=" + "e" * 64 in (tmp_path / "summary.md").read_text()


@pytest.mark.parametrize(
    ("jobs", "refused"),
    [
        ({**GREEN, "crash-matrix": ("in_progress", None)}, "crash-matrix=in_progress/null"),
        ({**GREEN, "image": ("completed", "failure")}, "image=completed/failure"),
        ({**GREEN, "sweeps": ("completed", "cancelled")}, "sweeps=completed/cancelled"),
        ({**GREEN, "deploy": ("completed", "skipped")}, "deploy=completed/skipped"),
        ({job: GREEN[job] for job in REQUIRED_JOBS if job != "check"}, "check=absent"),
        (
            {**GREEN, "sweeps": ("queued", None), "deploy": ("completed", "failure")},
            "sweeps=queued/null deploy=completed/failure",
        ),
    ],
    ids=["pending", "failed", "cancelled", "skipped", "absent", "two"],
)
def test_a_required_job_not_concluded_success_refuses_the_dispatch_before_any_send(
    driver: tuple[FakeBinaries, dict[str, str]],
    jobs: dict[str, tuple[str, str | None]],
    refused: str,
) -> None:
    """The freeze step's fork 10: a pending, failed, cancelled, skipped or absent required
    job of the deployed sha's CI run ends the job red naming the run, the attempt and each
    job's state, and nothing is sent to the host."""
    fakes, env = driver
    _ci(fakes, jobs)
    _script(fakes, LAUNCHED)
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 1
    assert (
        f"CI run {CI_RUN} attempt {CI_ATTEMPT} of {SHA} has required jobs not concluded "
        f"success: {refused}; nothing is dispatched"
    ) in out
    assert not (fakes.fake_dir / "sends").exists()


@pytest.mark.parametrize(
    ("runs", "message"),
    [
        ((), f"no push run of ci.yml on main built {SHA}; nothing is dispatched"),
        (
            ((CI_RUN, 1, "push", "feature"),),
            f"no push run of ci.yml on main built {SHA}; nothing is dispatched",
        ),
        (
            ((CI_RUN, 1, "push", "main"), (CI_RUN + 1, 1, "push", "main")),
            f"2 push runs of ci.yml on main built {SHA} ({CI_RUN} {CI_RUN + 1}); one is expected, "
            "nothing is dispatched",
        ),
    ],
    ids=["none", "another-branch", "two"],
)
def test_the_guard_wants_exactly_one_push_run_of_ci_on_main_for_the_sha(
    driver: tuple[FakeBinaries, dict[str, str]],
    runs: tuple[tuple[int, int, str, str], ...],
    message: str,
) -> None:
    fakes, env = driver
    _ci(fakes, runs=runs)
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 1
    assert message in out
    assert fakes.lines("gh api")[1:] == [] and not (fakes.fake_dir / "sends").exists()


def test_a_continuation_passes_the_guard_too(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """The continue-run workflow runs the same driver, so an attempt is continued only on a
    commit whose CI run is green."""
    fakes, env = driver
    _ci(fakes, {**GREEN, "image": ("completed", "failure")})
    status, out, _ = _run(fakes, env, **CONTINUE_INPUTS)
    assert status == 1 and "image=completed/failure" in out
    assert not (fakes.fake_dir / "sends").exists()


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


def test_the_recovery_count_is_read_from_the_status_output_and_a_hold_ends_the_job_red(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """The launcher counts the log's recoveries and answers hold at the bound; the driver
    sends no count of its own and prints the one it read (the step-14 review's finding)."""
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        OK,
        ("Success", 0, "recoveries=0\nnext=recover\n"),
        OK,
        ("Success", 0, "recoveries=1\nnext=recover\n"),
        OK,
        ("Success", 0, "recoveries=2\nnext=hold\n"),
    )
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 1
    assert _words(fakes) == ["launch", "work", "status", "work", "status", "work", "status"]
    assert all("RECOVERIES" not in fakes.payload_exports(n) for n in (3, 5, 7))
    assert "status: next=recover after 1 recoveries" in out
    assert "status: next=hold after 2 recoveries" in out
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
        ("Success", 0, ADMITTED + "next=publish\n"),
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
    assert (
        "work failed with exit status 2 (a configuration fault or an unexpected failure), "
        "which no re-send cures"
    ) in out


def test_a_refused_work_reads_the_state_since_a_receipt_path_refuses_too(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        ("Failed", 1, "refused=run-77/1\nreason=closed_already\n"),
        ("Success", 0, ADMITTED + "next=publish\n"),
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
    _script(fakes, LAUNCHED, OK, ("Success", 0, ADMITTED + "next=publish\n"), OK, OK)
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
        ("Success", 0, ADMITTED + "next=publish\n"),
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
        ("Success", 0, "container=none\n" + ADMITTED + "next=publish\n"),
        OK,
        OK,
    )
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "status", "status", "publish", "inventory"]
    assert out.count("work container is still running") == 2


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
        ("Success", 0, "container=none\n" + ADMITTED + "next=publish\n"),
        OK,
        OK,
    )
    status, _, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "work", "status", "publish", "inventory"]


def test_a_continuation_without_a_delivery_starts_at_the_state_and_publishes_a_closed_attempt(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """The job that closed the attempt ended before its publish (the fourth live dispatch):
    the continuation reads the state, finds it closed, and publishes and lists it."""
    fakes, env = driver
    _script(fakes, ("Success", 0, "container=none\n" + ADMITTED + "next=publish\n"), OK, OK)
    inputs = {**CONTINUE_INPUTS, "INPUT_PAYLOAD_DIGEST": ""}
    status, _, err = _run(fakes, env, **inputs)
    assert status == 0, err
    assert _words(fakes) == ["status", "publish", "inventory"]
    assert fakes.payload_exports(1)["APPROVAL"] == "human"
    # The continuation carries no world or commit input: the inventory's scope is what the
    # status printed of the admission (the step-14 review's finding).
    inventory = fakes.payload_exports(3)
    assert inventory["WORLD_VERSION"] == ADMITTED_WORLD
    assert inventory["REGISTRATION_COMMIT"] == ADMITTED_COMMIT != _head(Path(env["CHECKOUT"]))


def test_a_status_that_names_no_admission_ends_the_job_before_publish(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """Nothing is published whose inventory could not be scoped."""
    fakes, env = driver
    _script(fakes, LAUNCHED, OK, ("Success", 0, "next=publish\n"))
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 1
    assert _words(fakes) == ["launch", "work", "status"]
    assert "status printed no world version, registration commit or ledger" in out


def test_a_status_without_the_admitted_ledger_ends_the_job_before_publish(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """The scope alone is not enough: without the admitted ledger the host could not check
    the job's ledger input against the admission, so the job ends before publish."""
    fakes, env = driver
    without_ledger = ADMITTED.replace("ledger=ledger-development\n", "")
    assert without_ledger != ADMITTED
    scoped = ("Success", 0, "attempt=closed\n" + without_ledger + "next=publish\n")
    _script(fakes, LAUNCHED, OK, scoped)
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 1
    assert _words(fakes) == ["launch", "work", "status"]
    assert "status printed no world version, registration commit or ledger" in out


def test_a_work_process_the_host_killed_is_read_and_recovered_not_ended(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """Exit 137 is the container's memory limit, not the process's own code: the state is
    read, the launcher answers recover, and the walk goes on (the step's batch review)."""
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        ("Failed", 137, ""),
        ("Success", 0, "container=none\nnext=recover\n"),
        OK,
        ("Success", 0, "container=none\n" + ADMITTED + "next=publish\n"),
        OK,
        OK,
    )
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "work", "status", "publish", "inventory"]
    assert "status 137, which it does not choose for itself" in out


def test_a_continuation_carries_the_policy_the_attempt_was_dispatched_under(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """An automatic attempt continued from another job is recovered under its own policy,
    so its export never records a human approver it did not have."""
    fakes, env = driver
    _script(
        fakes,
        ("Success", 0, "container=none\nnext=work\n"),
        OK,
        ("Success", 0, "container=none\n" + ADMITTED + "next=publish\n"),
        OK,
        OK,
    )
    inputs = {**CONTINUE_INPUTS, "INPUT_PAYLOAD_DIGEST": "", "INPUT_APPROVAL": "automatic"}
    status, _, err = _run(fakes, env, **inputs)
    assert status == 0, err
    assert _words(fakes) == ["status", "work", "status", "publish", "inventory"]
    assert fakes.payload_exports(1)["APPROVAL"] == "automatic"
    assert fakes.payload_exports(2)["APPROVAL"] == "automatic"


def test_an_invocation_the_agent_has_not_reported_yet_is_waited_through(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(fakes, LAUNCHED, OK, ("Success", 0, ADMITTED + "next=publish\n"), OK, OK)
    (fakes.fake_dir / "missing-2").write_text("2")
    status, out, _ = _run(fakes, env, **RUN_INPUTS)
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "publish", "inventory"]
    polls = fakes.lines("invocation 2")
    assert len(polls) >= 4, "two not-yet-reported answers, the status, the read"
    assert "uncertain" not in out


def test_six_failed_polls_make_the_send_uncertain_and_an_unreadable_job_names_the_continuation(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """The deploy role's session expires under a long work send: every poll fails, the
    send is uncertain, the state read fails the same way, and the job ends red naming
    continue-run instead of spinning to the workflow's timeout."""
    fakes, env = driver
    _script(fakes, LAUNCHED, OK)
    status, out, _ = _run(fakes, env, **{**RUN_INPUTS, "FAKE_INVOCATION_FAIL_AFTER": "2"})
    assert status == 1
    assert _words(fakes) == ["launch", "work", "status"]
    assert "work: 6 polls in a row failed, the last: An error occurred (ExpiredTokenException)" in (
        out
    )
    assert "dispatch continue-run for run-77 attempt 1 with launch=launch-1" in out
    assert len(fakes.lines("invocation 2")) == 6 and len(fakes.lines("invocation 3")) == 6


def test_a_result_that_cannot_be_read_after_a_terminal_status_is_uncertain(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = driver
    _script(fakes, LAUNCHED, OK)
    status, out, _ = _run(fakes, env, **{**RUN_INPUTS, "FAKE_INVOCATION_FAIL_AFTER": "3"})
    assert status == 1
    assert _words(fakes) == ["launch", "work", "status"]
    assert "work: the command ended Success and its result could not be read" in out


def test_the_poll_is_bounded_by_the_execution_timeout_and_its_margin(
    driver: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """A command the agent never reports terminal is not polled forever: past the
    execution timeout plus the margin the send is uncertain and the state is read."""
    fakes, env = driver
    _script(
        fakes,
        LAUNCHED,
        OK,
        ("Success", 0, "container=none\n" + ADMITTED + "next=publish\n"),
        OK,
        OK,
    )
    (fakes.fake_dir / "pending-2").write_text("30")
    bounds = {"EXECUTION_TIMEOUT": "3", "POLL_MARGIN_SECONDS": "0", "POLL_SECONDS": "1"}
    status, out, _ = _run(fakes, env, **{**RUN_INPUTS, **bounds})
    assert status == 0
    assert _words(fakes) == ["launch", "work", "status", "publish", "inventory"]
    assert "work: the poll passed the execution timeout plus its margin" in out
    assert len(fakes.lines("invocation 2")) < 30


@pytest.mark.parametrize(
    ("inputs", "named"),
    [
        ({"INPUT_RUN_ID": "../../srv"}, "run_id"),
        ({"INPUT_ATTEMPT": "0"}, "attempt"),
        ({"INPUT_ATTEMPT": "two"}, "attempt"),
    ],
)
def test_a_continuation_with_a_malformed_id_ends_before_any_send(
    driver: tuple[FakeBinaries, dict[str, str]], inputs: dict[str, str], named: str
) -> None:
    fakes, env = driver
    status, out, _ = _run(fakes, env, **{**CONTINUE_INPUTS, **inputs})
    assert status == 2
    assert named in out
    assert not (fakes.fake_dir / "sends").exists(), "nothing was sent"
