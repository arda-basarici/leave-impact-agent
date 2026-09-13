"""The read-side wiring both shells share: hosts and buckets from the environment, readers built.

The generator and the validator construct the same read-side adapters from the same
resolved configuration — the Frappe company, the Jira project and its field ids, the
calendar map, the world's documents in the bucket — and the rank-3 shells never import
one another, so the construction lives here, at the adapters' own level, once (ruling 4
of the step 12 interview, the reviewer's shape). Two boundaries hold on purpose. This
module builds read capabilities only: it hands out readers, the object store's reader
classes, and one narrow publication callable; never an object with a write method on
it, so a validator that imports it gains nothing the import law denies it by name. And
it aggregates the sibling adapters' constructors at the top level the way ``manifest``
does, while the siblings themselves keep not importing one another.

The environment's half of the configuration is parsed here too, since both jobs read the
same names for the same values: the vendor hosts and their credentials, and either the
two buckets with their region or the local twin's root. The names, listed once:

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

A missing or malformed value is ``ConfigurationError`` naming the variable and what was
expected, raised before any credential is used or any host is touched. The records
built here are never logged: the credential types' ``repr`` hides their values.

The verdict's publication is the one write a validator run makes, and it crosses this
seam as a callable that writes exactly one verdict key computed from the version and the
run's identifiers, the writer it closes over never exposed: the validator package cannot
name a writer, cannot choose a key, and cannot overwrite, which is the read-only boundary
of the validator step kept at source level while its one artifact still lands (the
part-2 review's carried obligation).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from leaveimpact.adapters.calendar.adapter import CalendarAdapter, CalendarCredential
from leaveimpact.adapters.frappe.adapter import FrappeAdapter, FrappeCredential
from leaveimpact.adapters.jira.adapter import JiraAdapter, JiraCredential
from leaveimpact.adapters.manifest import WorldManifest
from leaveimpact.adapters.object_store.documents import SealedDocumentReader
from leaveimpact.adapters.object_store.layout import verdict_key
from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.adapters.object_store.read import ObjectReader
from leaveimpact.adapters.object_store.s3 import S3ObjectReader, s3_client
from leaveimpact.adapters.object_store.s3_write import S3ObjectWriter
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.ports.read import CalendarReader, PeopleReader, WorkReader

PREFIX = "LEAVE_IMPACT_"


class ConfigurationError(Exception):
    """A value a job needs is missing or malformed; the message names it and the expectation."""


@dataclass(frozen=True, slots=True)
class Hosts:
    """Where the three vendor systems are and how to enter them."""

    frappe_base_url: str
    frappe_credential: FrappeCredential
    jira_base_url: str
    jira_credential: JiraCredential
    calendar_credential: CalendarCredential


@dataclass(frozen=True, slots=True)
class Buckets:
    """The two S3 buckets and their region."""

    world: str
    truth: str
    region: str


@dataclass(frozen=True, slots=True)
class Deployment:
    """Where a job runs: the environment's half of its configuration."""

    hosts: Hosts
    buckets: Buckets | None
    local_root: Path | None


@dataclass(frozen=True, slots=True)
class ObjectReaders:
    """The truth and world stores as readers."""

    truth: ObjectReader
    world: ObjectReader


@dataclass(frozen=True, slots=True)
class Readers:
    """The read side of one projected world, built from its manifest; ``close`` when done."""

    people: PeopleReader
    work: WorkReader
    calendar: CalendarReader
    documents: SealedDocumentReader
    close: Callable[[], None]


VerdictPublisher = Callable[[WorldVersion, str, str, bytes], str]
"""Publish one verdict: the version, the run id, the run attempt and the bytes; the version id."""


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


def readers_for(deployment: Deployment) -> ObjectReaders:
    """The truth and world stores as readers, where the deployment says they are."""
    if deployment.local_root is not None:
        root = deployment.local_root
        return ObjectReaders(LocalObjectReader(root / "truth"), LocalObjectReader(root / "world"))
    assert deployment.buckets is not None, "a deployment names a root or the buckets"
    client = s3_client(deployment.buckets.region)
    return ObjectReaders(
        S3ObjectReader(client, deployment.buckets.truth),
        S3ObjectReader(client, deployment.buckets.world),
    )


def verdict_publisher(deployment: Deployment) -> VerdictPublisher:
    """A callable that seals one verdict at its key in the world store and returns the version id.

    The writer lives in the closure and nowhere the caller can reach; the key is computed
    here from the version and the run's identifiers, so a rerun's verdict is a new
    immutable object and the caller cannot write anywhere else.
    """
    if deployment.local_root is not None:
        writer = LocalObjectWriter(deployment.local_root / "world")
    else:
        assert deployment.buckets is not None, "a deployment names a root or the buckets"
        writer = S3ObjectWriter(s3_client(deployment.buckets.region), deployment.buckets.world)

    def publish(version: WorldVersion, run_id: str, run_attempt: str, content: bytes) -> str:
        return writer.put_if_absent(verdict_key(version, run_id, run_attempt), content).version_id

    return publish


def build_readers(hosts: Hosts, manifest: WorldManifest, world_store: ObjectReader) -> Readers:
    """The four readers of the world ``manifest`` describes, on ``hosts`` and ``world_store``."""
    frappe = FrappeAdapter(
        base_url=hosts.frappe_base_url,
        credential=hosts.frappe_credential,
        config=manifest.systems.frappe,
    )
    jira = JiraAdapter(
        base_url=hosts.jira_base_url, credential=hosts.jira_credential, config=manifest.systems.jira
    )
    calendar = CalendarAdapter(
        credential=hosts.calendar_credential, config=manifest.systems.calendar
    )
    documents = SealedDocumentReader(world_store, manifest.world_version)

    def close() -> None:
        for adapter in (frappe, jira, calendar):
            adapter.close()

    return Readers(frappe, jira, calendar, documents, close)


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
