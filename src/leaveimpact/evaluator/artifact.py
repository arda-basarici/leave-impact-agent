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
alike; the comparison is of bytes, made before anything at that commit is decoded, so a
file of an older format there is another registration and no error. And what the export
records of its own execution is what the registration says: the system and its variant, a
cell the registration holds and runs, the outage schedule's digest, the caps, the prefetch
rule, the retrieval, the composing policy its claims were composed under, and for a system
that calls a model its roles by name, each with its configuration, its prompts and its
tool surface, and the attribution table its dispatches were read by. Equal bytes alone
would show matching declarations and nothing about what ran; an equal composing policy
shows the export recorded the registered identity and verifies no implementation. A system
with a value still pending that its execution needs has nothing to be compared with, so
its runs are not eligible. Under a bound registration the harness's tree is clean as well.
A run that fails any of these keeps its grade and its cost in the inventory and enters no
table; so does one whose cited commit resolves to no registration, which is classified
unknown.

Two things are not runs of this evaluation at all and are kept all the same: an object
that does not decode as an export, with nothing more to say of it, and an export of another
world, with its cost.

*What refuses the whole evaluation.* Two eligible exports that carry one run and attempt
make the set ambiguous, and a registration this evaluator cannot read as a plan (a name it
does not hold, a prefetch it does not plan) is incompatible; both raise, since tables cut
from either would look complete and be about something else. So does a bound registration
evaluated against a world other than the one it binds, and one whose procedure is not the
frozen registration's it names (``require_binding``): binding a world changes nothing
else, and a reader that could not hold it to that would report under a procedure nobody
froze. A set that is merely short does not raise: the analysis builds every registered arm
and scenario and shows the shortfall.

*The label* is derived here and stored, never read from an export. A draft registration
gives a development evaluation, and so does a frozen one: its world does not exist yet,
and a run names its own. A bound one gives a reported evaluation, or an exploratory one
when the registration declares that it amends an earlier one and that full-set results on
this world existed when it was written. Those two statements are the registration's
author's and nothing here can check them, so the artifact carries them as declared. An
evaluation under a bound registration by an evaluator whose implementation changed since
the registration's commit says so beside its label; whether a change was maintenance or a
change to a metric is a judgment for the report.

Reading the store, resolving a commit and refusing a dirty evaluator tree are the entry
point's. This module takes bytes and gives data; ``cited_commits`` says which commits the
entry point must resolve before the artifact can be made, and a bound registration's
frozen commit is one more.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.attribution import attribution_table_digest
from leaveimpact.core.jsonshape import canonical_bytes
from leaveimpact.core.registration import (
    Amendment,
    Pending,
    Registration,
    RegistrationStatus,
    blocking,
    condition_id,
    roles_of,
    schedule_digest,
)
from leaveimpact.core.registration_json import (
    decode_registration_bytes,
    procedure_digest,
    procedure_projection,
)
from leaveimpact.core.run_export import RunExport
from leaveimpact.core.run_export_json import decode_export_bytes
from leaveimpact.core.run_record import PrefetchRule
from leaveimpact.core.run_timing import TreeState
from leaveimpact.evaluator.analysis import Analysis, analyse
from leaveimpact.evaluator.cost_check import CostCheck, check_cost
from leaveimpact.evaluator.sealed_world import SealedSource, SealedWorld
from leaveimpact.evaluator.trace_metrics import Evaluation, evaluate_run
from leaveimpact.world.artifacts import digest

