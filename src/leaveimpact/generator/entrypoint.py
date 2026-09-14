"""The generator's configuration boundary: the recipe from the command line, the writers it needs.

Every value the generation job needs arrives as a string — a command-line argument or an
environment variable — and is parsed, type-checked and named exactly once, so the
composition root and everything under it see ``OrgParams``, ``Hosts`` and bucket names and
never a string they have to interpret (the configuration-boundary ruling at the
organization step, applied to the job). The two sources are two kinds of value, and the
split is the point: what defines the world — the seed, the world's start date, the
organization's dials — is the command line, the ``workflow_dispatch`` inputs, parsed here;
what depends on where the job runs — the vendor hosts and their credentials, the buckets,
the region — is the environment, parsed by ``adapters.wiring`` for this job and the
validator alike, since both read the same names (the entry-point ruling of the step 12
interview). What is the generator's alone is the write side: the two stores as writers,
which only this shell may open, so ``stores_for`` lives here and not in the shared wiring.

A missing or malformed value is ``ConfigurationError`` naming the flag or variable and
what was expected, raised before any credential is used or any host is touched.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.adapters.object_store.s3 import s3_client
from leaveimpact.adapters.object_store.s3_write import S3ObjectWriter
from leaveimpact.adapters.object_store.write import ObjectWriter
from leaveimpact.adapters.prose.bedrock import BedrockChecker, BedrockWriter, bedrock_client
from leaveimpact.adapters.wiring import (
    PREFIX,
    ConfigurationError,
    Deployment,
    deployment_from_env,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.worldtime import date_at
from leaveimpact.world.artifacts import SHA256_HEX
from leaveimpact.world.org import DEFAULT_PARAMS, OrgParams

__all__ = [
    "ConfigurationError",
    "Deployment",
    "ProseModels",
    "WorldRecipe",
    "deployment_from_env",
    "parse_recipe",
    "prose_models_for",
    "prose_models_from_env",
    "stores_for",
]

DEFAULT_ATTEMPT_CAP = 4
"""Fresh attempts per target before the target fails; revisited on the first world's numbers."""


@dataclass(frozen=True, slots=True)
class WorldRecipe:
    """What defines the world, plus the two run controls of the prose stage.

    ``attempt_cap`` bounds the materializer and is recorded in the world's provenance;
    ``resume`` names a sealed realization to continue instead of generating a fresh one
    (the step 14 rulings: before sealing a restart regenerates, after it resumes).
    """

    seed: int
    params: OrgParams
    world_start: date
    attempt_cap: int = DEFAULT_ATTEMPT_CAP
    resume: WorldVersion | None = None


