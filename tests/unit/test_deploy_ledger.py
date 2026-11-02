"""The deploy ledger under fake binaries (the M1 audit's F-012, built at M3 step 17): a
completed deploy opens a block with `started` and ends it with `deployed`, each line a UTC
stamp, the word and the sha and digest; the boundary probe, run after the deploy in the
same shell as the workflow's payload orders them, appends `probe pass` third; a failure
after the block opened ends it with `failed` naming the phase and the exit status, one
line per history (a parameter still holding its placeholder, a refused stop, a failed
bootstrap, a worker whose wait failed); a refused lock and a missing digest write nothing,
since the one never opened a block and the other failed before the lock; a ledger that
cannot be appended fails the deploy before any fetch. The probe alone: its handler is
installed before its first command, so every failure it can meet (the identity read, a
foreign role, the positive control, a truth bucket that is not refused or refused for
another reason, the temporary file) ends with exactly one `probe fail` line carrying the
status, no PASS printed, and the deploy's block before it intact; a `probe pass` that
cannot be appended fails the command before PASS prints."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.unit.shell_support import (
    DEPLOY_SCRIPT,
    PROBE_SCRIPT,
    FakeBinaries,
    fake_binaries,
    posix,
    run_script,
)
from tests.unit.test_instance_deploy import COMPOSE, DIGEST, SHA

STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z ")
STARTED = f"started sha={SHA} digest={DIGEST}"
DEPLOYED = f"deployed sha={SHA} digest={DIGEST}"
PROBE_PASS = f"probe pass sha={SHA}"
IDENTITY_READ = "aws sts get-caller-identity --region eu-central-1 --query Arn --output text"
WORLD = "leave-impact-world-445743457479"
TRUTH = "leave-impact-truth-445743457479"
PROBE_CALLS = [
    f"aws s3api list-objects-v2 --region eu-central-1 --bucket {WORLD} "
    "--prefix worlds/ --max-keys 1",
    f"aws s3api list-objects-v2 --region eu-central-1 --bucket {TRUTH} --max-keys 1",
    f"aws s3api get-object --region eu-central-1 --bucket {TRUTH} "
    "--key access-probe/read-denied-canary /dev/null",
]
FOREIGN_ROLE = "arn:aws:sts::445743457479:assumed-role/other/i-fake"


def ledger_of(app_dir: Path) -> list[str]:
    """The ledger's lines without their stamps, after each stamp is checked for its form."""
    path = app_dir / "DEPLOY_LEDGER"
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    for line in lines:
        assert STAMP.match(line), line
    return [STAMP.sub("", line) for line in lines]


def stamps_of(app_dir: Path) -> list[str]:
    return [line[:20] for line in (app_dir / "DEPLOY_LEDGER").read_text().splitlines()]


@pytest.fixture
def host(tmp_path: Path) -> tuple[FakeBinaries, dict[str, str], Path]:
    """A host running the current stack, deploying it again (the deploy suite's fixture,
    restated here so this module reads on its own)."""
    fakes = fake_binaries(tmp_path)
    app_dir = tmp_path / "srv"
    app_dir.mkdir()
    (app_dir / "compose.yaml").write_bytes(COMPOSE.read_bytes())
    env = fakes.environment(
        APP_DIR=posix(app_dir),
        DEPLOY_SHA=SHA,
        DEPLOY_DIGEST=DIGEST,
        FAKE_COMPOSE_SOURCE=posix(COMPOSE),
    )
    return fakes, env, app_dir


# --- the deploy's block ---------------------------------------------------------------


def test_a_completed_deploy_opens_a_block_with_started_and_ends_it_with_deployed(
    host: tuple[FakeBinaries, dict[str, str], Path],
) -> None:
    _, env, app_dir = host
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode == 0, completed.stderr
    assert ledger_of(app_dir) == [STARTED, DEPLOYED]
    first, second = stamps_of(app_dir)
    assert first <= second
    assert (app_dir / "DEPLOYED").read_text().strip() == SHA


def test_the_payload_in_the_workflows_order_appends_the_probes_pass_line_third(
    host: tuple[FakeBinaries, dict[str, str], Path], tmp_path: Path
) -> None:
    """The workflow sends the two scripts as consecutive commands of one shell script
    (`AWS-RunShellScript` joins them with newlines), the exports ahead of both; the probe
    inherits the deploy's shell, its directory and the lock, and its line closes the
    block the deploy opened."""
    fakes, env, app_dir = host
    del env["DEPLOY_SHA"], env["DEPLOY_DIGEST"]
    payload = "\n".join(
        [
            f"export DEPLOY_SHA={SHA}",
            f"export DEPLOY_DIGEST={DIGEST}",
            DEPLOY_SCRIPT.read_text(),
            PROBE_SCRIPT.read_text(),
        ]
    )
    script = tmp_path / "payload.sh"
    script.write_text(payload, newline="\n")
    completed = run_script(script, env)
    assert completed.returncode == 0, completed.stderr
    assert ledger_of(app_dir) == [STARTED, DEPLOYED, PROBE_PASS]
    assert stamps_of(app_dir) == sorted(stamps_of(app_dir))
    assert "boundary probe: PASS" in completed.stdout
    # The probe ran after the deploy's end: its first call follows the last docker line.
    log = fakes.log.read_text().splitlines()
    last_docker = max(index for index, line in enumerate(log) if line.startswith("docker "))
    assert log.index(IDENTITY_READ) > last_docker


