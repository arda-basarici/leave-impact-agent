"""The world manifest: the projection's receipt, and where every reader of a projected world starts.

This module owns the portable configuration-and-receipt contract for the projected
external systems — not world truth, and not projection orchestration. A manifest carries
what preparation resolved (the Frappe company, the Jira project key and its four custom
field ids, the employee-to-calendar map, the corpus world version), one locator per
projected domain id in every system, and enough provenance to name the world it realized:
the world version, the digests of the three sealed artifacts keyed by role, the generator
version and the organization parameters. It is written by the generator alone and decoded
by the generator's own restart, by the validator and by the application, each of which
builds its adapters from the configuration here. Rank 2 is the lowest package that can
type all of it: the configuration types are the adapters', the provenance types are
``world``'s, and every reader above may import both (the manifest's-home ruling at the
projector step).

Three things are structurally absent, and the tests hold the door. No credential: an
adapter is built from a credential, a configuration and a transport policy as three
separate values, and only the configuration is recorded — the base URLs and the database
DSN are host configuration from the environment for the same reason, so ``observed_sites``
names the hosts for a human's diagnosis and never for a consumer's configuration. No seed:
the application holds the generator code, and the seed with the parameters regenerates the
plan, which names the planted traps; the seed lives in the benchmark-private world spec
only. No entity, key or fact type: the record's fields are configurations, id-to-locator
strings and provenance, so deleting the manifest after identity resolution loses nothing
that can change a scenario's answer (DESIGN, "Benchmark state is split by audience and
authority").

The manifest is also the projection's durable checkpoint, so its lifecycle is explicit
and has two stages. Under ``preparing`` configuration and receipts may both be partial:
the calendar map grows one person at a time, persisted after each obtained id, so an
interrupted attempt orphans at most one empty calendar; the receipts grow one write at a
time, folded in as the projectors report each locator, so a later failure cannot lose an
earlier write's receipt. A preparing manifest is never served. ``projected`` means the
configuration is resolved, the receipts cover every entity the world plants, the
post-projection guards passed, and the manifest may be served; the composition root
asserts the coverage, because only the world knows which ids exist. A decoder states the
stage its caller can accept: the generator's restart takes either, the validator and the
application require ``projected`` and refuse a checkpoint by name. A manifest is keyed by
the world version it realized, and a reader handed one of another version refuses before
using any recorded id (the manifest-lifecycle ruling at the projector step).

Receipts are one locator per domain id per system, every entity kind alike, derived ids
included: what was projected, in one place, whatever minted the id. The calendar's receipt
is the derived vendor event id shared by every attendee's copy — a copy's address is that
id on a calendar already in the configuration map, so multiplicity is derivable and not
stored. The bytes are canonical JSON under ``core``'s one byte rule, with every mapping
sorted by key, so the file is a property of the manifest's value and never of the order
projection happened to run in; the manifest sits outside the world hash, so nothing here
feeds the world version.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType

from leaveimpact.adapters.calendar.adapter import CalendarConfig
from leaveimpact.adapters.corpus.adapter import CorpusConfig
from leaveimpact.adapters.frappe.adapter import FrappeConfig
from leaveimpact.adapters.jira.adapter import JiraConfig, JiraFields
from leaveimpact.core.enums import EntityKind, Source
from leaveimpact.core.ids import (
    ComponentId,
    DocumentId,
    EmployeeId,
    EventId,
    LeaveId,
    TeamId,
    WorkItemId,
    WorldVersion,
    is_numbered_id,
)
from leaveimpact.core.jsonshape import (
    JsonObject,
    array_field,
    as_object,
    canonical_bytes,
    expect_fields,
    integer_field,
    object_field,
    string_field,
)
from leaveimpact.core.refs import EntityRef
from leaveimpact.world.artifacts import SCENARIO_SPECS, TRUTH_MANIFEST, WORLD_SPEC
from leaveimpact.world.org import OrgParams, decode_org_params, encode_org_params
from leaveimpact.world.version import GeneratorVersion

MANIFEST_FORMAT = 1
"""The manifest's own schema version; a reader refuses any other."""

MANIFEST_FILE = "world-manifest.json"

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class ManifestStage(StrEnum):
    """Where the manifest is in its life: a checkpoint of preparation, or an accepted projection."""

    PREPARING = "preparing"
    PROJECTED = "projected"


