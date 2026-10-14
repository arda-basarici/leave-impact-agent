"""The deploy script under fake binaries: the app image pulled by the digest CI recorded and
given the commit's tag, the service image pulled by compose, the secrets reaching the
containers' environment and never a command line, the deployed sha written last, and the
refusals before any pull (no digest, a parameter still holding its placeholder)."""

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
        "docker compose run --rm app",
    ]
    assert (app_dir / "DEPLOYED").read_text() == SHA + "\n"
    assert f"deployed {SHA} ({DIGEST}) at " in completed.stdout
    # The compose file of the commit, fetched by sha into the app directory.
    assert fakes.lines("curl") == [
        "curl -fsSL https://raw.githubusercontent.com/arda-basarici/leave-impact-agent/"
        f"{SHA}/compose.yaml -o compose.yaml"
    ]
    # Every container saw the tag, the bucket and the password in its environment, and no
    # command line carried the password. The fake numbers every docker invocation, so the
    # containers' environments are the ones at the three `compose run` positions.
    runs = [n for n, line in enumerate(docker, start=1) if "compose run" in line]
    assert len(runs) == 3
    for n in runs:
        held = (fakes.fake_dir / f"docker-env-{n}.txt").read_text()
        assert f"APP_TAG={SHA}" in held
        assert "LEAVE_IMPACT_WORLD_BUCKET=leave-impact-world-445743457479" in held
        assert "LEAVE_IMPACT_AWS_REGION=eu-central-1" in held
        assert "POSTGRES_PASSWORD=value-of-/leave-agent/postgres-password" in held
    assert "value-of-" not in "\n".join(docker)


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
