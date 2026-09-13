"""The generator's configuration boundary: a recipe from the command line with every dial
defaulting to the reference parameters, a missing or malformed value named with what was
expected, the organization's own consistency rule surfacing through the boundary; and the
writers opened where the deployment says, the local twins under ``truth/`` and ``world/``
(the deployment's own parsing is the shared wiring's, tested there)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.generator.entrypoint import (
    ConfigurationError,
    deployment_from_env,
    parse_recipe,
    stores_for,
)
from leaveimpact.world.org import DEFAULT_PARAMS
from tests.unit.test_adapters_wiring import local_environment


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


def test_the_writers_open_under_the_local_root_the_deployment_names(tmp_path: Path) -> None:
    deployment = deployment_from_env(local_environment(tmp_path))
    truth, world = stores_for(deployment)
    assert isinstance(truth, LocalObjectWriter) and isinstance(world, LocalObjectWriter)
    assert (truth.root, world.root) == (tmp_path / "store" / "truth", tmp_path / "store" / "world")