def parse_recipe(argv: Sequence[str]) -> WorldRecipe:
    """The world recipe from ``argv``; every organization dial defaults to ``DEFAULT_PARAMS``."""
    parser = argparse.ArgumentParser(
        prog="python -m leaveimpact.generator",
        description="Generate a world and seal it into the benchmark's buckets.",
        exit_on_error=False,
    )
    parser.add_argument("--seed", type=int, required=True, help="the generation seed")
    parser.add_argument(
        "--world-start", required=True, help="the world's first day, ISO 8601 (2026-01-05)"
    )
    defaults = DEFAULT_PARAMS
    parser.add_argument("--org-size", type=int, default=defaults.org_size)
    parser.add_argument("--team-count", type=int, default=defaults.team_count)
    parser.add_argument("--component-count", type=int, default=defaults.component_count)
    parser.add_argument("--blank-skill-records", type=int, default=defaults.blank_skill_records)
    parser.add_argument(
        "--skills-per-person",
        type=int,
        nargs=2,
        metavar=("MIN", "MAX"),
        default=list(defaults.skills_per_person),
    )
    parser.add_argument("--contractor-share", type=float, default=defaults.contractor_share)
    parser.add_argument("--remote-share", type=float, default=defaults.remote_share)
    parser.add_argument("--reference-timezone", default=defaults.reference_timezone)
    parser.add_argument("--timezone-gap-hours", type=int, default=defaults.timezone_gap_hours)
    parser.add_argument(
        "--attempt-cap",
        type=int,
        default=DEFAULT_ATTEMPT_CAP,
        help="fresh attempts per prose target before the target fails (default 4)",
    )
    parser.add_argument(
        "--resume",
        default=None,
        metavar="WORLD_VERSION",
        help="continue sealing the named realization instead of generating a fresh one",
    )
    try:
        parsed = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit) as error:
        raise ConfigurationError(f"the command line is not a world recipe: {error}") from error
    if parsed.attempt_cap < 1:
        raise ConfigurationError(f"--attempt-cap is at least one, got {parsed.attempt_cap}")
    resume: WorldVersion | None = None
    if parsed.resume is not None:
        if not SHA256_HEX.fullmatch(parsed.resume):
            raise ConfigurationError(f"--resume is a 64-hex world version, got {parsed.resume!r}")
        resume = WorldVersion(parsed.resume)
    try:
        world_start = date_at(parsed.world_start, "--world-start")
    except ValueError as error:
        raise ConfigurationError(f"--world-start is an ISO date (2026-01-05): {error}") from error
    try:
        params = OrgParams(
            org_size=parsed.org_size,
            team_count=parsed.team_count,
            component_count=parsed.component_count,
            blank_skill_records=parsed.blank_skill_records,
            skills_per_person=(parsed.skills_per_person[0], parsed.skills_per_person[1]),
            contractor_share=parsed.contractor_share,
            remote_share=parsed.remote_share,
            reference_timezone=parsed.reference_timezone,
            timezone_gap_hours=parsed.timezone_gap_hours,
        )
    except ValueError as error:
        raise ConfigurationError(f"the organization dials are not consistent: {error}") from error
    return WorldRecipe(parsed.seed, params, world_start, parsed.attempt_cap, resume)


@dataclass(frozen=True, slots=True)
class ProseModels:
    """The two inference profiles and the region the prose stage calls them in.

    From the environment and never defaulted: the workflow is the authority on which
    models write a world, and a value the code guessed would be a choice nobody made
    (the step 14 rulings). Separate from the object store's region on purpose, so a run
    against the local twin can still reach Bedrock.
    """

    writer: str
    checker: str
    region: str


def prose_models_from_env(env: Mapping[str, str]) -> ProseModels:
    """``LEAVE_IMPACT_PROSE_WRITER_MODEL``, ``…_CHECKER_MODEL`` and ``…_BEDROCK_REGION``."""
    return ProseModels(
        writer=_required(env, "PROSE_WRITER_MODEL"),
        checker=_required(env, "PROSE_CHECKER_MODEL"),
        region=_required(env, "BEDROCK_REGION"),
    )


def prose_models_for(models: ProseModels) -> tuple[BedrockWriter, BedrockChecker]:
    """The writer and the checker over one runtime client, on the ambient credentials."""
    client = bedrock_client(models.region)
    return BedrockWriter(client, models.writer), BedrockChecker(client, models.checker)


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(PREFIX + name, "").strip()
    if not value:
        raise ConfigurationError(f"{PREFIX}{name} is not set and the prose stage needs it")
    return value


def stores_for(deployment: Deployment) -> tuple[ObjectWriter, ObjectWriter]:
    """The truth and world writers the deployment names, in that order; the generator's alone."""
    if deployment.local_root is not None:
        root = deployment.local_root
        return LocalObjectWriter(root / "truth"), LocalObjectWriter(root / "world")
    assert deployment.buckets is not None, "a deployment names a root or the buckets"
    client = s3_client(deployment.buckets.region)
    return (
        S3ObjectWriter(client, deployment.buckets.truth),
        S3ObjectWriter(client, deployment.buckets.world),
    )