@pytest.mark.parametrize(
    ("scripted", "phase"),
    [
        ({"FAKE_UNSET_PARAMETER": "/leave-agent/postgres-password"}, "before-stop"),
        ({"FAKE_DOCKER_FAIL_ON": "compose stop worker"}, "before-bootstrap"),
        ({"FAKE_DOCKER_FAIL_ON": "leaveimpact.cache"}, "after-bootstrap"),
        ({"FAKE_DOCKER_FAIL_ON": "wait-timeout 90 worker"}, "worker-started"),
    ],
    ids=["placeholder-parameter", "refused-stop", "failed-bootstrap", "worker-wait"],
)
def test_a_failure_after_the_block_opened_ends_it_with_failed_and_its_phase(
    host: tuple[FakeBinaries, dict[str, str], Path], scripted: dict[str, str], phase: str
) -> None:
    _, env, app_dir = host
    env.update(scripted)
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode == 1
    assert ledger_of(app_dir) == [STARTED, f"failed sha={SHA} phase={phase} exit=1"]
    assert "could not take the failed line" not in completed.stderr


@pytest.mark.parametrize("history", ["refused-lock", "no-digest"])
def test_a_refused_lock_and_a_missing_digest_write_nothing(
    host: tuple[FakeBinaries, dict[str, str], Path], history: str
) -> None:
    """A refused lock never opened a block, and another deploy owns the ledger; a missing
    digest is refused before the lock is taken."""
    fakes, env, app_dir = host
    if history == "refused-lock":
        env["FAKE_FLOCK_HELD"] = "1"
    else:
        del env["DEPLOY_DIGEST"]
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode != 0
    assert not (app_dir / "DEPLOY_LEDGER").exists()
    assert fakes.lines("curl ") == []


def test_a_ledger_that_cannot_be_appended_fails_the_deploy_before_any_fetch(
    host: tuple[FakeBinaries, dict[str, str], Path],
) -> None:
    fakes, env, app_dir = host
    (app_dir / "DEPLOY_LEDGER").mkdir()
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode != 0
    assert fakes.lines("curl ") == []
    assert fakes.lines("docker ") == []
    assert not (app_dir / "DEPLOYED").exists()


# --- the probe's line -----------------------------------------------------------------


@pytest.fixture
def probed(tmp_path: Path) -> tuple[FakeBinaries, dict[str, str], Path]:
    """A host whose ledger holds a completed deploy's block, the probe about to run under
    the payload's exports."""
    fakes = fake_binaries(tmp_path)
    app_dir = tmp_path / "srv"
    app_dir.mkdir()
    (app_dir / "DEPLOY_LEDGER").write_text(
        f"2026-11-02T10:00:00Z {STARTED}\n2026-11-02T10:02:00Z {DEPLOYED}\n", newline="\n"
    )
    env = fakes.environment(APP_DIR=posix(app_dir), DEPLOY_SHA=SHA)
    return fakes, env, app_dir


def test_a_passing_probe_appends_its_pass_line_to_the_block(
    probed: tuple[FakeBinaries, dict[str, str], Path],
) -> None:
    fakes, env, app_dir = probed
    completed = run_script(PROBE_SCRIPT, env)
    assert completed.returncode == 0, completed.stderr
    assert ledger_of(app_dir) == [STARTED, DEPLOYED, PROBE_PASS]
    assert "boundary probe: PASS" in completed.stdout
    assert [line for line in fakes.lines("aws ") if "s3api" in line] == PROBE_CALLS


@pytest.mark.parametrize(
    ("scripted", "exit_status", "said"),
    [
        ({"FAKE_STS_FAIL": "1"}, 254, ""),
        ({"FAKE_STS_ARN": FOREIGN_ROLE}, 1, "not the instance role"),
        ({"FAKE_S3_FAIL_ON": "world"}, 254, ""),
        ({"FAKE_S3_ALLOW_ON": "truth"}, 1, "NOT refused"),
        ({"FAKE_S3_FAIL_ON": "truth"}, 1, "refused for another reason than AccessDenied"),
        ({"FAKE_MKTEMP_FAIL": "1"}, 1, ""),
    ],
    ids=[
        "identity-read",
        "foreign-role",
        "positive-control",
        "not-refused",
        "other-reason",
        "mktemp",
    ],
)
def test_every_failure_the_probe_can_meet_writes_exactly_one_fail_line(
    probed: tuple[FakeBinaries, dict[str, str], Path],
    scripted: dict[str, str],
    exit_status: int,
    said: str,
) -> None:
    """The handler is installed before the first command that can fail: the identity read
    and the positive control precede the temporary file, where the handler used to be
    installed, and a failure there would have reached the deploy's handler instead."""
    fakes, env, app_dir = probed
    env.update(scripted)
    if "FAKE_MKTEMP_FAIL" in scripted:
        fake = fakes.bin_dir / "mktemp"
        fake.write_text("#!/usr/bin/env bash\nexit 1\n", newline="\n")
        fake.chmod(0o755)
    completed = run_script(PROBE_SCRIPT, env)
    assert completed.returncode == exit_status
    assert ledger_of(app_dir) == [STARTED, DEPLOYED, f"probe fail sha={SHA} exit={exit_status}"]
    assert "PASS" not in completed.stdout
    assert said in completed.stdout


def test_a_pass_line_that_cannot_be_appended_fails_the_probe_before_pass_prints(
    tmp_path: Path,
) -> None:
    fakes = fake_binaries(tmp_path)
    app_dir = tmp_path / "srv"
    app_dir.mkdir()
    (app_dir / "DEPLOY_LEDGER").mkdir()
    env = fakes.environment(APP_DIR=posix(app_dir), DEPLOY_SHA=SHA)
    completed = run_script(PROBE_SCRIPT, env)
    assert completed.returncode != 0
    assert "PASS" not in completed.stdout
    assert "could not take the probe's fail line" in completed.stderr
