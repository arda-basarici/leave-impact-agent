"""The composition root of projection: prepare, checkpoint, project, prove, promote.

One function, ``realize``, drives a world into the four systems and returns the manifest
that says it did. Its shape is the manifest-lifecycle ruling at the projector step made
executable. A previous manifest, when the store holds one, is the checkpoint the run resumes
from: it must realize the same world version and describe the same Frappe company and Jira
project the sites were just prepared with, or the run refuses before touching a vendor —
calendars belong to one world, and a configuration that drifted since the checkpoint means
the site is no longer the one the receipts describe. Then, one employee at a time, a
calendar is verified or created and the manifest saved, so an interrupted preparation
orphans at most one empty calendar. Then the two site inspections run as a preflight: the
Frappe company and the Jira project may hold a subset of this world's ids and nothing
outside it. Then the projectors run, every receipt checkpointed into the manifest before
the next external write. Then the same inspections run as a postflight, this time demanding
the exact set, the receipts are proven to cover every planted id, and only then does the
stage move to ``projected`` — the one write a validator or the application will accept.

The root holds policy and sequence; the facts come from two seams. ``Preparation`` is what
the root needs from the systems interleaved with its checkpoints: one calendar per call,
the four systems built from the final calendar map, and the two inspections. Everything
else preparation does — the site schema, the company, the skills, the project and its
mark, the field ids, the owner options, the corpus schema — happens before the root runs
and is idempotent on its own, so it needs no checkpoint and no interleaving; the wiring
in ``systems`` does it and hands the root the configuration it resolved. ``ManifestStore``
is durability: ``save`` returns only once the manifest would survive the process, which is
what makes "checkpointed before the next write" a true sentence.

A refusal here is ``ProjectionRefused``, distinct from the port faults on purpose: the
vendors answered and translated, the identities hold, and still the world is not this one
whole — another world's debris in the company or the project, a checkpoint of another
version, a planted id with no receipt. The last case is the residual window the projector
documents, a write that returned and died before its checkpoint, and the message says what
to do: delete the marked record and rerun. Nothing here adopts, overwrites or infers.

The names a world takes in the vendors are derived from its version, so no operator
chooses them and two worlds on one site cannot collide by choice: a key of a letter and
the first nine hex digits, valid for a Jira project key by construction and the prefix
every calendar summary carries; a Frappe company named by that key with the abbreviation
Frappe's five-character limit allows, a collision there refused by the vendor as a
duplicate abbreviation rather than caught here.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Protocol

from leaveimpact.adapters.calendar.adapter import CalendarConfig
from leaveimpact.adapters.corpus.adapter import CorpusConfig
from leaveimpact.adapters.frappe.adapter import FrappeConfig
from leaveimpact.adapters.jira.adapter import JiraConfig
from leaveimpact.adapters.manifest import (
    ArtifactDigest,
    ArtifactRole,
    ManifestStage,
    Receipts,
    SystemConfigs,
    WorldManifest,
    with_receipt,
)
from leaveimpact.core.entities import Employee
from leaveimpact.core.enums import Source
from leaveimpact.core.ids import EmployeeId, WorkItemId, WorldVersion
from leaveimpact.core.refs import EntityRef
from leaveimpact.generator.projection import (
    Systems,
    WorldEntities,
    project_world,
    world_entities,
)
from leaveimpact.world.artifacts import Bundle
from leaveimpact.world.assembly import WorldSpec


class ProjectionRefused(Exception):
    """The root will not project or promote: a checkpoint, a site or the coverage disagrees."""


class ManifestStore(Protocol):
    """Where the manifest lives between runs; ``save`` is durable before it returns."""

    def load(self) -> WorldManifest | None:
        """The stored manifest at any stage, or ``None`` when there is none."""
        ...

    def save(self, manifest: WorldManifest) -> None:
        """Persist ``manifest`` so it survives the process, replacing what was stored."""
        ...


class Preparation(Protocol):
    """What the root drives interleaved with its checkpoints, behind the adapters."""

    def ensure_calendar(self, employee: Employee, known: str | None) -> str:
        """The calendar id of ``employee``: ``known`` verified by a read, or a new one created."""
        ...

    def systems(self, calendars: CalendarConfig) -> Systems:
        """The four systems, the calendar one built on the final map."""
        ...

    def held_employee_numbers(self, world_ids: Iterable[EmployeeId]) -> frozenset[EmployeeId]:
        """The Frappe company's numbers, the site inspected past the company for collisions."""
        ...

    def held_markers(self) -> frozenset[WorkItemId]:
        """The Jira project's identity markers, debris refused."""
        ...


