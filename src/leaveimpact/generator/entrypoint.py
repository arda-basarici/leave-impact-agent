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
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

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
from leaveimpact.generator.recipe import DEFAULT_ATTEMPT_CAP, WorldRecipe
from leaveimpact.world.artifacts import SHA256_HEX
from leaveimpact.world.disclosure import Disclosure
from leaveimpact.world.levels import NO_FILLER, FillerPlan, SealedLevel
from leaveimpact.world.org import DEFAULT_PARAMS, OrgParams
from leaveimpact.world.plan import PLANS

__all__ = [
    "ConfigurationError",
    "Deployment",
    "ProseModels",
    "deployment_from_env",
    "parse_recipe",
    "prose_models_for",
    "prose_models_from_env",
    "stores_for",
]

def parse_recipe(argv: Sequence[str], env: Mapping[str, str] | None = None) -> WorldRecipe:
    """The world recipe from ``argv``, the seed from ``env`` under the secret source; every
    organization dial defaults to ``DEFAULT_PARAMS``.

    ``--seed N`` is the development path. ``--seed-source secret`` reads the seed from
    ``LEAVE_IMPACT_SEED_HEX`` instead, sixty-four lowercase hex characters parsed in memory:
    the one form the masking probe showed safe to cross a workflow whole, never echoed, cut
    or re-encoded (the generator step's ruling 5), so a refusal names the variable and the
    rule and nothing of the value. ``--embargoed`` seals the world's disclosure mark and
    needs the secret source, since an embargo over a seed given in the open is one an
    enumeration undoes. With no ``env`` the secret source refuses as unset.
    """
    parser = argparse.ArgumentParser(
        prog="python -m leaveimpact.generator",
        description="Generate a world and seal it into the benchmark's buckets.",
        exit_on_error=False,
    )
    parser.add_argument(
        "--seed", type=int, default=None, help="the generation seed, under the input source"
    )
    parser.add_argument(
        "--seed-source",
        choices=("input", "secret"),
        default="input",
        help=f"where the seed comes from: --seed, or {PREFIX}SEED_HEX in the environment",
    )
    parser.add_argument(
        "--embargoed",
        action="store_true",
        help="seal the world embargoed: no public output carries its enumerable digests",
    )
    parser.add_argument(
        "--plan",
        choices=sorted(PLANS),
        default="tier1",
        help="the plan the world is drawn under (default tier1)",
    )
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
        help="fresh attempts per prose target before the target fails (default 8)",
    )
    parser.add_argument(
        "--filler-documents",
        type=int,
        default=0,
        help="filler documents minted after the planted world (default none)",
    )
    parser.add_argument(
        "--filler-sections",
        type=int,
        default=DEFAULT_FILLER_SECTIONS,
        help="sections a filler document holds, each a model-written paragraph (default 4)",
    )
    parser.add_argument(
        "--level",
        action="append",
        default=[],
        metavar="NAME=COUNT",
        help="a corpus level sealed over the first COUNT filler documents; repeatable",
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
    seed = _seed(parsed.seed, parsed.seed_source, {} if env is None else env)
    disclosure = Disclosure.EMBARGOED if parsed.embargoed else Disclosure.OPEN
    if disclosure is Disclosure.EMBARGOED and parsed.seed_source != "secret":
        raise ConfigurationError(
            "--embargoed needs --seed-source secret: an embargo over a seed given in the open "
            "is none"
        )
    if parsed.attempt_cap < 1:
        raise ConfigurationError(f"--attempt-cap is at least one, got {parsed.attempt_cap}")
    resume: WorldVersion | None = None
    if parsed.resume is not None:
        if not SHA256_HEX.fullmatch(parsed.resume):
            raise ConfigurationError(f"--resume is a 64-hex world version, got {parsed.resume!r}")
        resume = WorldVersion(parsed.resume)
    filler = _filler_plan(parsed.filler_documents, parsed.filler_sections, parsed.level)
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
    return WorldRecipe(
        seed, params, world_start, parsed.attempt_cap, resume, parsed.plan, filler, disclosure
    )


SEED_HEX = re.compile(r"[0-9a-f]{64}")
"""The secret seed's one transport form: thirty-two bytes of entropy as lowercase hex."""


def _seed(given: int | None, source: str, env: Mapping[str, str]) -> int:
    """The seed the source names; a refusal under the secret source carries nothing of the
    value, not a prefix, not a length, since the log it would print to is public."""
    if source == "input":
        if given is None:
            raise ConfigurationError("--seed is required under the input seed source")
        return given
    if given is not None:
        raise ConfigurationError(
            "--seed is not given under the secret seed source; the seed is the environment's"
        )
    value = env.get(PREFIX + "SEED_HEX", "")
    if not value:
        raise ConfigurationError(f"{PREFIX}SEED_HEX is not set and the secret seed source needs it")
    if not SEED_HEX.fullmatch(value):
        raise ConfigurationError(f"{PREFIX}SEED_HEX is sixty-four lowercase hex characters")
    return int(value, 16)


DEFAULT_FILLER_SECTIONS = 4
"""Sections a filler document holds when the recipe names a pool and no count: the
development default of the generator step's group 2, measured before the freeze."""


def _filler_plan(documents: int, sections: int, levels: Sequence[str]) -> FillerPlan:
    """The filler plan the three options name; ``ConfigurationError`` names the option or
    the plan's own rule that refused."""
    if documents == 0:
        if levels:
            raise ConfigurationError("--level needs a pool: give --filler-documents")
        return NO_FILLER
    sealed: list[SealedLevel] = []
    for spec in levels:
        name, equals, count = spec.partition("=")
        if not equals or not name or not count.isdigit():
            raise ConfigurationError(f"--level is NAME=COUNT, got {spec!r}")
        sealed.append(SealedLevel(name, int(count)))
    try:
        return FillerPlan(documents, sections, tuple(sealed))
    except ValueError as error:
        raise ConfigurationError(f"the filler plan is not consistent: {error}") from error


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
