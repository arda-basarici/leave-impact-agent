"""The validator's composition: inputs authenticated, systems read, checks run, a verdict returned.

The order is the integrity chain the role allows (the decoders ruling at the validator
step). The manifest is decoded first and must be at ``projected``; its recorded digest
authenticates the raw world-spec bytes before they are decoded; the decoded spec's cited
digest authenticates the raw scenario-spec bytes before those are decoded; and the truth
manifest's digest, which both accessible artifacts record, is compared across them without
the truth ever being read. "Authenticates" means the artifacts are mutually consistent —
the same generator sealed and recorded them — not that an outside authority vouched for
them; it is the strongest check a reader of these three files can make. The two decoded
files are then joined by scenario id, no row unmatched on either side. All of that happens
before a single system is read, so a refused input costs no vendor call and is an
``IntegrityRefused``, never a finding: the inputs did not describe one sealed world, and
there is no world to judge.

Then the reads, as few as the claims need: each enumeration once, the windowed kinds once
over the world horizon for exactness and once per scenario window for the view, teams and
documents by id since neither port enumerates them, and the corpus's held ids through the
adapter's inspection outside the port, the one enumeration the investigator never makes
(the corpus ruling at the validator step). A source that cannot answer raises
``SourceUnreachable`` through, unhandled, as the projector does: a validation with a dead
system has nothing to record.

The checks run in their dependency order and a dependent check that cannot run says so.
Fidelity for a kind runs only over identities present on both sides and is not run when
that kind's exactness failed, since a set with holes cannot establish fidelity; a
scenario's view is not run when any kind the view derives from failed exactness, since a
foreign record has no planting to compare against. The wiring of real adapters from a
manifest and hosts is the entry point's, at the sealing step; this function takes the
readers it is handed.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from leaveimpact.adapters.manifest import (
    ArtifactRole,
    ManifestStage,
    WorldManifest,
    decode_manifest,
)
from leaveimpact.core.entities import Component, Employee, WorkItem
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import DocumentId
from leaveimpact.core.ports.observed import Entity, Observed
from leaveimpact.core.ports.read import (
    CalendarReader,
    DocumentReader,
    PeopleReader,
    WorkReader,
)
from leaveimpact.validator.checks import (
    CheckStatus,
    compare_identities,
    compare_records,
    compare_views,
    derive_live,
    expected_view,
    world_horizon,
)
from leaveimpact.validator.verdict import (
    VALIDATOR_VERSION,
    ExactnessResult,
    FidelityResult,
    ValidationVerdict,
    ViewResult,
)
from leaveimpact.world.artifacts import PlantedWorldSpec
from leaveimpact.world.decoders import decode_scenario_specs, decode_world_spec
from leaveimpact.world.runtime_view import events_within, leaves_within, window_instants
from leaveimpact.world.scenario import ScenarioSpec


class IntegrityRefused(ValueError):
    """The three inputs do not describe one sealed world; nothing was read."""


@dataclass(frozen=True, slots=True)
class LiveSystems:
    """The readers of one projected world, and the corpus's inspection outside its port."""

    people: PeopleReader
    work: WorkReader
    calendar: CalendarReader
    documents: DocumentReader
    held_document_ids: Callable[[], frozenset[DocumentId]]


VIEW_KINDS = (
    EntityKind.EMPLOYEE,
    EntityKind.COMPONENT,
    EntityKind.WORK_ITEM,
    EntityKind.LEAVE,
    EntityKind.EVENT,
)
"""The kinds a scenario's view derives from; their exactness gates the view."""