@dataclass(frozen=True, slots=True)
class Prepared:
    """What preparation resolved before the root runs, and the hosts it did so on."""

    frappe: FrappeConfig
    jira: JiraConfig
    observed_sites: Mapping[Source, str]


# --- The names a world takes ---------------------------------------------------------------


def world_key(version: WorldVersion) -> str:
    """``W`` and the first nine hex digits upper-cased: a Jira project key, a calendar prefix.

    >>> world_key(WorldVersion("0fbc9b09ef16f8b96614cb6838579b4d1a67e206754b647040bc1c6176aa86a9"))
    'W0FBC9B09E'
    """
    return "W" + version[:9].upper()


def jira_project_name(version: WorldVersion) -> str:
    """What Jira shows for the project; unconstrained, so it reads as a sentence."""
    return f"Leave Impact world {version[:8]}"


def frappe_company(version: WorldVersion) -> FrappeConfig:
    """The company a world occupies on the Frappe site, named by its key.

    >>> frappe_company(WorldVersion("0fbc9b09" * 8))
    FrappeConfig(company='World W0FBC9B090', company_abbr='W0FBC')
    """
    key = world_key(version)
    return FrappeConfig(f"World {key}", key[:5])


def artifact_digests(sealed: Bundle) -> tuple[ArtifactDigest, ...]:
    """The three digests of a sealed bundle by role, for the manifest to carry."""
    return (
        ArtifactDigest(ArtifactRole.WORLD_SPEC, sealed.world_spec.digest),
        ArtifactDigest(ArtifactRole.SCENARIO_SPECS, sealed.scenario_specs.digest),
        ArtifactDigest(ArtifactRole.TRUTH_MANIFEST, sealed.truth_manifest.digest),
    )


# --- The run ---------------------------------------------------------------------------------


def realize(
    world: WorldSpec,
    sealed: Bundle,
    prepared: Prepared,
    preparation: Preparation,
    store: ManifestStore,
) -> WorldManifest:
    """Project ``world`` into the prepared systems, checkpointing into ``store``; the manifest."""
    entities = world_entities(world)
    manifest = _starting_point(store.load(), world, sealed, prepared)
    store.save(manifest)

    employee_ids = frozenset(employee.id for employee in entities.employees)
    work_item_ids = frozenset(item.id for item in entities.work_items)
    calendars = dict(manifest.systems.calendar.calendar_by_employee)
    # The map is configuration the calendar adapter reads every entry of, so a foreign entry
    # would widen the application's read surface; it is scoped like a site, at both ends.
    check_scope(calendars, employee_ids, complete=False, what="the calendar map")
    for employee in entities.employees:
        known = calendars.get(employee.id)
        calendar_id = preparation.ensure_calendar(employee, known)
        if calendar_id != known:
            calendars[employee.id] = calendar_id
            manifest = _with_calendars(manifest, calendars)
            store.save(manifest)
    check_scope(calendars, employee_ids, complete=True, what="the calendar map")

    check_scope(
        preparation.held_employee_numbers(employee_ids),
        employee_ids,
        complete=False,
        what="the Frappe company",
    )
    check_scope(preparation.held_markers(), work_item_ids, complete=False, what="the Jira project")

    systems = preparation.systems(manifest.systems.calendar)

    def checkpoint(ref: EntityRef, locator: str) -> None:
        nonlocal manifest
        folded = with_receipt(manifest.receipts, ref, locator)
        if folded != manifest.receipts:
            manifest = replace(manifest, receipts=folded)
            store.save(manifest)

    project_world(entities, systems, checkpoint)

    check_scope(
        preparation.held_employee_numbers(employee_ids),
        employee_ids,
        complete=True,
        what="the Frappe company",
    )
    check_scope(preparation.held_markers(), work_item_ids, complete=True, what="the Jira project")
    check_coverage(manifest.receipts, entities)
    manifest = replace(manifest, stage=ManifestStage.PROJECTED)
    store.save(manifest)
    return manifest


