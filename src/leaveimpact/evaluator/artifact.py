"""The evaluation artifact: one evaluation of an explicit set of stored runs, as plain data, and
the pure function that produces it.

An evaluation is over a snapshot (the investigator milestone's sixth build step, ruling 7).
Its caller lists the objects stored for a world's runs and gives every one of them here,
with the store's version id of each; every one comes back in the artifact's inventory with
what it is, what it cost and exactly one reason for being in or out of the tables. Nothing
listed is dropped: a run that contributes no estimate was still paid for, and an inventory
that only held the runs that counted would read as a smaller experiment.

*Which runs enter the tables.* A run is eligible when it was made under the registration
this evaluation reads, and that takes two things. The registration file at the commit the
export cites has the same bytes as the evaluator's own, which shows the two were declared
alike. And what the export records of its own execution is what the registration says: the
system and its variant, an arm the registration holds, the outage schedule's digest, the
caps, the prefetch rule, the retrieval, and for a system that calls a model its
configuration, its prompts and its tool surface. Equal bytes alone would show matching
declarations and nothing about what ran. A system with a value still pending has nothing to
be compared with, so its runs are not eligible. Under a frozen registration the harness's
tree is clean as well. A run that fails any of these keeps its grade and its cost in the
inventory and enters no table; so does one whose cited commit resolves to no registration,
which is classified unknown.

Two things are not runs of this evaluation at all and are kept all the same: an object
that does not decode as an export, with nothing more to say of it, and an export of another
world, with its cost.

*What refuses the whole evaluation.* Two eligible exports that carry one run and attempt
make the set ambiguous, and a registration this evaluator cannot read as a plan (a name it
does not hold, a prefetch it does not plan) is incompatible; both raise, since tables cut
from either would look complete and be about something else. A set that is merely short
does not raise: the analysis builds every registered arm and scenario and shows the
shortfall.

*The label* is derived here and stored, never read from an export. A draft registration
gives a development evaluation. A frozen one gives a reported evaluation, or an
exploratory one when the registration declares that it amends an earlier one and that
full-set results on this world existed when it was written. Those two statements are the
registration's author's and nothing here can check them, so the artifact carries them as
declared. An evaluation under a frozen registration by an evaluator whose implementation
changed since the registration's commit says so beside its label; whether a change was
maintenance or a change to a metric is a judgment for the report.

Reading the store, resolving a commit and refusing a dirty evaluator tree are the entry
point's. This module takes bytes and gives data; ``cited_commits`` says which commits the
entry point must resolve before the artifact can be made.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.provenance import ModelConfiguration
from leaveimpact.core.registration import (
    AgentSystem,
    Amendment,
    Pending,
    RegisteredArm,
    RegisteredSystem,
    Registration,
    RegistrationStatus,
    RulesOnlySystem,
    SingleShotSystem,
    condition_id,
    schedule_digest,
)
from leaveimpact.core.registration_json import decode_registration_bytes
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_export_json import decode_export_bytes
from leaveimpact.core.run_record import PrefetchRule, RunRecord, TreeState
from leaveimpact.evaluator.analysis import Analysis, analyse
from leaveimpact.evaluator.cost_check import CostCheck, check_cost
from leaveimpact.evaluator.sealed_world import SealedSource, SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world.artifacts import digest

ARTIFACT_FORMAT_VERSION = 1
"""The format of the evaluation artifact as this code writes it."""


class Label(StrEnum):
    """What kind of evidence an evaluation, or one run in it, is; a member is the wire format."""

    DEVELOPMENT = "development"
    REPORTED = "reported"
    EXPLORATORY = "exploratory"
    UNKNOWN = "unknown"
    """Of a run only: its cited commit resolves to no registration."""


class Disposition(StrEnum):
    """Why a listed object is in or out of the tables; a member is the wire format."""

    ELIGIBLE = "eligible"
    NOT_AN_EXPORT = "not_an_export"
    ANOTHER_WORLD = "another_world"
    REGISTRATION_NOT_RESOLVED = "registration_not_resolved"
    ANOTHER_REGISTRATION = "another_registration"
    SETTINGS_DIFFER = "settings_differ"
    DIRTY_HARNESS = "dirty_harness"


class RecordedSetting(StrEnum):
    """What an export records of its execution that the registration fixes."""

    SYSTEM = "system"
    ARM = "arm"
    OUTAGE_SCHEDULE = "outage_schedule"
    CAPS = "caps"
    PREFETCH = "prefetch"
    RETRIEVAL = "retrieval"
    MODEL = "model"
    PROMPTS = "prompts"
    TOOL_SURFACE = "tool_surface"
    PENDING = "pending"
    """The registered system has a value still pending, so nothing can be compared."""


@dataclass(frozen=True, slots=True)
class StoredRun:
    """One object as the store listed and returned it: its key, the version id read, its bytes."""

    key: str
    version_id: str
    content: bytes


@dataclass(frozen=True, slots=True)
class ChangedPath:
    """One path of the evaluator's implementation that differs between two commits, by the
    identity of its content at each; ``None`` where the path does not exist."""

    path: str
    before: str | None
    after: str | None


@dataclass(frozen=True, slots=True)
class EvaluatorRevision:
    """The evaluator as it ran: its commit, the commit its registration file was last
    changed at, and the paths of its declared implementation that changed between the two."""

    commit: str
    registration_commit: str
    changed: tuple[ChangedPath, ...]


@dataclass(frozen=True, slots=True)
class InventoryEntry:
    """One listed object and what this evaluation made of it.

    ``digest`` is the SHA-256 of the bytes read. ``evaluation`` is the run's own grading,
    present for every export of this world, in or out of the tables. ``cost`` is the cost
    recomputed from the export, present for every object that decodes as one.
    ``differing`` names the settings that differ, set exactly for that disposition.
    ``label`` is the evaluation's own for an eligible run, unknown for one whose
    registration did not resolve, and absent otherwise: a run made under another
    registration is not this evaluation's to label.
    """

    key: str
    version_id: str
    digest: str
    disposition: Disposition
    differing: tuple[RecordedSetting, ...]
    label: Label | None
    evaluation: Evaluation | None
    cost: CostCheck | None

    def __post_init__(self) -> None:
        if bool(self.differing) != (self.disposition is Disposition.SETTINGS_DIFFER):
            raise ValueError("the differing settings are named exactly when settings differ")


@dataclass(frozen=True, slots=True)
class RegistrationRead:
    """The registration an evaluation was made under: its status, the SHA-256 of its bytes,
    and what its author declares of its history, which nothing here verified."""

    status: RegistrationStatus
    digest: str
    declared: Amendment


@dataclass(frozen=True, slots=True)
class WorldRead:
    """The sealed world an evaluation graded against, by its version and where each of its
    three files was read from."""

    version: str
    world_spec: SealedSource
    scenario_specs: SealedSource
    truth_manifest: SealedSource


@dataclass(frozen=True, slots=True)
class EvaluationArtifact:
    """One evaluation: what was read, what every listed object is, and the registered tables
    over the eligible runs. ``inventory`` is in key order."""

    format_version: int
    label: Label
    evaluated_by_changed_code: bool
    world: WorldRead
    evaluator: EvaluatorRevision
    registration: RegistrationRead
    inventory: tuple[InventoryEntry, ...]
    analysis: Analysis


class AmbiguousRuns(ValueError):
    """Two eligible exports carry one run and attempt; the message names their keys only."""


def cited_commits(runs: Sequence[StoredRun]) -> tuple[str, ...]:
    """The preregistration commits the exports among ``runs`` cite, each once, in order: what
    the caller resolves to registration bytes before the artifact is made."""
    commits: list[str] = []
    for run in runs:
        export = _decoded(run)
        if export is not None:
            commits.append(export.record.preregistration_commit)
    return tuple(dict.fromkeys(commits))


def evaluation_artifact(
    world: SealedWorld,
    registration_content: bytes,
    runs: Sequence[StoredRun],
    registrations_at: Mapping[str, bytes | None],
    evaluator: EvaluatorRevision,
) -> EvaluationArtifact:
    """The evaluation of ``runs`` against ``world`` under the registration whose bytes are
    ``registration_content``.

    ``registrations_at`` gives, for a cited commit, the registration file's bytes at it, or
    ``None`` (or no entry) when the commit resolves to none. Raises ``ValueError`` for a
    registration that does not decode or that this evaluator cannot read as a plan, and
    ``AmbiguousRuns`` for two eligible exports of one run and attempt.
    """
    registration = decode_registration_bytes(registration_content)
    frozen = registration.status is RegistrationStatus.FROZEN
    label = _label(registration)
    inventory = tuple(
        _entry(world, run, registration, registration_content, registrations_at, label)
        for run in sorted(runs, key=lambda run: run.key)
    )
    eligible = [entry for entry in inventory if entry.disposition is Disposition.ELIGIBLE]
    _require_unambiguous(eligible)
    evaluations = [entry.evaluation for entry in eligible if entry.evaluation is not None]
    return EvaluationArtifact(
        format_version=ARTIFACT_FORMAT_VERSION,
        label=label,
        evaluated_by_changed_code=frozen and bool(evaluator.changed),
        world=WorldRead(
            world.version, world.world_spec, world.scenario_specs, world.truth_manifest
        ),
        evaluator=evaluator,
        registration=RegistrationRead(
            registration.status, digest(registration_content), registration.amendment
        ),
        inventory=inventory,
        analysis=analyse(world, evaluations, registration),
    )


def setting_differences(
    registration: Registration, record: RunRecord
) -> tuple[RecordedSetting, ...]:
    """The settings ``record`` states that are not what ``registration`` fixes, in the
    declared order; empty when the run executed as registered."""
    system = registration.system(record.system.kind)
    if system is None:
        return (RecordedSetting.SYSTEM,)
    model = _model_settings(system)
    if isinstance(system.variant, Pending) or model is None:
        return (RecordedSetting.PENDING,)
    registered = registration.prefetch
    condition = condition_id(record.outage.scheduled_unreachable)
    recorded = _ModelSettings(
        frozenset(configuration for _, configuration in record.model_configurations),
        frozenset(_prompts_by_role(record).values()),
        frozenset(surface for _, surface in record.tool_surface_digests),
    )
    same = {
        RecordedSetting.SYSTEM: system.variant == record.system.variant,
        RecordedSetting.ARM: RegisteredArm(record.system.kind, condition) in registration.arms,
        RecordedSetting.OUTAGE_SCHEDULE: (
            record.outage.schedule_digest == schedule_digest(registration.outage)
        ),
        RecordedSetting.CAPS: record.caps == registration.caps.caps,
        RecordedSetting.PREFETCH: (
            record.prefetch_rule == PrefetchRule(registered.identifier, registered.digest)
        ),
        RecordedSetting.RETRIEVAL: record.retrieval == system.retrieval,
        RecordedSetting.MODEL: recorded.models == model.models,
        RecordedSetting.PROMPTS: recorded.prompts == model.prompts,
        RecordedSetting.TOOL_SURFACE: recorded.surfaces == model.surfaces,
    }
    return tuple(setting for setting, holds in same.items() if not holds)


@dataclass(frozen=True, slots=True)
class _ModelSettings:
    """What a system's model calls ran under, as sets over its roles: a record indexes them
    by role and the registration holds one of each per system, so every role's must be the
    registered one. ``prompts`` holds each role's whole prompt set as one member; pooled
    over roles, two roles holding half the registered set each would pass for it."""

    models: frozenset[ModelConfiguration]
    prompts: frozenset[frozenset[tuple[str, str]]]
    surfaces: frozenset[str]


def _model_settings(system: RegisteredSystem) -> _ModelSettings | None:
    """The model settings ``system`` registers, none for a system that calls no model and no
    tool surface for one that is given no tools; ``None`` while any of them is pending."""
    match system:
        case RulesOnlySystem():
            return _ModelSettings(frozenset(), frozenset(), frozenset())
        case AgentSystem():
            surface = system.tool_surface_digest
            if (
                isinstance(system.model, Pending)
                or isinstance(system.prompt_digests, Pending)
                or isinstance(surface, Pending)
            ):
                return None
            return _ModelSettings(
                frozenset({system.model}),
                frozenset({frozenset(system.prompt_digests)}),
                frozenset({surface}),
            )
        case SingleShotSystem():
            # Its query protocol is only ever pending in this registration format.
            return None


def _prompts_by_role(record: RunRecord) -> dict[str, frozenset[tuple[str, str]]]:
    """Each role's prompts as ``record`` states them, by name and digest; a role that calls a
    model and records no prompt holds the empty set."""
    held: dict[str, set[tuple[str, str]]] = {role: set() for role, _ in record.model_configurations}
    for role, name, value in record.prompt_digests:
        held.setdefault(role, set()).add((name, value))
    return {role: frozenset(prompts) for role, prompts in held.items()}


def _entry(
    world: SealedWorld,
    run: StoredRun,
    registration: Registration,
    registration_content: bytes,
    registrations_at: Mapping[str, bytes | None],
    label: Label,
) -> InventoryEntry:
    read = digest(run.content)

    def entry(
        disposition: Disposition,
        evaluation: Evaluation | None,
        cost: CostCheck | None,
        differing: tuple[RecordedSetting, ...] = (),
        of_run: Label | None = None,
    ) -> InventoryEntry:
        return InventoryEntry(
            run.key, run.version_id, read, disposition, differing, of_run, evaluation, cost
        )

    export = _decoded(run)
    if export is None:
        return entry(Disposition.NOT_AN_EXPORT, None, None)
    if export.context.world_version != world.version:
        return entry(Disposition.ANOTHER_WORLD, None, check_cost(export))
    evaluation = evaluate_run(world, export)
    cost = evaluation.metrics.cost
    record = export.record
    cited = registrations_at.get(record.preregistration_commit)
    if cited is None:
        return entry(Disposition.REGISTRATION_NOT_RESOLVED, evaluation, cost, (), Label.UNKNOWN)
    if cited != registration_content:
        return entry(Disposition.ANOTHER_REGISTRATION, evaluation, cost)
    differing = setting_differences(registration, record)
    if differing:
        return entry(Disposition.SETTINGS_DIFFER, evaluation, cost, differing)
    frozen = registration.status is RegistrationStatus.FROZEN
    if frozen and record.harness.tree is not TreeState.CLEAN:
        return entry(Disposition.DIRTY_HARNESS, evaluation, cost)
    return entry(Disposition.ELIGIBLE, evaluation, cost, (), label)


def _decoded(run: StoredRun) -> RunExport | None:
    """The export ``run`` holds, or ``None`` when its bytes are not one."""
    try:
        return decode_export_bytes(run.content)
    except ValueError:
        return None


def _label(registration: Registration) -> Label:
    if registration.status is RegistrationStatus.DRAFT:
        return Label.DEVELOPMENT
    declared = registration.amendment
    if declared.amends is not None and declared.prior_full_set_results:
        return Label.EXPLORATORY
    return Label.REPORTED


def _require_unambiguous(eligible: Sequence[InventoryEntry]) -> None:
    first: dict[tuple[str, int], str] = {}
    for entry in eligible:
        assert entry.evaluation is not None
        header = entry.evaluation.outcome.header
        identity = (header.run_id, header.attempt)
        if identity in first:
            raise AmbiguousRuns(
                f"two eligible exports carry one run and attempt: {first[identity]} and {entry.key}"
            )
        first[identity] = entry.key


__all__ = [
    "ARTIFACT_FORMAT_VERSION",
    "AmbiguousRuns",
    "ChangedPath",
    "Disposition",
    "EvaluationArtifact",
    "EvaluatorRevision",
    "InventoryEntry",
    "Label",
    "RegistrationRead",
    "RecordedSetting",
    "StoredRun",
    "WorldRead",
    "cited_commits",
    "evaluation_artifact",
    "setting_differences",
]
