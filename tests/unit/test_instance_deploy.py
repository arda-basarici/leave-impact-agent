"""The deploy script under fake binaries: the app image pulled by the digest CI recorded and
given the commit's tag, the service image pulled by compose, the secrets reaching the
containers' environment and never a command line, the two named checks (the identity
command as the image check, the readiness route read after `up --wait` as the readiness
check) with the deployed sha written last and only after both, and the refusals: before
any pull (no digest, a parameter still holding its placeholder), and after the service
started (a service that is not ready, a container answering with another revision), each
leaving no DEPLOYED marker."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.shell_support import DEPLOY_SCRIPT, FakeBinaries, fake_binaries, posix, run_script

SHA = "f" * 40
DIGEST = "sha256:" + "d" * 64
IMAGE = "ghcr.io/arda-basarici/leave-impact-agent"


@pytest.fixture
def host(tmp_path: Path) -> tuple[FakeBinaries, dict[str, str], Path]:
    fakes = fake_binaries(tmp_path)
    app_dir = tmp_path / "srv"
    app_dir.mkdir()
    env = fakes.environment(APP_DIR=posix(app_dir), DEPLOY_SHA=SHA, DEPLOY_DIGEST=DIGEST)
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
    assert docker[:4] == [
        f"docker pull --quiet {IMAGE}@{DIGEST}",
        f"docker tag {IMAGE}@{DIGEST} {IMAGE}:{SHA}",
        "docker compose pull --quiet postgres",
        "docker compose up -d --wait postgres",
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
    assert f"identity: leaveimpact {SHA}: the demo surface's image" in completed.stdout
    assert f'ready: {{"ready":true,"code_version":"{SHA}"' in completed.stdout
    assert (app_dir / "DEPLOYED").read_text() == SHA + "\n"
    assert f"deployed {SHA} ({DIGEST}) at " in completed.stdout
    # The compose file of the commit, fetched by sha into the app directory.
    assert fakes.lines("curl") == [
        "curl -fsSL https://raw.githubusercontent.com/arda-basarici/leave-impact-agent/"
        f"{SHA}/compose.yaml -o compose.yaml"
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