def _starting_point(
    previous: WorldManifest | None, world: WorldSpec, sealed: Bundle, prepared: Prepared
) -> WorldManifest:
    """The checkpoint to resume from, verified against this world and site, or a fresh one.

    A fresh manifest is built from the world, the bundle and the preparation every time; a
    stored one contributes only what grew in it — the calendar map and the receipts — and
    only when its header says the same thing the fresh one does, field by field. The root
    holds every authoritative value, so a checkpoint hand-edited or assembled for another
    realization is refused here rather than carried into a promoted manifest. The observed
    hosts are the one field taken fresh without comparison: diagnostic, free to differ.
    """
    version = sealed.world_version
    fresh = WorldManifest(
        stage=ManifestStage.PREPARING,
        world_version=version,
        artifacts=artifact_digests(sealed),
        generator_version=world.generator_version,
        org_params=world.org.params,
        systems=SystemConfigs(
            frappe=prepared.frappe,
            jira=prepared.jira,
            calendar=CalendarConfig({}),
            corpus=CorpusConfig(version),
        ),
        receipts=Receipts(),
        observed_sites=prepared.observed_sites,
    )
    if previous is None:
        return fresh
    if previous.world_version != version:
        raise ProjectionRefused(
            f"the stored manifest realizes world {previous.world_version}, this run is "
            f"{version}: calendars and receipts belong to one world, give this one its own store"
        )
    drifted = [
        name
        for name, stored, current in (
            ("artifacts", previous.artifacts, fresh.artifacts),
            ("generator_version", previous.generator_version, fresh.generator_version),
            ("org_params", previous.org_params, fresh.org_params),
            ("frappe", previous.systems.frappe, fresh.systems.frappe),
            ("jira", previous.systems.jira, fresh.systems.jira),
            ("corpus", previous.systems.corpus, fresh.systems.corpus),
        )
        if stored != current
    ]
    if drifted:
        raise ProjectionRefused(
            f"the stored manifest disagrees with this run on {drifted}: the checkpoint is not "
            "this realization's, or the sites' configuration drifted since it was written"
        )
    systems = replace(fresh.systems, calendar=previous.systems.calendar)
    return replace(fresh, systems=systems, receipts=previous.receipts)


def _with_calendars(manifest: WorldManifest, calendars: Mapping[EmployeeId, str]) -> WorldManifest:
    systems = replace(manifest.systems, calendar=CalendarConfig(dict(calendars)))
    return replace(manifest, systems=systems)


def check_scope(
    held: Collection[str], expected: Collection[str], *, complete: bool, what: str
) -> None:
    """``held`` is a subset of ``expected``, and the whole of it when ``complete``; else refuse.

    Before projection a site may hold part of this world, a restart; after it the site holds
    exactly this world. Anything outside the world is another world's debris, refused at
    both ends — a site is one world's.

    >>> check_scope({"a"}, {"a", "b"}, complete=False, what="the site")
    >>> check_scope({"a", "c"}, {"a", "b"}, complete=False, what="a site")  # doctest: +ELLIPSIS
    Traceback (most recent call last):
    ...
    leaveimpact.generator.realize.ProjectionRefused: a site holds ids outside this world: ['c'] ...
    """
    extra = sorted(set(held) - set(expected))
    if extra:
        raise ProjectionRefused(
            f"{what} holds ids outside this world: {extra} — another world's debris, delete it "
            "before rerunning"
        )
    missing = sorted(set(expected) - set(held))
    if complete and missing:
        raise ProjectionRefused(f"{what} lacks {missing} after projection")


def check_coverage(receipts: Receipts, entities: WorldEntities) -> None:
    """Exactly the planted ids have receipts, or refuse naming the ones missing or foreign."""
    receipted: set[str] = set()
    for held in (
        receipts.people.teams,
        receipts.people.employees,
        receipts.people.leaves,
        receipts.work.components,
        receipts.work.work_items,
        receipts.calendar.events,
        receipts.documents.documents,
    ):
        receipted.update(held)
    planted = {
        entity.id
        for kind in (
            entities.teams,
            entities.employees,
            entities.leaves,
            entities.components,
            entities.work_items,
            entities.events,
            entities.documents,
        )
        for entity in kind
    }
    missing = sorted(planted - receipted)
    if missing:
        raise ProjectionRefused(
            f"no receipt for {missing}: written and never checkpointed, or never written — "
            "delete the marked records and rerun"
        )
    foreign = sorted(receipted - planted)
    if foreign:
        raise ProjectionRefused(
            f"receipts for ids this world never planted: {foreign} — the checkpoint is not "
            "this realization's"
        )
