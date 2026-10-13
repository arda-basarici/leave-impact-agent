"""The host-side lifecycle script under fake binaries: each lifecycle word composes the one
command line the docs promise, the launch writes the files the later words read back, the
dispatched commit must be the deployed one, a cleared run directory stops a later word, and
no secret ever reaches a command line (they reach the container's environment only)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.unit.shell_support import HOST_SCRIPT, FakeBinaries, fake_binaries, posix, run_script

SHA = "f" * 40
COMMIT = "c" * 40
WORLD = "7" * 64

LAUNCH_INPUTS = {
    "WORLD_VERSION": WORLD,
    "SCENARIO": "scn-development-3",
    "SYSTEM": "agent",
    "CONDITION": "normal",
    "LEVEL": "base",
    "REGISTRATION_COMMIT": COMMIT,
    "REQUEST_ID": "req-run-1-a1",
    "ADMITTER": "workflow:investigate",
    "AUTHORITY": "workflow:investigate",
    "LEDGER": "ledger-development",
    "THRESHOLD_PICO": "50000000000000",
    "LIMIT_PICO": "270000000000000",
    "FRAPPE_BASE_URL": "https://hr-w3.example.test",
    "JIRA_BASE_URL": "https://api.atlassian.com/ex/jira/cloud-id",
}


@pytest.fixture
def host(tmp_path: Path) -> tuple[FakeBinaries, dict[str, str]]:
    """The fakes and the environment of a host whose DEPLOYED is the dispatched sha."""
    fakes = fake_binaries(tmp_path)
    app_dir = tmp_path / "srv"
    app_dir.mkdir()
    (app_dir / "DEPLOYED").write_text(SHA + "\n")
    base = fakes.environment(
        APP_DIR=posix(app_dir),
        RUN_ROOT=posix(tmp_path / "run"),
        RUN_SHA=SHA,
        RUN_ID="run-1",
        ATTEMPT="1",
    )
    return fakes, base


def _run(fakes: FakeBinaries, env: dict[str, str], word: str, **step: str) -> tuple[int, str]:
    full = dict(env)
    full["LIFECYCLE_COMMAND"] = word
    full.update(step)
    completed = run_script(HOST_SCRIPT, full)
    return completed.returncode, completed.stderr


def _launched(fakes: FakeBinaries, env: dict[str, str], **overrides: str) -> None:
    status, err = _run(fakes, env, "launch", **{**LAUNCH_INPUTS, **overrides})
    assert status == 0, err


def test_launch_plans_receipts_the_threshold_and_admits_in_one_run_directory(
    host: tuple[FakeBinaries, dict[str, str]], tmp_path: Path
) -> None:
    fakes, env = host
    _launched(fakes, env)
    runs = fakes.lines("docker compose run")
    assert len(runs) == 3
    plan, threshold, admit = runs
    mount = f"-v {posix(tmp_path / 'run')}/run-1:/run/job"
    assert all(mount in line for line in runs)
    assert " python -m leaveimpact.launch plan " in plan
    for flag in (
        f"--world-version {WORLD}",
        "--scenario scn-development-3",
        "--system agent",
        "--registration /run/job/registration.json",
        f"--registration-commit {COMMIT}",
        "--prices /run/job/prices.json",
        "--region eu-central-1",
        "--run run-1 --attempt 1 --request-id req-run-1-a1 --admitter workflow:investigate",
        "--out /run/job/attempt-1",
        "--ledger ledger-development",
    ):
        assert flag in plan, flag
    assert (
        "leaveimpact.agent set-threshold --ledger ledger-development --amount 50000000000000 "
        "--authority workflow:investigate --registration-commit "
        + COMMIT
        + " --limit 270000000000000"
    ) in threshold
    assert (
        "leaveimpact.agent admit --registration /run/job/registration.json "
        "--request /run/job/attempt-1/request.json"
    ) in admit
    run_env = (tmp_path / "run" / "run-1" / "run.env").read_text()
    assert "SCENARIO=scn-development-3\n" in run_env
    assert "FRAPPE_BASE_URL=https://hr-w3.example.test\n" in run_env
    fetched = fakes.lines("curl ")
    assert len(fetched) == 2
    assert all(f"/{SHA}/preregistration/" in line for line in fetched)
    # The directory is handed to the image's user after the files are fetched and before
    # any container reads it: the first live dispatch failed on a root-only directory.
    log = fakes.log.read_text().splitlines()
    handover = log.index(f"chown -R 1000:1000 {posix(tmp_path / 'run')}/run-1")
    assert handover > log.index(fetched[1])
    assert handover < log.index(runs[0])


def test_rules_only_plans_against_no_ledger_and_sends_no_threshold(
    host: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = host
    _launched(fakes, env, SYSTEM="rules_only")
    runs = fakes.lines("docker compose run")
    assert len(runs) == 2
    assert "--ledger" not in runs[0]
    assert "set-threshold" not in " ".join(runs)
    assert " admit " in runs[1]


def test_a_dispatched_commit_other_than_the_deployed_one_is_refused_before_anything_runs(
    host: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = host
    status, err = _run(fakes, {**env, "RUN_SHA": "e" * 40}, "launch", **LAUNCH_INPUTS)
    assert status == 2
    assert f"the dispatched commit {'e' * 40} is not the deployed one {SHA}" in err
    assert fakes.lines("docker compose run") == [] and fakes.lines("curl ") == []


def test_work_hands_the_vendor_principals_to_the_container_environment_and_no_command_line(
    host: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = host
    _launched(fakes, env)
    status, err = _run(fakes, env, "work", LAUNCH="launch-fake", APPROVAL="human")
    assert status == 0, err
    work = fakes.lines("docker compose run")[3]
    assert re.search(r" --nonce nonce-[0-9a-f]{32} --launch launch-fake ", work)
    assert " --name lifecycle-run-1-a1 " in work
    assert "docker rm -f lifecycle-run-1-a1" in fakes.lines("docker rm")[0]
    assert (
        "--approval human --system agent --condition normal --level base --region eu-central-1"
        in work
    )
    assert "value-of-" not in fakes.log.read_text(), "a parameter's value reached a command line"
    handed = (fakes.fake_dir / "docker-env-4.txt").read_text()
    for variable, parameter in (
        ("LEAVE_IMPACT_FRAPPE_API_KEY", "frappe-api-key"),
        ("LEAVE_IMPACT_FRAPPE_API_SECRET", "frappe-api-secret"),
        ("LEAVE_IMPACT_JIRA_EMAIL", "jira-email"),
        ("LEAVE_IMPACT_JIRA_TOKEN", "jira-token"),
        ("LEAVE_IMPACT_GOOGLE_AUTHORIZED_USER_JSON", "google-authorized-user-json"),
        ("POSTGRES_PASSWORD", "postgres-password"),
    ):
        assert f"{variable}=value-of-/leave-agent/{parameter}\n" in handed
    assert "LEAVE_IMPACT_FRAPPE_BASE_URL=https://hr-w3.example.test\n" in handed
    assert f"APP_TAG={SHA}\n" in handed
    # The launch's containers read no vendor: the deploy's rule, kept here.
    assert "LEAVE_IMPACT_FRAPPE_API_KEY" not in (fakes.fake_dir / "docker-env-1.txt").read_text()
    assert fakes.lines("curl ") and len(fakes.lines("curl ")) == 2, (
        "a later word re-fetches nothing present"
    )


def test_a_parameter_still_holding_the_placeholder_fails_the_step(
    host: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = host
    _launched(fakes, env)
    status, err = _run(
        fakes,
        {**env, "FAKE_UNSET_PARAMETER": "/leave-agent/jira-token"},
        "work",
        LAUNCH="launch-fake",
        APPROVAL="automatic",
    )
    assert status == 1
    assert (
        "parameter /leave-agent/jira-token is not put: it still holds the UNSET placeholder" in err
    )
    assert len(fakes.lines("docker compose run")) == 3, "no work container ran"


def test_a_word_after_a_cleared_run_directory_stops_and_says_why(
    host: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = host
    status, err = _run(fakes, env, "status", RECOVERIES="0", APPROVAL="automatic")
    assert status == 2
    assert "holds no run.env: the host's tmpfs was cleared since the launch" in err
    assert fakes.lines("docker compose run") == []


@pytest.mark.parametrize(
    ("word", "step", "expected"),
    [
        (
            "status",
            {"RECOVERIES": "2", "APPROVAL": "automatic"},
            "python -m leaveimpact.launch status --run run-1 --attempt 1 "
            "--registration /run/job/registration.json --recoveries 2 --approval automatic",
        ),
        (
            "deliver",
            {"APPROVER": "github:arda", "PAYLOAD_DIGEST": "d" * 64},
            "python -m leaveimpact.agent deliver-approval "
            "--registration /run/job/registration.json "
            "--run run-1 --attempt 1 --approver github:arda --payload-digest " + "d" * 64,
        ),
        (
            "publish",
            {},
            "python -m leaveimpact.agent publish --registration /run/job/registration.json "
            "--run run-1 --attempt 1",
        ),
        (
            "inventory",
            {},
            "python -m leaveimpact.agent inventory --registration /run/job/registration.json "
            f"--world-version {WORLD} --registration-commit {COMMIT} --ledger ledger-development",
        ),
    ],
)
def test_each_later_word_composes_its_one_command(
    host: tuple[FakeBinaries, dict[str, str]], word: str, step: dict[str, str], expected: str
) -> None:
    fakes, env = host
    _launched(fakes, env)
    status, err = _run(fakes, env, word, **step)
    assert status == 0, err
    assert fakes.lines("docker compose run")[3].endswith(expected)


def test_the_python_exit_status_is_the_steps(host: tuple[FakeBinaries, dict[str, str]]) -> None:
    fakes, env = host
    _launched(fakes, env)
    status, _ = _run(fakes, {**env, "FAKE_DOCKER_EXIT": "1"}, "publish")
    assert status == 1


def test_an_unknown_word_is_refused(host: tuple[FakeBinaries, dict[str, str]]) -> None:
    fakes, env = host
    _launched(fakes, env)
    status, err = _run(fakes, env, "review-approval")
    assert status == 2
    assert "not review-approval" in err


def test_work_refuses_to_start_beside_the_attempts_running_container(
    host: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = host
    _launched(fakes, env)
    (fakes.fake_dir / "running.txt").write_text("lifecycle-run-1-a1\n")
    status, err = _run(fakes, env, "work", LAUNCH="launch-fake", APPROVAL="automatic")
    assert status == 4
    assert "a work container of this attempt is still running: lifecycle-run-1-a1" in err
    assert len(fakes.lines("docker compose run")) == 3, "no work container started"
    assert fakes.lines("docker rm") == []


def test_status_reports_the_attempts_container_before_the_launchers_answer(
    host: tuple[FakeBinaries, dict[str, str]],
) -> None:
    fakes, env = host
    _launched(fakes, env)
    (fakes.fake_dir / "status.txt").write_text("attempt=open\nnext=recover\n")
    line = {**env, "LIFECYCLE_COMMAND": "status", "RECOVERIES": "0", "APPROVAL": "automatic"}
    assert run_script(HOST_SCRIPT, line).stdout.splitlines() == [
        "container=none",
        "attempt=open",
        "next=recover",
    ]
    (fakes.fake_dir / "running.txt").write_text("lifecycle-run-1-a1\n")
    assert run_script(HOST_SCRIPT, line).stdout.splitlines()[0] == "container=running"


def test_a_failing_parameter_read_ends_the_step_with_the_clis_own_error(
    host: tuple[FakeBinaries, dict[str, str]],
) -> None:
    """Bash drops errexit inside a command substitution: without the explicit return the
    value came back empty with status 0 and the container refused with "is not set", the
    wrong cause (the step's batch review)."""
    fakes, env = host
    _launched(fakes, env)
    status, err = _run(
        fakes,
        {**env, "FAKE_PARAMETER_FAIL": "/leave-agent/jira-token"},
        "work",
        LAUNCH="launch-fake",
        APPROVAL="automatic",
    )
    assert status == 254
    assert "ThrottlingException" in err
    assert "is not set" not in err
    assert len(fakes.lines("docker compose run")) == 3, "no work container ran"


def test_a_transfer_that_died_mid_body_leaves_no_file_and_the_next_launch_fetches_it_whole(
    host: tuple[FakeBinaries, dict[str, str]], tmp_path: Path
) -> None:
    fakes, env = host
    failing = {**env, "FAKE_CURL_FAIL_ONCE": "1"}
    status, err = _run(fakes, failing, "launch", **LAUNCH_INPUTS)
    assert status == 18
    assert "fetching preregistration/registration.json at " + SHA + " failed (curl exit 18)" in err
    run_dir = tmp_path / "run" / "run-1"
    assert not (run_dir / "registration.json").exists()
    assert list(run_dir.glob("*.part")) == []
    assert fakes.lines("docker compose run") == []
    status, err = _run(fakes, failing, "launch", **LAUNCH_INPUTS)
    assert status == 0, err
    assert (run_dir / "registration.json").read_text().strip() == "{}"
    assert (run_dir / "prices.json").read_text().strip() == "{}"


def test_publish_after_a_cleared_run_directory_remakes_it_and_fetches_the_registration(
    host: tuple[FakeBinaries, dict[str, str]], tmp_path: Path
) -> None:
    """A reboot between an attempt's close and its publish: publish needs the registration
    and the two ids alone, so it is the one later word that recreates the directory."""
    fakes, env = host
    status, err = _run(fakes, env, "publish")
    assert status == 0, err
    run_dir = tmp_path / "run" / "run-1"
    assert (run_dir / "registration.json").exists() and (run_dir / "prices.json").exists()
    assert fakes.lines("chown") == [f"chown -R 1000:1000 {posix(run_dir)}"]
    assert fakes.lines("docker compose run")[0].endswith(
        "python -m leaveimpact.agent publish --registration /run/job/registration.json "
        "--run run-1 --attempt 1"
    )
    status, err = _run(fakes, env, "inventory")
    assert status == 2
    assert "holds no run.env" in err
