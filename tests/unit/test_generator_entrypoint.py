"""The generator's configuration boundary: a recipe from the command line with every dial
defaulting to the reference parameters, a missing or malformed value named with what was
expected, the organization's own consistency rule surfacing through the boundary; and the
writers opened where the deployment says, the local twins under ``truth/`` and ``world/``
(the deployment's own parsing is the shared wiring's, tested there); the unprojected flag
read as the recipe's run control; and the local root's guard, which passes a root outside
any repository or one the repository ignores and refuses a tracked one naming both."""

from __future__ import annotations

import re
import subprocess
import traceback
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.generator.entrypoint import (
    ConfigurationError,
    Stores,
    check_local_root,
    deployment_from_env,
    parse_recipe,
    prose_models_from_env,
    stores_for,
)
from leaveimpact.world.disclosure import Disclosure
from leaveimpact.world.levels import NO_FILLER, FillerPlan, SealedLevel
from leaveimpact.world.org import DEFAULT_PARAMS
from tests.unit.test_adapters_wiring import local_environment


def test_a_recipe_defaults_every_dial_and_takes_the_ones_given() -> None:
    recipe = parse_recipe(["--seed", "7", "--world-start", "2026-01-05"])
    assert (recipe.seed, recipe.world_start) == (7, date(2026, 1, 5))
    assert recipe.params == DEFAULT_PARAMS
    assert recipe.plan_name == "tier1"
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
            "--plan",
            "tier1-plus-qualification",
        ]
    )
    assert dialed.plan_name == "tier1-plus-qualification"
    assert (dialed.params.org_size, dialed.params.team_count) == (12, 3)
    assert dialed.params.skills_per_person == (2, 3)
    assert dialed.params.contractor_share == 0.2


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--world-start", "2026-01-05"], "--seed"),
        (["--seed", "x", "--world-start", "2026-01-05"], "--seed"),
        (["--seed", "7", "--world-start", "5 Jan 2026"], "--world-start"),
        (["--seed", "7", "--world-start", "2026-01-05", "--plan", "tier4"], "--plan"),
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
    truth, world = stores_for(Stores(deployment.buckets, deployment.local_root))
    assert isinstance(truth, LocalObjectWriter) and isinstance(world, LocalObjectWriter)
    assert (truth.root, world.root) == (tmp_path / "store" / "truth", tmp_path / "store" / "world")


def test_the_prose_controls_default_and_are_validated() -> None:
    base = ["--seed", "7", "--world-start", "2026-01-05"]
    assert (parse_recipe(base).attempt_cap, parse_recipe(base).resume) == (8, None)
    named = parse_recipe([*base, "--attempt-cap", "2", "--resume", "a" * 64])
    assert (named.attempt_cap, named.resume) == (2, "a" * 64)
    with pytest.raises(ConfigurationError, match="--attempt-cap is at least one"):
        parse_recipe([*base, "--attempt-cap", "0"])
    with pytest.raises(ConfigurationError, match="--resume is a 64-hex world version"):
        parse_recipe([*base, "--resume", "not-a-version"])


def test_the_filler_plan_defaults_to_no_pool_and_is_read_from_its_three_options() -> None:
    base = ["--seed", "7", "--world-start", "2026-01-05"]
    assert parse_recipe(base).filler == NO_FILLER
    pooled = parse_recipe(
        [*base, "--filler-documents", "12", "--filler-sections", "2", "--level", "padded=6"]
    )
    assert pooled.filler == FillerPlan(12, 2, (SealedLevel("padded", 6),))
    assert parse_recipe([*base, "--filler-documents", "3"]).filler == FillerPlan(3, 4)
    with pytest.raises(ConfigurationError, match="--level is NAME=COUNT"):
        parse_recipe([*base, "--filler-documents", "3", "--level", "padded"])
    with pytest.raises(ConfigurationError, match="--level needs a pool"):
        parse_recipe([*base, "--level", "padded=1"])
    with pytest.raises(ConfigurationError, match="the filler plan is not consistent"):
        parse_recipe([*base, "--filler-documents", "3", "--level", "padded=4"])
    with pytest.raises(ConfigurationError, match="the filler plan is not consistent"):
        parse_recipe([*base, "--filler-documents", "3", "--level", "base=0"])


def test_the_prose_models_come_from_the_environment_and_are_never_defaulted() -> None:
    env = {
        "LEAVE_IMPACT_PROSE_WRITER_MODEL": "eu.writer",
        "LEAVE_IMPACT_PROSE_CHECKER_MODEL": "eu.checker",
        "LEAVE_IMPACT_BEDROCK_REGION": "eu-central-1",
    }
    models = prose_models_from_env(env)
    assert (models.writer, models.checker, models.region) == (
        "eu.writer",
        "eu.checker",
        "eu-central-1",
    )
    for missing in env:
        with pytest.raises(ConfigurationError, match=f"{missing} is not set and the prose stage"):
            prose_models_from_env({k: v for k, v in env.items() if k != missing})