class ArtifactRole(StrEnum):
    """The three sealed artifacts by role: a digest is "the truth manifest's", not a file name's."""

    WORLD_SPEC = "world_spec"
    SCENARIO_SPECS = "scenario_specs"
    TRUTH_MANIFEST = "truth_manifest"


FILE_NAME_BY_ROLE: Mapping[ArtifactRole, str] = MappingProxyType(
    {
        ArtifactRole.WORLD_SPEC: WORLD_SPEC,
        ArtifactRole.SCENARIO_SPECS: SCENARIO_SPECS,
        ArtifactRole.TRUTH_MANIFEST: TRUTH_MANIFEST,
    }
)


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    """One sealed artifact's SHA-256, keyed by its role.

    The file name is the role's, not a second field: the world version hashes each file
    under its fixed name, so a receipt naming the truth manifest's digest under the world
    spec's file would be a contradiction nothing downstream could resolve. The encoded
    form carries the name beside the role for a human reading the file, and the decoder
    refuses a name that is not the role's.
    """

    role: ArtifactRole
    digest: str

    def __post_init__(self) -> None:
        if not _SHA256_HEX.fullmatch(self.digest):
            raise ValueError(f"{self.role.value} digest is a SHA-256 hex, got {self.digest!r}")

    @property
    def file_name(self) -> str:
        """The name the artifact is sealed under, fixed per role."""
        return FILE_NAME_BY_ROLE[self.role]


@dataclass(frozen=True, slots=True)
class SystemConfigs:
    """The resolved configuration of the four adapters, as preparation produced it."""

    frappe: FrappeConfig
    jira: JiraConfig
    calendar: CalendarConfig
    corpus: CorpusConfig


def _frozen[K: str](mapping: Mapping[K, str]) -> Mapping[K, str]:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True, slots=True)
class PeopleReceipts:
    """Locators in the HR system, by domain id."""

    teams: Mapping[TeamId, str] = field(default_factory=dict[TeamId, str])
    employees: Mapping[EmployeeId, str] = field(default_factory=dict[EmployeeId, str])
    leaves: Mapping[LeaveId, str] = field(default_factory=dict[LeaveId, str])

    def __post_init__(self) -> None:
        object.__setattr__(self, "teams", _frozen(self.teams))
        object.__setattr__(self, "employees", _frozen(self.employees))
        object.__setattr__(self, "leaves", _frozen(self.leaves))


@dataclass(frozen=True, slots=True)
class WorkReceipts:
    """Locators in the issue tracker, by domain id."""

    components: Mapping[ComponentId, str] = field(default_factory=dict[ComponentId, str])
    work_items: Mapping[WorkItemId, str] = field(default_factory=dict[WorkItemId, str])

    def __post_init__(self) -> None:
        object.__setattr__(self, "components", _frozen(self.components))
        object.__setattr__(self, "work_items", _frozen(self.work_items))


@dataclass(frozen=True, slots=True)
class CalendarReceipts:
    """Locators in the calendar, by domain id: the derived vendor id every copy shares."""

    events: Mapping[EventId, str] = field(default_factory=dict[EventId, str])

    def __post_init__(self) -> None:
        object.__setattr__(self, "events", _frozen(self.events))


@dataclass(frozen=True, slots=True)
class DocumentReceipts:
    """Locators in the corpus, by domain id."""

    documents: Mapping[DocumentId, str] = field(default_factory=dict[DocumentId, str])

    def __post_init__(self) -> None:
        object.__setattr__(self, "documents", _frozen(self.documents))


@dataclass(frozen=True, slots=True)
class Receipts:
    """What projection wrote, per system; grows one fold at a time while the manifest prepares."""

    people: PeopleReceipts = field(default_factory=PeopleReceipts)
    work: WorkReceipts = field(default_factory=WorkReceipts)
    calendar: CalendarReceipts = field(default_factory=CalendarReceipts)
    documents: DocumentReceipts = field(default_factory=DocumentReceipts)


