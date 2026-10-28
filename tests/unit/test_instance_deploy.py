"""The deploy script under fake binaries: the app image pulled by the digest CI recorded and
given the commit's tag, the service image pulled by compose, the secrets reaching the
containers' environment and never a command line, the two named checks (the identity
command as the image check, the readiness route read after `up --wait` as the readiness
check) with the deployed sha written last and only after both, and the refusals: before
any pull (no digest, a parameter still holding its placeholder), and after the service
started (a service that is not ready, a container answering with another revision), each
leaving no DEPLOYED marker. Since the worker service's step: the worker drained under the
installed definition after the pulls and the parameter reads, and started last under the
target's, after the app serves, each only when that file names the service (a fresh
host stops nothing; a rollback to a release before the worker starts none); its vendor
principals and the two base URLs in the environment `compose up` reads; the trap's
branches on a failure after the stop, after a bootstrap and after the worker's own
start; a UTC stamp per phase; and the base URLs held equal to the demo configuration
and the investigate workflow's default."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.unit.shell_support import DEPLOY_SCRIPT, FakeBinaries, fake_binaries, posix, run_script

SHA = "f" * 40
DIGEST = "sha256:" + "d" * 64
IMAGE = "ghcr.io/arda-basarici/leave-impact-agent"
COMPOSE = DEPLOY_SCRIPT.parents[2] / "compose.yaml"
PRE_WORKER_COMPOSE = """name: leaveimpact
services:
  app:
    image: ghcr.io/arda-basarici/leave-impact-agent:${APP_TAG:-latest}
  postgres:
    image: postgres