# --- The seed source and the embargo (the generator step's ruling 5) --------------------------

# A stand-in seed with no entropy, built in the open: sixty-four hex characters in shape alone.
STAND_IN_HEX = "0123456789abcdef" * 4
STAND_IN_ENV = {"LEAVE_IMPACT_SEED_HEX": STAND_IN_HEX}
FROM_ENV = ["--seed-source", "secret", "--world-start", "2026-01-05"]


def test_the_secret_source_reads_the_hex_seed_from_the_environment_and_seals_the_mark() -> None:
    recipe = parse_recipe(FROM_ENV, STAND_IN_ENV)
    assert recipe.seed == int(STAND_IN_HEX, 16) and recipe.disclosure is Disclosure.OPEN
    embargoed = parse_recipe([*FROM_ENV, "--embargoed"], STAND_IN_ENV)
    assert (embargoed.seed, embargoed.disclosure) == (int(STAND_IN_HEX, 16), Disclosure.EMBARGOED)
    plain = parse_recipe(["--seed", "7", "--world-start", "2026-01-05"], STAND_IN_ENV)
    assert (plain.seed, plain.disclosure) == (7, Disclosure.OPEN)


@pytest.mark.parametrize(
    ("argv", "env", "expected"),
    [
        (FROM_ENV, {}, "LEAVE_IMPACT_SEED_HEX is not set"),
        (FROM_ENV, {"LEAVE_IMPACT_SEED_HEX": STAND_IN_HEX.upper()}, "sixty-four lowercase hex"),
        (FROM_ENV, {"LEAVE_IMPACT_SEED_HEX": STAND_IN_HEX[:-1]}, "sixty-four lowercase hex"),
        (FROM_ENV, {"LEAVE_IMPACT_SEED_HEX": STAND_IN_HEX + "0"}, "sixty-four lowercase hex"),
        (FROM_ENV, {"LEAVE_IMPACT_SEED_HEX": "g" + STAND_IN_HEX[1:]}, "sixty-four lowercase hex"),
        ([*FROM_ENV, "--seed", "7"], STAND_IN_ENV, "--seed is not given under the secret"),
        (
            ["--seed", "7", "--world-start", "2026-01-05", "--embargoed"],
            {},
            "--embargoed needs --seed-source secret",
        ),
        (["--world-start", "2026-01-05"], STAND_IN_ENV, "--seed is required under the input"),
    ],
    ids=[
        "unset",
        "uppercase",
        "short",
        "long",
        "non-hex",
        "both sources",
        "embargo in the open",
        "no seed under input",
    ],
)
def test_a_seed_refusal_names_the_rule_and_carries_nothing_of_the_value(
    argv: list[str], env: dict[str, str], expected: str
) -> None:
    with pytest.raises(ConfigurationError) as refused:
        parse_recipe(argv, env)
    printed = "".join(traceback.format_exception(refused.value))
    assert expected in printed
    # The log a refusal prints to is public: no form of the value, not the whole, not a
    # prefix, not its decimal, not its length, and nothing from the environment it read.
    # Each form is searched as a whole number or string, not as a substring of a line
    # number the traceback prints (a two-digit length sat inside "line 163" once).
    given = env.get("LEAVE_IMPACT_SEED_HEX", STAND_IN_HEX)
    for form in (given, given[:8], str(int(STAND_IN_HEX, 16)), str(len(given))):
        assert re.search(rf"(?<![0-9a-f]){re.escape(form)}(?![0-9a-f])", printed) is None, form


def test_without_an_environment_the_secret_source_refuses_as_unset() -> None:
    with pytest.raises(ConfigurationError, match="LEAVE_IMPACT_SEED_HEX is not set"):
        parse_recipe(FROM_ENV)


def test_the_unprojected_flag_is_a_run_control_read_from_the_command_line() -> None:
    base = ["--seed", "7", "--world-start", "2026-01-05"]
    assert parse_recipe(base).unprojected is False
    assert parse_recipe([*base, "--unprojected"]).unprojected is True


def _repository(path: Path) -> Path:
    path.mkdir()
    subprocess.run(["git", "-C", str(path), "init", "-q"], check=True)
    return path


def test_a_root_outside_any_repository_passes_the_guard(tmp_path: Path) -> None:
    """The suite's temporary directory is under no repository, which is the assumption."""
    check_local_root(tmp_path / "store")
    check_local_root(tmp_path / "not" / "yet" / "made")


def test_a_root_the_repository_ignores_passes_and_a_tracked_one_refuses_naming_both(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path / "repo")
    (repository / ".gitignore").write_text("data/\n", encoding="utf-8")
    check_local_root(repository / "data" / "object-store")
    tracked = repository / "worlds"
    with pytest.raises(ConfigurationError) as refused:
        check_local_root(tracked)
    message = str(refused.value)
    assert str(tracked) in message and "does not ignore" in message
    assert repository.name in message