@dataclass(frozen=True, slots=True)
class WorldManifest:
    """The receipt of one projected world, at one stage of its life.

    Construction refuses a digest set that is not exactly the three roles once each and a
    corpus configuration scoped to another world version than the manifest's own: the
    inconsistencies a hand-edited or mis-assembled manifest could carry that no field type
    catches. Partial receipts are legitimate at either stage as far as this record knows. The
    artifacts are kept in the world's hashing order whatever order they were given in, so
    two manifests of one world compare equal. Completeness of the receipts is the
    composition root's to assert, because only the world knows which ids exist.
    """

    stage: ManifestStage
    world_version: WorldVersion
    artifacts: tuple[ArtifactDigest, ...]
    generator_version: GeneratorVersion
    org_params: OrgParams
    systems: SystemConfigs
    receipts: Receipts = field(default_factory=Receipts)
    observed_sites: Mapping[Source, str] = MappingProxyType({})

    def __post_init__(self) -> None:
        if not _SHA256_HEX.fullmatch(self.world_version):
            raise ValueError(f"world version is a SHA-256 hex, got {self.world_version!r}")
        roles = [artifact.role for artifact in self.artifacts]
        if sorted(roles) != sorted(ArtifactRole):
            raise ValueError(
                f"artifact digests must name each of {[role.value for role in ArtifactRole]} "
                f"exactly once, got {[role.value for role in roles]}"
            )
        order = list(ArtifactRole)
        object.__setattr__(
            self,
            "artifacts",
            tuple(sorted(self.artifacts, key=lambda artifact: order.index(artifact.role))),
        )
        if self.systems.corpus.world_version != self.world_version:
            raise ValueError(
                f"the corpus configuration is scoped to {self.systems.corpus.world_version}, "
                f"the manifest realizes {self.world_version}"
            )
        object.__setattr__(self, "observed_sites", MappingProxyType(dict(self.observed_sites)))

    def digest_of(self, role: ArtifactRole) -> str:
        """The recorded digest of the artifact in ``role``."""
        (found,) = (artifact for artifact in self.artifacts if artifact.role is role)
        return found.digest


def with_receipt(receipts: Receipts, ref: EntityRef, locator: str) -> Receipts:
    """``receipts`` with ``locator`` recorded for ``ref``; the fold the composition root persists.

    The same pair again is a no-op, so the calendar re-reporting its derived id on every run
    costs nothing; a different locator for an id already held refuses, since one identity has
    one place in a system. An empty locator refuses here, at the one seam every receipt
    crosses, so the manifest can never hold a value its own decoder rejects. A kind no system
    receipts — a clause, a comment — is a caller's bug.

    >>> from leaveimpact.core.refs import team_ref
    >>> from leaveimpact.core.ids import team_id
    >>> folded = with_receipt(Receipts(), team_ref(team_id(1)), "Department/Platform - WA1")
    >>> dict(folded.people.teams)
    {'team_001': 'Department/Platform - WA1'}
    """
    if not locator:
        raise ValueError(f"the locator of {ref} is a non-empty string, got {locator!r}")
    people, work, calendar, documents = (
        receipts.people,
        receipts.work,
        receipts.calendar,
        receipts.documents,
    )
    match ref.kind:
        case EntityKind.TEAM:
            people = replace(people, teams=_held(people.teams, TeamId(ref.id), locator, ref))
        case EntityKind.EMPLOYEE:
            people = replace(
                people, employees=_held(people.employees, EmployeeId(ref.id), locator, ref)
            )
        case EntityKind.LEAVE:
            people = replace(people, leaves=_held(people.leaves, LeaveId(ref.id), locator, ref))
        case EntityKind.COMPONENT:
            work = replace(
                work, components=_held(work.components, ComponentId(ref.id), locator, ref)
            )
        case EntityKind.WORK_ITEM:
            work = replace(
                work, work_items=_held(work.work_items, WorkItemId(ref.id), locator, ref)
            )
        case EntityKind.EVENT:
            calendar = replace(
                calendar, events=_held(calendar.events, EventId(ref.id), locator, ref)
            )
        case EntityKind.DOCUMENT:
            documents = replace(
                documents,
                documents=_held(documents.documents, DocumentId(ref.id), locator, ref),
            )
        case _:
            raise ValueError(f"no system receipts a {ref.kind.value}: {ref}")
    return Receipts(people, work, calendar, documents)


