"""The generator's configuration boundary: a recipe from the command line with every dial
defaulting to the reference parameters, a missing or malformed value named with what was
expected, the organization's own consistency rule surfacing through the boundary; the
deployment from the environment with each missing name named, a base URL required to carry
its scheme, the Google credential read from the file the variable names and refused when
absent or not the authorized-user JSON, the local twin and the buckets exclusive; and the
stores opened where the deployment says, the local twins under ``truth/`` and ``world/``."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.generator.entrypoint import (
    PREFIX,
    ConfigurationError,
    deployment_from_env,
    parse_recipe,
    stores_for,
)
from leaveimpact.world.org import DEFAULT_PARAMS


def test_a_recipe_defaults_every_dial_and_takes_the_ones_given() -> None:
    recipe = parse_recipe(["--seed", "7", "--world-start", "2026-01-05"])
    assert (recipe.seed, recipe.world_start) == (7, date(2026, 1, 5))
    assert recipe.params == DEFAULT_PARAMS
    dialed = parse_recipe(
        [
            "--seed",
            "7",
            "--world-start",
            "2026-01-05",
            "--org-size",
            "12",
            "--team-count",
            "3",
            "--skills-per-person",
            "2",
            "3",
            "--contractor-share",
            "0.2",
        ]
    )
    assert (dialed.params.org_size, dialed.params.team_count) == (12, 3)
    assert dialed.params.skills_per_person == (2, 3)
    assert dialed.params.contractor_share == 0.2


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--world-start", "2026-01-05"], "--seed"),
        (["--seed", "x", "--world-start", "2026-01-05"], "--seed"),
        (["--seed", "7", "--world-start", "5 Jan 2026"], "--world-start"),
        (
            ["--seed", "7", "--world-start", "2026-01-05", "--reference-timezone", "Europe/Berlin"],
            "not consistent",
        ),
    ],
)
def test_a_malformed_recipe_names_the_flag_or_the_rule(argv: list[str], expected: str) -> None:
    with pytest.raises(ConfigurationError, match=expected):
        parse_recipe(argv)


def environment(tmp_path: Path, **overrides: str) -> dict[str, str]:
    google = tmp_path / "google.json"
    google.write_text(
        json.dumps(
            {"client_id": "cid", "client_secret": "cs", "refresh_token": "refresh-token-value"}
        ),
        encoding="utf-8",
    )
    env = {
        "FRAPPE_BASE_URL": "https://hr.example.invalid/",
        "FRAPPE_API_KEY": "frappe-key-value",
        "FRAPPE_API_SECRET": "s",
        "JIRA_BASE_URL": "https://jira.example.invalid",
        "JIRA_EMAIL": "ops@example.invalid",
        "JIRA_TOKEN": "t",
        "GOOGLE_AUTHORIZED_USER_FILE": str(google),
        "WORLD_BUCKET": "world-bucket",
        "TRUTH_BUCKET": "truth-bucket",
        "AWS_REGION": "eu-central-1",
    }
    env.update(overrides)
    return {PREFIX + name: value for name, value in env.items()}


def test_a_deployment_reads_every_name_once_and_strips_the_url(tmp_path: Path) -> None:
    deployment = deployment_from_env(environment(tmp_path))
    assert deployment.hosts.frappe_base_url == "https://hr.example.invalid"
    assert deployment.hosts.frappe_credential.api_key == "frappe-key-value"
    assert deployment.hosts.jira_credential.email == "ops@example.invalid"
    assert deployment.hosts.calendar_credential.refresh_token == "refresh-token-value"
    assert deployment.buckets is not None
    assert (deployment.buckets.world, deployment.buckets.truth, deployment.buckets.region) == (
        "world-bucket",
        "truth-bucket",
        "eu-central-1",
    )
    assert deployment.local_root is None
    shown = repr(deployment)
    assert "refresh-token-value" not in shown and "frappe-key-value" not in shown


@pytest.mark.parametrize(
    "missing", ["FRAPPE_API_SECRET", "JIRA_TOKEN", "GOOGLE_AUTHORIZED_USER_FILE", "TRUTH_BUCKET"]
)
def test_a_missing_variable_is_named(tmp_path: Path, missing: str) -> None:
    env = environment(tmp_path)
    del env[PREFIX + missing]
    with pytest.raises(ConfigurationError, match=PREFIX + missing):
        deployment_from_env(env)


def test_a_url_without_a_scheme_and_a_bad_google_file_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="FRAPPE_BASE_URL is a base URL"):
        deployment_from_env(environment(tmp_path, FRAPPE_BASE_URL="hr.example.invalid"))
    with pytest.raises(ConfigurationError, match="cannot be read"):
        deployment_from_env(
            environment(tmp_path, GOOGLE_AUTHORIZED_USER_FILE=str(tmp_path / "absent.json"))
        )
    env = environment(tmp_path)
    for content in ('{"client_id": "cid"}', "not json"):
        (tmp_path / "google.json").write_text(content, encoding="utf-8")
        with pytest.raises(ConfigurationError, match="not the authorized-user JSON"):
            deployment_from_env(env)


def test_the_local_twin_and_the_buckets_are_exclusive(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not both"):
        deployment_from_env(environment(tmp_path, OBJECT_STORE_ROOT=str(tmp_path / "store")))
    env = environment(tmp_path, OBJECT_STORE_ROOT=str(tmp_path / "store"))
    for name in ("WORLD_BUCKET", "TRUTH_BUCKET", "AWS_REGION"):
        del env[PREFIX + name]
    deployment = deployment_from_env(env)
    assert deployment.buckets is None and deployment.local_root == tmp_path / "store"
    truth, world = stores_for(deployment)
    assert isinstance(truth, LocalObjectWriter) and isinstance(world, LocalObjectWriter)
    assert (truth.root, world.root) == (tmp_path / "store" / "truth", tmp_path / "store" / "world")
