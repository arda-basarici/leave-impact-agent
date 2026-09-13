"""The generator's configuration boundary: raw scalars in, typed records out, nothing else.

Every value the generation job needs arrives as a string — a command-line argument or an
environment variable — and is parsed, type-checked and named exactly once here, so the
composition root and everything under it see ``OrgParams``, ``Hosts`` and bucket names and
never a string they have to interpret (the configuration-boundary ruling at the
organization step, applied to the job). The two sources are two kinds of value, and the
split is the point: what defines the world — the seed, the world's start date, the
organization's dials — is the command line, the ``workflow_dispatch`` inputs; what
depends on where the job runs — the vendor hosts and their credentials, the buckets, the
region — is the environment, filled by the workflow from its secrets and variables, by
the deploy script from the parameter store, or by a workstation's own variables, and
the code cannot tell which (the entry-point ruling of the step 12 interview).

The environment variable names, the one place they are listed:

- ``LEAVE_IMPACT_FRAPPE_BASE_URL``, ``LEAVE_IMPACT_FRAPPE_API_KEY``,
  ``LEAVE_IMPACT_FRAPPE_API_SECRET`` — the world's Frappe site and its API pair.
- ``LEAVE_IMPACT_JIRA_BASE_URL``, ``LEAVE_IMPACT_JIRA_EMAIL``, ``LEAVE_IMPACT_JIRA_TOKEN``
  — the Jira site, the account and its token.
- ``LEAVE_IMPACT_GOOGLE_AUTHORIZED_USER_FILE`` — the path of the authorized-user JSON
  google-auth wrote at consent; the workflow writes the secret to a file on the
  runner's ephemeral disk and passes the path, since the value is multi-line.
- ``LEAVE_IMPACT_WORLD_BUCKET``, ``LEAVE_IMPACT_TRUTH_BUCKET``, ``LEAVE_IMPACT_AWS_REGION``
  — the two buckets and their region, for the S3 stores on the ambient AWS credentials
  the workflow's OIDC exchange exports.
- ``LEAVE_IMPACT_OBJECT_STORE_ROOT`` — instead of the three above: a directory under
  which the local twins hold ``truth/`` and ``world/``, the development path with no AWS
  in reach. Naming both a root and a bucket is refused as ambiguous.

A missing or malformed value is ``ConfigurationError`` naming the variable or flag and
what was expected, raised before any credential is used or any host is touched. The
records built here are never logged: the credential types' ``repr`` hides their values,
and the entry point prints the world version and the run's numbers, nothing of these.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, cast

from leaveimpact.adapters.calendar.adapter import CalendarCredential
from leaveimpact.adapters.frappe.adapter import FrappeCredential
from leaveimpact.adapters.jira.adapter import JiraCredential
from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.adapters.object_store.s3 import s3_client
from leaveimpact.adapters.object_store.s3_write import S3ObjectWriter
from leaveimpact.adapters.object_store.write import ObjectWriter
from leaveimpact.core.worldtime import date_at
from leaveimpact.generator.systems import Hosts
from leaveimpact.world.org import DEFAULT_PARAMS, OrgParams

PREFIX = "LEAVE_IMPACT_"


class ConfigurationError(Exception):
    """A value the job needs is missing or malformed; the message names it and the expectation."""


@dataclass(frozen=True, slots=True)
class WorldRecipe:
    """What defines the world: the command line's half of the configuration."""

    seed: int
    params: OrgParams
    world_start: date


@dataclass(frozen=True, slots=True)
class Buckets:
    """The two S3 buckets and their region."""

    world: str
    truth: str
    region: str


@dataclass(frozen=True, slots=True)
class Deployment:
    """Where the job runs: the environment's half of the configuration."""

    hosts: Hosts
    buckets: Buckets | None
    local_root: Path | None


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
    try:
        parsed = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit) as error:
        raise ConfigurationError(f"the command line is not a world recipe: {error}") from error
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
    return WorldRecipe(parsed.seed, params, world_start)


def deployment_from_env(env: Mapping[str, str]) -> Deployment:
    """The hosts, credentials and stores from ``env``; a missing name is named in the error."""
    hosts = Hosts(
        frappe_base_url=_url(env, "FRAPPE_BASE_URL"),
        frappe_credential=FrappeCredential(
            api_key=_required(env, "FRAPPE_API_KEY"),
            api_secret=_required(env, "FRAPPE_API_SECRET"),
        ),
        jira_base_url=_url(env, "JIRA_BASE_URL"),
        jira_credential=JiraCredential(
            email=_required(env, "JIRA_EMAIL"), api_token=_required(env, "JIRA_TOKEN")
        ),
        calendar_credential=_calendar_credential(env),
    )
    root = env.get(PREFIX + "OBJECT_STORE_ROOT", "").strip()
    named_buckets = [
        name for name in ("WORLD_BUCKET", "TRUTH_BUCKET", "AWS_REGION") if env.get(PREFIX + name)
    ]
    if root and named_buckets:
        raise ConfigurationError(
            f"{PREFIX}OBJECT_STORE_ROOT names the local twin and {PREFIX}{named_buckets[0]} "
            "names S3: one store per run, not both"
        )
    if root:
        return Deployment(hosts, buckets=None, local_root=Path(root))
    buckets = Buckets(
        world=_required(env, "WORLD_BUCKET"),
        truth=_required(env, "TRUTH_BUCKET"),
        region=_required(env, "AWS_REGION"),
    )
    return Deployment(hosts, buckets=buckets, local_root=None)


def stores_for(deployment: Deployment) -> tuple[ObjectWriter, ObjectWriter]:
    """The truth and world writers the deployment names, in that order."""
    if deployment.local_root is not None:
        root = deployment.local_root
        return LocalObjectWriter(root / "truth"), LocalObjectWriter(root / "world")
    assert deployment.buckets is not None, "a deployment names a root or the buckets"
    client = s3_client(deployment.buckets.region)
    return (
        S3ObjectWriter(client, deployment.buckets.truth),
        S3ObjectWriter(client, deployment.buckets.world),
    )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(PREFIX + name, "").strip()
    if not value:
        raise ConfigurationError(f"{PREFIX}{name} is not set and the job needs it")
    return value


def _url(env: Mapping[str, str], name: str) -> str:
    value = _required(env, name)
    if not value.startswith(("https://", "http://")):
        raise ConfigurationError(f"{PREFIX}{name} is a base URL with its scheme, got {value!r}")
    return value.rstrip("/")


def _calendar_credential(env: Mapping[str, str]) -> CalendarCredential:
    name = "GOOGLE_AUTHORIZED_USER_FILE"
    path = Path(_required(env, name))
    try:
        info = cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
        return CalendarCredential.from_authorized_user_info(info)
    except OSError as error:
        raise ConfigurationError(f"{PREFIX}{name} names {path}, which cannot be read") from error
    except (ValueError, KeyError, TypeError) as error:
        raise ConfigurationError(
            f"{PREFIX}{name} names {path}, which is not the authorized-user JSON google-auth "
            "writes (client id, client secret, refresh token)"
        ) from error