def _held[K: str](held: Mapping[K, str], id: K, locator: str, ref: EntityRef) -> dict[K, str]:
    known = held.get(id)
    if known is not None and known != locator:
        raise ValueError(f"{ref} is already receipted at {known!r}, got {locator!r}")
    return {**held, id: locator}


# --- Encoding -------------------------------------------------------------------------


def encode_manifest(manifest: WorldManifest) -> JsonObject:
    """The JSON object of ``manifest``: header first, artifacts in hashing order, maps sorted."""
    systems = manifest.systems
    receipts = manifest.receipts
    return {
        "format": MANIFEST_FORMAT,
        "stage": manifest.stage.value,
        "world_version": manifest.world_version,
        "artifacts": [
            {
                "role": artifact.role.value,
                "file_name": artifact.file_name,
                "digest": artifact.digest,
            }
            for artifact in manifest.artifacts
        ],
        "generator_version": manifest.generator_version,
        "org_params": encode_org_params(manifest.org_params),
        "systems": {
            "frappe": {
                "company": systems.frappe.company,
                "company_abbr": systems.frappe.company_abbr,
            },
            "jira": {
                "project_key": systems.jira.project_key,
                "fields": {
                    "ticket_id": systems.jira.fields.ticket_id,
                    "owner": systems.jira.fields.owner,
                    "opened_on": systems.jira.fields.opened_on,
                    "resolved_on": systems.jira.fields.resolved_on,
                },
            },
            "calendar": {"calendar_by_employee": _sorted(systems.calendar.calendar_by_employee)},
            "corpus": {"world_version": systems.corpus.world_version},
        },
        "receipts": {
            "people": {
                "teams": _sorted(receipts.people.teams),
                "employees": _sorted(receipts.people.employees),
                "leaves": _sorted(receipts.people.leaves),
            },
            "work": {
                "components": _sorted(receipts.work.components),
                "work_items": _sorted(receipts.work.work_items),
            },
            "calendar": {"events": _sorted(receipts.calendar.events)},
            "documents": {"documents": _sorted(receipts.documents.documents)},
        },
        "observed_sites": {
            source.value: host
            for source, host in sorted(manifest.observed_sites.items(), key=lambda item: item[0])
        },
    }


def manifest_bytes(manifest: WorldManifest) -> bytes:
    """The canonical bytes of ``manifest`` — what the generator writes and a reader decodes."""
    return canonical_bytes(encode_manifest(manifest))


def _sorted[K: str](mapping: Mapping[K, str]) -> JsonObject:
    return {key: mapping[key] for key in sorted(mapping)}


# --- Decoding -------------------------------------------------------------------------


def decode_manifest(content: bytes | str, *, stage: ManifestStage | None) -> WorldManifest:
    """The manifest ``content`` encodes, refused unless it is at ``stage``.

    ``stage`` is what the caller can act on: the validator and the application pass
    ``PROJECTED``, because a checkpoint of an unfinished projection is not a world to
    verify or serve; the generator's own restart passes ``None`` and takes either. Every
    field is checked for shape here and for meaning by the domain constructors, so a
    manifest that decodes is one an adapter can be built from.
    """
    data = as_object(json.loads(content), "the world manifest")
    expect_fields(
        data,
        (
            "format",
            "stage",
            "world_version",
            "artifacts",
            "generator_version",
            "org_params",
            "systems",
            "receipts",
            "observed_sites",
        ),
        "the world manifest",
    )
    fmt = integer_field(data, "format")
    if fmt != MANIFEST_FORMAT:
        raise ValueError(f"the world manifest is format {MANIFEST_FORMAT}, got {fmt}")
    found_stage = ManifestStage(string_field(data, "stage"))
    if stage is not None and found_stage is not stage:
        raise ValueError(
            f"the world manifest is at stage {found_stage.value}, {stage.value} required: "
            "a checkpoint of an unfinished projection is not a projected world"
        )
    systems = object_field(data, "systems")
    receipts = object_field(data, "receipts")
    return WorldManifest(
        stage=found_stage,
        world_version=WorldVersion(string_field(data, "world_version")),
        artifacts=tuple(_artifact(item) for item in array_field(data, "artifacts")),
        generator_version=GeneratorVersion(string_field(data, "generator_version")),
        org_params=decode_org_params(object_field(data, "org_params")),
        systems=_systems(systems),
        receipts=_receipts(receipts),
        observed_sites=_sites(object_field(data, "observed_sites")),
    )