def validate(
    manifest_bytes: bytes,
    world_spec_bytes: bytes,
    scenario_specs_bytes: bytes,
    systems: LiveSystems,
) -> ValidationVerdict:
    """The verdict on the projection ``manifest_bytes`` records, against the sealed world.

    Refuses with ``IntegrityRefused`` before any read when the inputs are not one sealed
    world; otherwise reads the systems and returns a verdict, approved or refused, that
    lists every finding.
    """
    manifest = decode_manifest(manifest_bytes, stage=ManifestStage.PROJECTED)
    _authenticate(
        world_spec_bytes,
        manifest.digest_of(ArtifactRole.WORLD_SPEC),
        "the world spec",
        "the manifest",
    )
    spec = decode_world_spec(world_spec_bytes)
    _authenticate(
        scenario_specs_bytes, spec.scenario_specs_digest, "the scenario specs", "the world spec"
    )
    _cross_check(spec, manifest)
    specs = _joined(spec, decode_scenario_specs(scenario_specs_bytes))

    exactness, fidelity, enumerated = _records_checked(spec, specs, systems)
    exact = {result.check.kind for result in exactness if result.status is CheckStatus.PASSED}
    views = tuple(_view_checked(spec, one, systems, enumerated, exact) for one in specs)
    return ValidationVerdict(
        world_version=manifest.world_version,
        validator_version=VALIDATOR_VERSION,
        manifest_digest=hashlib.sha256(manifest_bytes).hexdigest(),
        artifacts=manifest.artifacts,
        exactness=exactness,
        fidelity=fidelity,
        views=views,
    )


# --- The integrity chain ------------------------------------------------------------------


def _authenticate(content: bytes, recorded: str, what: str, by: str) -> None:
    found = hashlib.sha256(content).hexdigest()
    if found != recorded:
        raise IntegrityRefused(
            f"{what} does not match the digest {by} records: got {found}, recorded {recorded}"
        )


def _cross_check(spec: PlantedWorldSpec, manifest: WorldManifest) -> None:
    """The two accessible artifacts agree on the other two digests, the truth's never read.

    The scenario specs are authenticated by the spec's digest, so the manifest's copy is
    compared here rather than trusted: the verdict carries the manifest's digests as its
    provenance, and a manifest recording another scenario-specs digest would otherwise
    put a file the validator never saw into an approved verdict.
    """
    for role, cited, what in (
        (ArtifactRole.SCENARIO_SPECS, spec.scenario_specs_digest, "scenario specs"),
        (ArtifactRole.TRUTH_MANIFEST, spec.truth_manifest_digest, "truth manifests"),
    ):
        recorded = manifest.digest_of(role)
        if cited != recorded:
            raise IntegrityRefused(
                f"the world spec and the manifest record different {what}: "
                f"{cited} against {recorded}"
            )
    if spec.generator_version != manifest.generator_version:
        raise IntegrityRefused(
            f"the world spec was generated by version {spec.generator_version}, the manifest "
            f"records {manifest.generator_version}"
        )
    if spec.org.params != manifest.org_params:
        raise IntegrityRefused("the world spec and the manifest record different org parameters")


def _joined(spec: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...]) -> tuple[ScenarioSpec, ...]:
    """The scenario specs in the spec's planting order; a row unmatched on either side refuses."""
    planted_ids = [planting.scenario_id for planting in spec.scenarios]
    by_id = {one.id: one for one in specs}
    missing = sorted(set(planted_ids) - set(by_id))
    surplus = sorted(set(by_id) - set(planted_ids))
    if missing or surplus:
        raise IntegrityRefused(
            f"the world spec and the scenario specs name different scenarios: "
            f"missing from the scenario specs {missing}, surplus {surplus}"
        )
    return tuple(by_id[id] for id in planted_ids)


# --- The record checks --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Enumerated:
    """The three whole enumerations, read once and reused by every scenario's view."""

    employees: tuple[Observed[Employee], ...]
    components: tuple[Observed[Component], ...]
    work_items: tuple[Observed[WorkItem], ...]