"""
"""A release before the worker service (the shape of `c0256f4`'s file): what a rollback
targets, and what a host ran before this step's first deploy."""
WORKER_UP = "docker compose up -d --wait --wait-timeout 90 worker"


@pytest.fixture
def host(tmp_path: Path) -> tuple[FakeBinaries, dict[str, str], Path]:
    """A host running the current stack (the tree's compose file installed), deploying the
    current stack again; the tests of other histories change the two files."""
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


def test_the_image_is_pulled_by_its_digest_and_tagged_before_compose_runs_anything(
    host: tuple[FakeBinaries, dict[str, str], Path],
) -> None:
    """The freeze step, fork 10 with fork 32's split: the tag is a label, the digest is the
    identity, so the deploy pulls the digest the image job recorded and compose finds the
    sha tag present; the service image is pulled by compose under its own pinned tag."""
    fakes, env, app_dir = host
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode == 0, completed.stderr
    docker = fakes.lines("docker ")
    assert docker[:6] == [
        f"docker pull --quiet {IMAGE}@{DIGEST}",
        f"docker tag {IMAGE}@{DIGEST} {IMAGE}:{SHA}",
        "docker compose -f compose.yaml.next pull --quiet postgres",
        "docker compose -f compose.yaml.next up -d --wait postgres",
        "docker compose config --services",
        "docker compose stop worker",
    ]
    assert "docker compose pull --quiet\n" not in "\n".join(docker) + "\n"
    assert [line for line in docker if "compose run" in line] == [
        "docker compose run --rm app python -m leaveimpact.cache",
        "docker compose run --rm app python -m leaveimpact.agent bootstrap-log",
        "docker compose run --rm app python -m leaveimpact.app bootstrap",
        "docker compose run --rm app python -m leaveimpact identity",
    ]
    # The service after the cache and the log are prepared, readiness read through the
    # bounded wait and then once more as the printed evidence.
    service = [line for line in docker if line.endswith(" app") or " exec -T app " in line]
    assert service[0] == "docker compose up -d --wait --wait-timeout 120 app"
    assert service[1].startswith("docker compose exec -T app python -c ") and "/ready" in service[1]
    # The worker last, after the readiness read and the target's own service list, and
    # nothing of it before the stop; the installed file replaced by the target's after
    # the drain (the file on disk is the target's at the end).
    worker_up = WORKER_UP
    assert docker.index(worker_up) > docker.index(service[1])
    assert docker[docker.index(worker_up) - 1] == "docker compose config --services"
    assert [line for line in docker if line.endswith(" worker")] == [
        "docker compose stop worker",
        worker_up,
    ]
    assert (app_dir / "compose.yaml").read_bytes() == COMPOSE.read_bytes()
    assert not (app_dir / "compose.yaml.next").exists()
    assert f"identity: leaveimpact {SHA}: the demo surface's image" in completed.stdout
    assert f'ready: {{"ready":true,"code_version":"{SHA}"' in completed.stdout
    assert (app_dir / "DEPLOYED").read_text() == SHA + "\n"
    assert f"deployed {SHA} ({DIGEST}) at " in completed.stdout
    # The compose file of the commit, fetched by sha into the app directory.
    assert fakes.lines("curl") == [
        "curl -fsSL https://raw.githubusercontent.com/arda-basarici/leave-impact-agent/"
        f"{SHA}/compose.yaml -o compose.yaml.next"
    ]
    # Every container saw the tag, the bucket and the password in its environment, and no
    # command line carried the password. The fake numbers every docker invocation, so the
    # containers' environments are the ones at the four `compose run` positions.
    runs = [n for n, line in enumerate(docker, start=1) if "compose run" in line]
    assert len(runs) == 4
    for n in runs:
        held = (fakes.fake_dir / f"docker-env-{n}.txt").read_text()
        assert f"APP_TAG={SHA}" in held
        assert "LEAVE_IMPACT_WORLD_BUCKET=leave-impact-world-445743457479" in held
        assert "LEAVE_IMPACT_AWS_REGION=eu-central-1" in held
        assert "POSTGRES_PASSWORD=value-of-/leave-agent/postgres-password" in held
    assert "value-of-" not in "\n".join(docker)
    # The worker's `up` saw the five principals and the two base URLs; no command line did.
    handed = (fakes.fake_dir / f"docker-env-{docker.index(worker_up) + 1}.txt").read_text()
    for variable, parameter in (
        ("LEAVE_IMPACT_FRAPPE_API_KEY", "frappe-api-key"),
        ("LEAVE_IMPACT_FRAPPE_API_SECRET", "frappe-api-secret"),
        ("LEAVE_IMPACT_JIRA_EMAIL", "jira-email"),
        ("LEAVE_IMPACT_JIRA_TOKEN", "jira-token"),
        ("LEAVE_IMPACT_GOOGLE_AUTHORIZED_USER_JSON", "google-authorized-user-json"),
    ):
        assert f"{variable}=value-of-/leave-agent/{parameter}\n" in handed
    assert "LEAVE_IMPACT_FRAPPE_BASE_URL=https://hr-w3.ardabasarici.dev\n" in handed
    assert "LEAVE_IMPACT_JIRA_BASE_URL=https://api.atlassian.com/ex/jira/" in handed
    # A UTC stamp per phase, in the deploy's order, so a slow deploy says where it was slow.
    stamps = re.findall(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z (.*)$", completed.stdout, re.MULTILINE
    )
    assert stamps == [
        f"fetched compose.yaml of {SHA}",
        "parameters read",
        "images pulled, postgres up",
        "worker stopped",
        "cache loaded",
        "log bootstrapped",
        "app bootstrapped",
        "app ready",
        "worker up",
    ]
    assert "deploy failed" not in completed.stderr


def test_the_host_lock_is_taken_first_and_a_held_lock_refuses_before_any_fetch_or_pull(
    host: tuple[FakeBinaries, dict[str, str], Path],
) -> None:
    """The worker service's step: one deploy on the host at a time, the second layer under
    the workflow's concurrency group. The lock is the script's first recorded action, on a
    descriptor over the app directory's lock file; a held lock (``flock -n``'s exit 1,
    scripted) refuses with one sentence before the compose file is fetched or an image
    pulled, and leaves no marker."""
    fakes, env, app_dir = host
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode == 0, completed.stderr
    assert fakes.log.read_text().splitlines()[0] == "flock -n 9"
    assert (app_dir / "deploy.lock").exists()
    (app_dir / "second").mkdir()
    held = fake_binaries(app_dir / "second")
    held_env = held.environment(
        APP_DIR=posix(app_dir), DEPLOY_SHA=SHA, DEPLOY_DIGEST=DIGEST, FAKE_FLOCK_HELD="1"
    )
    (app_dir / "DEPLOYED").unlink()
    completed = run_script(DEPLOY_SCRIPT, held_env)
    assert completed.returncode == 1
    assert f"another deploy holds {posix(app_dir)}/deploy.lock; this one is refused" in (
        completed.stderr
    )
    assert held.lines("docker") == [] and held.lines("curl") == []
    assert not (app_dir / "DEPLOYED").exists()


def test_no_digest_refuses_the_deploy_before_any_pull(
    host: tuple[FakeBinaries, dict[str, str], Path],
) -> None:
    fakes, env, _ = host
    del env["DEPLOY_DIGEST"]
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode != 0
    assert "the manifest digest CI recorded for the image of that commit" in completed.stderr
    assert fakes.lines("docker") == [] and fakes.lines("curl") == []


def test_a_parameter_still_holding_its_placeholder_fails_the_deploy_before_any_pull(
    host: tuple[FakeBinaries, dict[str, str], Path],
) -> None:
    fakes, env, _ = host
    env["FAKE_UNSET_PARAMETER"] = "/leave-agent/postgres-password"
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode != 0
    assert "parameter /leave-agent/postgres-password is not put" in completed.stderr
    assert fakes.lines("docker") == []


@pytest.mark.parametrize(
    ("scripted", "stage"),
    [
        ({"FAKE_IDENTITY_SHA": "e" * 40}, "identity"),
        ({"FAKE_READY": "false"}, "ready"),
        ({"FAKE_READY_SHA": "e" * 40}, "ready"),
    ],
)
def test_a_failed_check_leaves_no_deployed_marker(
    host: tuple[FakeBinaries, dict[str, str], Path], scripted: dict[str, str], stage: str
) -> None:
    """A stale image answering the identity command, a service that is not ready, or a
    container answering the readiness route with another revision: the deploy fails after
    that check, writes no DEPLOYED and claims no deploy, so a failed readiness keeps the
    previous marker and a rollback is the script with the older sha."""
    fakes, env, app_dir = host
    env.update(scripted)
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode != 0
    assert not (app_dir / "DEPLOYED").exists()
    assert "deployed " not in completed.stdout
    docker = fakes.lines("docker ")
    started = any(line == "docker compose up -d --wait --wait-timeout 120 app" for line in docker)
    assert started == (stage == "ready")
    # The trap's after-bootstrap branch: the worker stays stopped and the state is said,
    # with the rerun line; nothing starts the previous worker under an advanced schema.
    assert "deploy failed after a bootstrap" in completed.stderr
    assert "the worker stays stopped until a deploy succeeds" in completed.stderr
    assert f"DEPLOY_SHA={SHA} DEPLOY_DIGEST={DIGEST}" in completed.stderr
    assert "docker compose start worker" not in docker
    assert WORKER_UP not in docker


def test_a_refused_stop_starts_the_previous_worker_again_and_runs_no_bootstrap(
    host: tuple[FakeBinaries, dict[str, str], Path],
) -> None:
    """The trap's before-bootstrap branch: the window between the drain and the first
    bootstrap holds only the stop and the file's replacement, since the pulls and every
    parameter read come before it; a stop the daemon refused leaves the worker under the
    schema it ran under, so it is started again (under the installed file, still in
    place) and the deploy fails with no bootstrap run and no marker."""
    fakes, env, app_dir = host
    env["FAKE_DOCKER_FAIL_ON"] = "compose stop worker"
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode == 1
    assert "deploy failed before the bootstraps (exit 1)" in completed.stderr
    docker = fakes.lines("docker ")
    assert docker[-2:] == ["docker compose stop worker", "docker compose start worker"]
    assert not any("compose run" in line for line in docker)
    assert not (app_dir / "DEPLOYED").exists()
    assert (app_dir / "compose.yaml.next").exists(), "the installed file was not replaced"


def test_a_fresh_host_stops_nothing_and_starts_the_worker_the_target_names(
    host: tuple[FakeBinaries, dict[str, str], Path],
) -> None:
    """No installed file (a fresh host) or one naming no worker (a host before this step):
    the drain is skipped and said, the worker is started from the target, and a failure
    after a bootstrap reports that no worker was running rather than a stopped one."""
    fakes, env, app_dir = host
    (app_dir / "compose.yaml").unlink()
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode == 0, completed.stderr
    docker = fakes.lines("docker ")
    assert "docker compose stop worker" not in docker
    assert WORKER_UP in docker
    assert "no installed worker to stop" in completed.stdout
    assert (app_dir / "DEPLOYED").exists()
    (app_dir / "DEPLOYED").unlink()
    (app_dir / "compose.yaml").write_text(PRE_WORKER_COMPOSE)
    (app_dir / "before").mkdir()
    before = fake_binaries(app_dir / "before")
    before_env = before.environment(
        APP_DIR=posix(app_dir),
        DEPLOY_SHA=SHA,
        DEPLOY_DIGEST=DIGEST,
        FAKE_COMPOSE_SOURCE=posix(COMPOSE),
        FAKE_READY="false",
    )
    completed = run_script(DEPLOY_SCRIPT, before_env)
    assert completed.returncode != 0
    assert "docker compose stop worker" not in before.lines("docker ")
    assert "no worker was running before it and none was started" in completed.stderr
    assert not (app_dir / "DEPLOYED").exists()


def test_a_rollback_to_a_release_before_the_worker_drains_it_and_starts_none(
    host: tuple[FakeBinaries, dict[str, str], Path], tmp_path: Path
) -> None:
    """The advertised rollback (this script with an older sha and digest) against a target
    whose file names no worker: the running worker is drained under the installed file,
    the target's file is installed, the app lands, and no worker is started (the stopped
    container is an orphan compose warns about; the runbook says so)."""
    fakes, env, app_dir = host
    target = tmp_path / "pre-worker.yaml"
    target.write_text(PRE_WORKER_COMPOSE)
    env["FAKE_COMPOSE_SOURCE"] = posix(target)
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode == 0, completed.stderr
    docker = fakes.lines("docker ")
    assert "docker compose stop worker" in docker
    assert WORKER_UP not in docker
    assert "the target names no worker service; none started" in completed.stdout
    assert (app_dir / "compose.yaml").read_text() == PRE_WORKER_COMPOSE
    assert (app_dir / "DEPLOYED").read_text() == SHA + "\n"


@pytest.mark.parametrize("fail_on", [WORKER_UP.removeprefix("docker "), "image prune -f"])
def test_a_failure_after_the_workers_start_reports_only_what_ps_can_tell(
    host: tuple[FakeBinaries, dict[str, str], Path], fail_on: str
) -> None:
    """The external read's first finding: a detached start whose wait failed, or a prune
    that failed after a healthy start, leaves the container running, so the trap must
    not say the worker is stopped; it says the state is `docker compose ps`'s."""
    fakes, env, app_dir = host
    env["FAKE_DOCKER_FAIL_ON"] = fail_on  # the fake matches its arguments, without "docker "
    completed = run_script(DEPLOY_SCRIPT, env)
    assert completed.returncode == 1
    assert WORKER_UP in fakes.lines("docker ")
    assert "deploy failed after the worker was started from the new image" in completed.stderr
    assert "stays stopped" not in completed.stderr
    assert f"DEPLOY_SHA={SHA} DEPLOY_DIGEST={DIGEST}" in completed.stderr
    assert "docker compose start worker" not in fakes.lines("docker ")
    assert not (app_dir / "DEPLOYED").exists()


def test_the_base_urls_the_deploy_exports_are_their_sources_values() -> None:
    """The worker's child composes its hosts from the environment, so the deploy exports
    the HR site and the tracker's gateway root as literals; neither is in Parameter Store.
    The HR site is the demo configuration's and the gateway root the investigate
    workflow's default, so the three copies are held to one another here (the worker
    service step's group 3)."""
    script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    exported = dict(re.findall(r"^export (LEAVE_IMPACT_\w+_BASE_URL)=(\S+)$", script, re.MULTILINE))
    demo = json.loads(
        (DEPLOY_SCRIPT.parents[2] / "src" / "leaveimpact" / "app" / "demo.json").read_text(
            encoding="utf-8"
        )
    )
    assert exported["LEAVE_IMPACT_FRAPPE_BASE_URL"] == demo["frappe_base_url"]
    workflow = (DEPLOY_SCRIPT.parents[2] / ".github" / "workflows" / "investigate.yml").read_text(
        encoding="utf-8"
    )
    default = re.search(
        r"^      jira_base_url:\n(?:        .*\n)*?        default: (\S+)$", workflow, re.MULTILINE
    )
    assert default is not None
    assert exported["LEAVE_IMPACT_JIRA_BASE_URL"] == default.group(1)