def _artifact(item: object) -> ArtifactDigest:
    data = as_object(item, "an artifact digest")
    expect_fields(data, ("role", "file_name", "digest"), "an artifact digest")
    digest = ArtifactDigest(ArtifactRole(string_field(data, "role")), string_field(data, "digest"))
    file_name = string_field(data, "file_name")
    if file_name != digest.file_name:
        raise ValueError(
            f"the {digest.role.value} artifact is sealed as {digest.file_name}, got {file_name!r}"
        )
    return digest


def _systems(data: Mapping[str, object]) -> SystemConfigs:
    expect_fields(data, ("frappe", "jira", "calendar", "corpus"), "systems")
    frappe = object_field(data, "frappe")
    expect_fields(frappe, ("company", "company_abbr"), "the frappe configuration")
    jira = object_field(data, "jira")
    expect_fields(jira, ("project_key", "fields"), "the jira configuration")
    jira_fields = object_field(jira, "fields")
    expect_fields(
        jira_fields, ("ticket_id", "owner", "opened_on", "resolved_on"), "the jira fields"
    )
    calendar = object_field(data, "calendar")
    expect_fields(calendar, ("calendar_by_employee",), "the calendar configuration")
    corpus = object_field(data, "corpus")
    expect_fields(corpus, ("world_version",), "the corpus configuration")
    return SystemConfigs(
        frappe=FrappeConfig(string_field(frappe, "company"), string_field(frappe, "company_abbr")),
        jira=JiraConfig(
            string_field(jira, "project_key"),
            JiraFields(
                ticket_id=string_field(jira_fields, "ticket_id"),
                owner=string_field(jira_fields, "owner"),
                opened_on=string_field(jira_fields, "opened_on"),
                resolved_on=string_field(jira_fields, "resolved_on"),
            ),
        ),
        calendar=CalendarConfig(
            _ids(object_field(calendar, "calendar_by_employee"), "emp", EmployeeId)
        ),
        corpus=CorpusConfig(WorldVersion(string_field(corpus, "world_version"))),
    )


def _receipts(data: Mapping[str, object]) -> Receipts:
    expect_fields(data, ("people", "work", "calendar", "documents"), "receipts")
    people = object_field(data, "people")
    expect_fields(people, ("teams", "employees", "leaves"), "people receipts")
    work = object_field(data, "work")
    expect_fields(work, ("components", "work_items"), "work receipts")
    calendar = object_field(data, "calendar")
    expect_fields(calendar, ("events",), "calendar receipts")
    documents = object_field(data, "documents")
    expect_fields(documents, ("documents",), "document receipts")
    return Receipts(
        people=PeopleReceipts(
            teams=_ids(object_field(people, "teams"), "team", TeamId),
            employees=_ids(object_field(people, "employees"), "emp", EmployeeId),
            leaves=_ids(object_field(people, "leaves"), "leave", LeaveId),
        ),
        work=WorkReceipts(
            components=_ids(object_field(work, "components"), "comp", ComponentId),
            work_items=_ids(object_field(work, "work_items"), "ticket", WorkItemId),
        ),
        calendar=CalendarReceipts(events=_ids(object_field(calendar, "events"), "event", EventId)),
        documents=DocumentReceipts(
            documents=_ids(object_field(documents, "documents"), "doc", DocumentId)
        ),
    )


def _ids[K: str](data: Mapping[str, object], prefix: str, kind: Callable[[str], K]) -> dict[K, str]:
    """A mapping whose keys are ids of one kind and whose values are locator strings."""
    result: dict[K, str] = {}
    for key, value in data.items():
        if not is_numbered_id(key) or not key.startswith(f"{prefix}_"):
            raise ValueError(f"{key!r} is not a {prefix}_ id")
        if not isinstance(value, str) or not value:
            raise ValueError(f"the locator of {key} is a non-empty string, got {value!r}")
        result[kind(key)] = value
    return result


def _sites(data: Mapping[str, object]) -> dict[Source, str]:
    return {Source(name): string_field(data, name) for name in data}