ARTIFACT_FORMAT_VERSION = 3
"""The format of the evaluation artifact as this code writes it; 3 since an estimate states
why a bootstrap resolved no interval and a comparison of single runs carries one."""


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
    CELL = "cell"
    """The system under the assigned condition at the assigned level is no registered cell,
    or one whose conditional group is not decided as run."""
    OUTAGE_SCHEDULE = "outage_schedule"
    CAPS = "caps"
    PREFETCH = "prefetch"
    RETRIEVAL = "retrieval"
    COMPOSING_POLICY = "composing_policy"
    MODEL = "model"
    PROMPTS = "prompts"
    TOOL_SURFACE = "tool_surface"
    ATTRIBUTION_TABLE = "attribution_table"
    PENDING = "pending"
    """The registered system has a value still pending that its execution needs, so nothing
    can be compared."""


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
    the digest of its procedure, which a frozen registration and the bound one made from it
    share, the frozen commit a bound one names, and what its author declares of its
    history, which nothing here verified."""

    status: RegistrationStatus
    digest: str
    procedure: str
    frozen_commit: str | None
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
    bound = registration.status is RegistrationStatus.BOUND
    if bound and registration.world.version != world.version:
        raise ValueError(
            f"the registration is bound to the world {registration.world.version}, and this "
            f"evaluation is against {world.version}"
        )
    label = _label(registration)
    inventory = tuple(
        _entry(world, run, registration, registration_content, registrations_at, label)
        for run in sorted(runs, key=lambda run: run.key)
    )
    eligible = [entry for entry in inventory if entry.disposition is Disposition.ELIGIBLE]
    _require_unambiguous(eligible)
    evaluations = [entry.evaluation for entry in eligible if entry.evaluation is not None]
    # Out of the tables and still a trace of this world: what its reads show of a source
    # contradicting itself is evidence about the world, whatever kept it out of an estimate.
    outside = [
        (entry.key, entry.evaluation)
        for entry in inventory
        if entry.evaluation is not None and entry.disposition is not Disposition.ELIGIBLE
    ]
    return EvaluationArtifact(
        format_version=ARTIFACT_FORMAT_VERSION,
        label=label,
        evaluated_by_changed_code=bound and bool(evaluator.changed),
        world=WorldRead(
            world.version, world.world_spec, world.scenario_specs, world.truth_manifest
        ),
        evaluator=evaluator,
        registration=RegistrationRead(
            registration.status,
            digest(registration_content),
            procedure_digest(registration),
            registration.world.frozen_commit,
            registration.amendment,
        ),
        inventory=inventory,
        analysis=analyse(world, evaluations, registration, outside=outside),
    )


def require_binding(registration: Registration, frozen_content: bytes | None) -> None:
    """Hold a bound ``registration`` to the frozen one it names, whose file at that commit
    has the bytes ``frozen_content`` (``None`` when the commit resolves to none).

    Raises ``ValueError`` unless the file there decodes, is frozen, and has the procedure
    the bound one has: binding a world changes the status, the world's version and the
    frozen commit named, and nothing else. A registration that is not bound binds nothing
    and passes.

    The two procedures are compared in their canonical bytes, section by section, never as
    decoded values: Python holds ``True`` equal to ``1``, and a setting changed from the
    one to the other is a changed procedure.
    """
    commit = registration.world.frozen_commit
    if registration.status is not RegistrationStatus.BOUND or commit is None:
        return
    if frozen_content is None:
        raise ValueError(f"the frozen commit {commit} holds no registration")
    try:
        frozen = decode_registration_bytes(frozen_content)
    except ValueError as error:
        raise ValueError(
            f"the registration at the frozen commit {commit} does not decode: {error}"
        ) from error
    if frozen.status is not RegistrationStatus.FROZEN:
        raise ValueError(
            f"the registration at the frozen commit {commit} is {frozen.status.value}, "
            "not frozen"
        )
    ours, theirs = procedure_projection(registration), procedure_projection(frozen)
    # Both are this code's encoding of a registration, so they hold the same sections.
    changed = [
        key
        for key in ours
        if canonical_bytes({key: ours[key]}) != canonical_bytes({key: theirs[key]})
    ]
    if changed:
        raise ValueError(
            "the bound registration's procedure is not the frozen one's at "
            f"{commit}; they differ in {', '.join(changed)}"
        )


def setting_differences(
    registration: Registration, export: RunExport
) -> tuple[RecordedSetting, ...]:
    """The settings ``export`` states that are not what ``registration`` fixes, in the
    declared order; empty when the run executed as registered."""
    record = export.record
    system = registration.system(record.system.kind)
    if system is None:
        return (RecordedSetting.SYSTEM,)
    roles = roles_of(system)
    if blocking(registration, system.kind) or isinstance(roles, Pending):
        return (RecordedSetting.PENDING,)
    registered = registration.prefetch
    condition = condition_id(record.outage.scheduled_unreachable)
    cell = registration.cell(system.kind, condition, record.corpus_level)
    table = registration.attribution
    same = {
        RecordedSetting.SYSTEM: system.variant == record.system.variant,
        RecordedSetting.CELL: cell is not None and registration.runs(cell),
        RecordedSetting.OUTAGE_SCHEDULE: (
            record.outage.schedule_digest == schedule_digest(registration.outage)
        ),
        RecordedSetting.CAPS: record.caps == system.caps.caps,
        RecordedSetting.PREFETCH: (
            record.prefetch_rule == PrefetchRule(registered.identifier, registered.digest)
        ),
        RecordedSetting.RETRIEVAL: record.retrieval == system.retrieval,
        RecordedSetting.COMPOSING_POLICY: (
            export.trace.composition.policy == registration.stated_facts.composing_policy
        ),
        # Role by role, by name: a role the registration does not name, or one it names
        # that the run did not record, makes all three differ.
        RecordedSetting.MODEL: dict(record.model_configurations)
        == {role.name: role.configuration for role in roles},
        RecordedSetting.PROMPTS: _prompts_by_role(export)
        == {role.name: frozenset(role.prompt_digests) for role in roles},
        RecordedSetting.TOOL_SURFACE: dict(record.tool_surface_digests)
        == {role.name: role.tool_surface_digest for role in roles},
        RecordedSetting.ATTRIBUTION_TABLE: record.attribution_table
        == (
            attribution_table_digest(table)
            if roles and not isinstance(table, Pending)
            else None
        ),
    }
    return tuple(setting for setting, holds in same.items() if not holds)


def _prompts_by_role(export: RunExport) -> dict[str, frozenset[tuple[str, str]]]:
    """Each role's prompts as the record states them, by name and digest; a role that calls
    a model and records no prompt holds the empty set."""
    record = export.record
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
    differing = setting_differences(registration, export)
    if differing:
        return entry(Disposition.SETTINGS_DIFFER, evaluation, cost, differing)
    bound = registration.status is RegistrationStatus.BOUND
    dirty = any(
        revision.tree is not TreeState.CLEAN for revision in record.timing.harness_revisions
    )
    if bound and dirty:
        return entry(Disposition.DIRTY_HARNESS, evaluation, cost)
    return entry(Disposition.ELIGIBLE, evaluation, cost, (), label)


def _decoded(run: StoredRun) -> RunExport | None:
    """The export ``run`` holds, or ``None`` when its bytes are not one."""
    try:
        return decode_export_bytes(run.content)
    except ValueError:
        return None


def _label(registration: Registration) -> Label:
    if registration.status is not RegistrationStatus.BOUND:
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
    "require_binding",
    "setting_differences",
]