def _records_checked(
    spec: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...], systems: LiveSystems
) -> tuple[tuple[ExactnessResult, ...], tuple[FidelityResult, ...], _Enumerated]:
    days, instants = world_horizon(specs)
    owned = [row.owned for row in spec.scenarios]
    planted_leaves = [p for entities in owned for p in entities.leaves]
    planted_events = [p for entities in owned for p in entities.events]

    employees = systems.people.employees()
    components = systems.work.components()
    work_items = systems.work.work_items()
    leaves = systems.people.leaves_within(days)
    events = systems.calendar.events_within(instants)
    teams = _by_id(systems.people.team(team.id) for team in spec.org.teams)
    planted_documents = [p.entity for entities in owned for p in entities.documents]
    documents = _by_id(systems.documents.document(doc.id) for doc in planted_documents)
    held_documents = systems.held_document_ids()

    horizon = f"the world horizon {days.start}..{days.end}"
    kinds: list[
        tuple[EntityKind, str, Mapping[str, Entity], Mapping[str, Entity], Iterable[str]]
    ] = [
        (
            EntityKind.EMPLOYEE,
            "the company's employees, enumerated",
            _keyed(spec.org.employees),
            _observed(employees),
            _observed(employees),
        ),
        (
            EntityKind.TEAM,
            "by id; a foreign team is not observable through the port",
            _keyed(spec.org.teams),
            teams,
            teams,
        ),
        (
            EntityKind.COMPONENT,
            "the project's components, enumerated",
            _keyed(spec.org.components),
            _observed(components),
            _observed(components),
        ),
        (
            EntityKind.WORK_ITEM,
            "the project's work items, enumerated",
            _keyed(p.entity for entities in owned for p in entities.work_items),
            _observed(work_items),
            _observed(work_items),
        ),
        (
            EntityKind.LEAVE,
            f"leaves within {horizon}",
            _keyed(leaves_within(planted_leaves, days)),
            _observed(leaves),
            _observed(leaves),
        ),
        (
            EntityKind.EVENT,
            f"events within {horizon}",
            _keyed(events_within(planted_events, instants)),
            _observed(events),
            _observed(events),
        ),
        (
            EntityKind.DOCUMENT,
            "the corpus's documents under the world version, by inspection",
            _keyed(planted_documents),
            documents,
            held_documents,
        ),
    ]
    exactness: list[ExactnessResult] = []
    fidelity: list[FidelityResult] = []
    for kind, scope, expected, read_back, held in kinds:
        check = compare_identities(kind, expected.keys(), held)
        exactness.append(ExactnessResult(check, scope))
        if check.status is not CheckStatus.PASSED:
            fidelity.append(
                FidelityResult(kind, CheckStatus.NOT_RUN, reason="identity exactness failed")
            )
            continue
        mismatches = compare_records(expected, read_back)
        status = CheckStatus.PASSED if not mismatches else CheckStatus.FAILED
        fidelity.append(FidelityResult(kind, status, mismatches))
    return tuple(exactness), tuple(fidelity), _Enumerated(employees, components, work_items)


def _view_checked(
    spec: PlantedWorldSpec,
    one: ScenarioSpec,
    systems: LiveSystems,
    enumerated: _Enumerated,
    exact: set[EntityKind],
) -> ViewResult:
    failed = [kind.value for kind in VIEW_KINDS if kind not in exact]
    if failed:
        return ViewResult(
            one.id,
            one.today,
            CheckStatus.NOT_RUN,
            reason=f"identity exactness failed for {', '.join(failed)}",
        )
    today = one.today
    instants = window_instants(one.window, one.reference_timezone)
    # The enumerations are the record phase's reads; only the windowed reads are the
    # scenario's own, since the window query is what this layer exercises.
    live = frozenset(
        [
            *derive_live(enumerated.employees, today),
            *derive_live(enumerated.components, today),
            *derive_live(enumerated.work_items, today),
            *derive_live(systems.people.leaves_within(one.window), today),
            *derive_live(systems.calendar.events_within(instants), today),
        ]
    )
    disagreement = compare_views(one.id, today, expected_view(spec, one), live)
    if disagreement is None:
        return ViewResult(one.id, today, CheckStatus.PASSED)
    return ViewResult(one.id, today, CheckStatus.FAILED, disagreement)


# --- Shapes -------------------------------------------------------------------------------


def _keyed[T: Entity](records: Iterable[T]) -> dict[str, T]:
    return {record.id: record for record in records}


def _observed[T: Entity](records: Iterable[Observed[T]]) -> dict[str, T]:
    return {record.value.id: record.value for record in records}


def _by_id[T: Entity](records: Iterable[Observed[T] | None]) -> dict[str, T]:
    return {record.value.id: record.value for record in records if record is not None}
