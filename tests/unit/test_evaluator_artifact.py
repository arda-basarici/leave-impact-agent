"""The evaluation artifact. Every listed object comes back in the inventory with one reason: an
eligible run enters the tables; an object that is no export, an export of another world, a
run whose registration does not resolve, was another one, or whose recorded settings differ,
and under a frozen registration a run from a dirty tree, each keep what can be said of them
and enter none. The label follows the registration's status and what it declares. A short
set shows its shortfall; an ambiguous set and an incompatible registration refuse."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.agent.export import export_rules_only_run
from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import investigate
from leaveimpact.core import (
    AgentSystem,
    Amendment,
    Basis,
    Caps,
    HarnessRevision,
    ModelConfiguration,
    OutageAssignment,
    PrefetchRule,
    PricingBasis,
    RegisteredArm,
    Registration,
    RegistrationStatus,
    RulesOnlySystem,
    RunExport,
    ScenarioSetName,
    Setting,
    Source,
    System,
    SystemKind,
    TreeState,
    condition_id,
    decode_registration_bytes,
    export_bytes,
    registration_bytes,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator.artifact import (
    ARTIFACT_FORMAT_VERSION,
    AmbiguousRuns,
    ChangedPath,
    Disposition,
    EvaluationArtifact,
    EvaluatorRevision,
    InventoryEntry,
    Label,
    RecordedSetting,
    StoredRun,
    cited_commits,
    evaluation_artifact,
    setting_differences,
)
from leaveimpact.evaluator.cells import StratumKind
from leaveimpact.evaluator.grading import Graded
from leaveimpact.evaluator.registered import development_selection
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from leaveimpact.world.artifacts import digest
from tests.unit.export_fixture import agent_export
from tests.unit.reads_fixture import systems_holding
from tests.unit.throwaway_world import loaded_world

DIGEST = "a" * 64
COMMIT = "b" * 40
OTHER_COMMIT = "c" * 40
UNCHANGED = EvaluatorRevision(COMMIT, COMMIT, ())
FIRST = Amendment(None, False)
"""What a first registration declares: it amends none and no result existed."""

_COMMITTED = decode_registration_bytes(
    (Path(__file__).resolve().parents[2] / "preregistration" / "registration.json").read_bytes()
)
# The registered resample count buys precision these tests do not need.
DRAFT = replace(_COMMITTED, statistics=replace(_COMMITTED.statistics, resamples=200))
DRAFT_BYTES = registration_bytes(DRAFT)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def exported(
    world: SealedWorld,
    scenario: Scenario,
    *down: Source,
    registration: Registration = DRAFT,
    run_id: str = "run-1",
    tree: TreeState = TreeState.CLEAN,
) -> RunExport:
    """The real baseline's export of ``scenario`` under ``registration``."""
    systems = systems_holding(world)
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    context = world.context_of(scenario)
    provenance = rules_only_provenance(
        registration,
        condition_id(down),
        harness=HarnessRevision(COMMIT, tree),
        preregistration_commit=COMMIT,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    return export_rules_only_run(
        investigate(context, systems.ports),
        context,
        provenance,
        run_id=run_id,
        attempt=1,
        duration_ms=1_200,
    )


def stored(key: str, export: RunExport) -> StoredRun:
    return StoredRun(key, f"version-of-{key}", export_bytes(export))


def artifact_of(
    world: SealedWorld,
    *runs: StoredRun,
    registration: bytes = DRAFT_BYTES,
    at: Mapping[str, bytes | None] | None = None,
    evaluator: EvaluatorRevision = UNCHANGED,
) -> EvaluationArtifact:
    resolved = {COMMIT: registration} if at is None else at
    return evaluation_artifact(world, registration, runs, resolved, evaluator)


def only(artifact: EvaluationArtifact) -> InventoryEntry:
    (entry,) = artifact.inventory
    return entry


def made(artifact: EvaluationArtifact) -> int:
    """The runs the full set's tables hold, over every arm."""
    full = next(held for held in artifact.analysis.sets if held.name is ScenarioSetName.FULL)
    return sum(
        cell.accounting.made
        for arm in full.arms
        for cell in arm.cells
        if cell.stratum.kind is StratumKind.OVERALL
    )


def with_record(export: RunExport, **changes: object) -> RunExport:
    return replace(export, record=replace(export.record, **changes))


def frozen(world: SealedWorld, amendment: Amendment = FIRST) -> Registration:
    """A frozen registration of the rules-only system alone: nothing pending, the numbers
    calibrated, the development scenarios listed, no comparison left to name another system."""
    statistics = DRAFT.statistics
    return replace(
        DRAFT,
        status=RegistrationStatus.FROZEN,
        amendment=amendment,
        systems=tuple(s for s in DRAFT.systems if isinstance(s, RulesOnlySystem)),
        arms=tuple(arm for arm in DRAFT.arms if arm.system is SystemKind.RULES_ONLY),
        statistics=replace(
            statistics, primary=(), descriptive=replace(statistics.descriptive, pairs=())
        ),
        caps=replace(DRAFT.caps, basis=Basis.CALIBRATED),
        budget=replace(DRAFT.budget, basis=Basis.CALIBRATED),
        scenario_sets=replace(DRAFT.scenario_sets, development=development_selection(world, DRAFT)),
    )


# --- An eligible set ---------------------------------------------------------------------------


def test_eligible_runs_enter_the_tables_and_the_artifact_says_what_it_read(
    world: SealedWorld,
) -> None:
    first, second = world.scenarios[:2]
    runs = [
        stored("runs/b", exported(world, second, run_id="run-2")),
        stored("runs/a", exported(world, first)),
    ]
    artifact = artifact_of(world, *runs)
    assert artifact.format_version == ARTIFACT_FORMAT_VERSION
    assert (artifact.label, artifact.evaluated_by_changed_code) == (Label.DEVELOPMENT, False)
    assert artifact.world.version == world.version
    assert artifact.world.truth_manifest == world.truth_manifest
    assert artifact.registration.digest == digest(DRAFT_BYTES)
    assert artifact.registration.status is RegistrationStatus.DRAFT
    assert artifact.registration.declared == Amendment(None, False)
    assert artifact.evaluator == UNCHANGED
    # In key order, each with the version id read and the digest of its bytes.
    assert [entry.key for entry in artifact.inventory] == ["runs/a", "runs/b"]
    for entry, run in zip(artifact.inventory, reversed(runs), strict=True):
        assert (entry.version_id, entry.digest) == (run.version_id, digest(run.content))
        assert (entry.disposition, entry.differing) == (Disposition.ELIGIBLE, ())
        assert entry.label is Label.DEVELOPMENT
        assert entry.evaluation is not None and isinstance(entry.evaluation.outcome, Graded)
        assert entry.cost is entry.evaluation.metrics.cost
    assert made(artifact) == 2


def test_a_short_set_shows_its_shortfall_and_an_empty_one_every_run_missing(
    world: SealedWorld,
) -> None:
    one = artifact_of(world, stored("runs/a", exported(world, world.scenarios[0])))
    full = next(held for held in one.analysis.sets if held.name is ScenarioSetName.FULL)
    normal = next(arm for arm in full.arms if arm.condition == "normal")
    assert (normal.cells[0].accounting.made, normal.cells[0].accounting.missing) == (1, 29)
    none = artifact_of(world)
    assert none.inventory == () and made(none) == 0


# --- Each reason for staying out of the tables -------------------------------------------------


def test_an_object_that_is_no_export_is_listed_with_nothing_more(world: SealedWorld) -> None:
    export = exported(world, world.scenarios[0])
    pretty = export_bytes(export).replace(b":", b": ")
    for content in (b"not json", b"[]", pretty):
        entry = only(artifact_of(world, StoredRun("runs/x", "v1", content)))
        assert entry.disposition is Disposition.NOT_AN_EXPORT
        assert (entry.evaluation, entry.cost, entry.label) == (None, None, None)
        assert entry.digest == digest(content)


def test_an_export_of_another_world_keeps_its_cost_and_is_not_graded(world: SealedWorld) -> None:
    export = exported(world, world.scenarios[0])
    elsewhere = replace(
        export, context=replace(export.context, world_version=WorldVersion("f" * 64))
    )
    artifact = artifact_of(world, stored("runs/x", elsewhere))
    entry = only(artifact)
    assert entry.disposition is Disposition.ANOTHER_WORLD
    assert entry.evaluation is None and entry.cost is not None and entry.label is None
    assert made(artifact) == 0


def test_a_run_whose_registration_does_not_resolve_is_graded_and_classified_unknown(
    world: SealedWorld,
) -> None:
    run = stored("runs/x", exported(world, world.scenarios[0]))
    for at in ({}, {COMMIT: None}, {OTHER_COMMIT: DRAFT_BYTES}):
        artifact = artifact_of(world, run, at=at)
        entry = only(artifact)
        assert entry.disposition is Disposition.REGISTRATION_NOT_RESOLVED
        assert entry.label is Label.UNKNOWN
        assert entry.evaluation is not None and isinstance(entry.evaluation.outcome, Graded)
        assert made(artifact) == 0


def test_a_run_made_under_another_registration_keeps_its_grade_and_enters_no_table(
    world: SealedWorld,
) -> None:
    run = stored("runs/x", exported(world, world.scenarios[0]))
    other = registration_bytes(replace(DRAFT, statistics=replace(DRAFT.statistics, seed=8)))
    artifact = artifact_of(world, run, at={COMMIT: other})
    entry = only(artifact)
    assert entry.disposition is Disposition.ANOTHER_REGISTRATION
    assert entry.evaluation is not None and entry.cost is not None and entry.label is None
    assert made(artifact) == 0


def test_a_run_whose_recorded_settings_differ_says_which_and_enters_no_table(
    world: SealedWorld,
) -> None:
    export = exported(world, world.scenarios[0])
    record = export.record
    cases: list[tuple[RunExport, tuple[RecordedSetting, ...]]] = [
        (
            with_record(export, caps=Caps(21, 400_000, 2, 20_000, record.caps.counting_rule)),
            (RecordedSetting.CAPS,),
        ),
        (
            with_record(export, system=System(SystemKind.RULES_ONLY, "another")),
            (RecordedSetting.SYSTEM,),
        ),
        (
            with_record(
                export,
                outage=OutageAssignment(
                    frozenset({Source.JIRA, Source.CALENDAR}), record.outage.schedule_digest
                ),
            ),
            (RecordedSetting.ARM,),
        ),
        (
            with_record(export, outage=OutageAssignment(frozenset(), DIGEST)),
            (RecordedSetting.OUTAGE_SCHEDULE,),
        ),
        (
            with_record(export, prefetch_rule=PrefetchRule("another-prefetch", DIGEST)),
            (RecordedSetting.PREFETCH,),
        ),
        (
            with_record(
                export,
                caps=Caps(21, 400_000, 2, 20_000, record.caps.counting_rule),
                prefetch_rule=PrefetchRule("another-prefetch", DIGEST),
            ),
            (RecordedSetting.CAPS, RecordedSetting.PREFETCH),
        ),
    ]
    for changed, differing in cases:
        artifact = artifact_of(world, stored("runs/x", changed))
        entry = only(artifact)
        assert (entry.disposition, entry.differing) == (Disposition.SETTINGS_DIFFER, differing)
        assert entry.evaluation is not None and entry.label is None
        assert made(artifact) == 0


def test_a_run_of_a_system_still_pending_has_nothing_to_be_compared_with(
    world: SealedWorld,
) -> None:
    run = stored("runs/x", agent_export(world, world.scenarios[0], ()))
    entry = only(artifact_of(world, run))
    assert entry.disposition is Disposition.SETTINGS_DIFFER
    assert entry.differing == (RecordedSetting.PENDING,)


def test_a_model_systems_configuration_prompts_and_surface_are_compared_per_role(
    world: SealedWorld,
) -> None:
    record = agent_export(world, world.scenarios[0], ()).record
    ((_, model),) = record.model_configurations
    agent = next(system for system in DRAFT.systems if isinstance(system, AgentSystem))

    def registered(**changes: object) -> Registration:
        named = replace(
            agent,
            variant=record.system.variant,
            model=model,
            prompt_digests=(("system", DIGEST),),
            tool_surface_digest=DIGEST,
        )
        named = replace(named, **changes)
        systems = tuple(named if system is agent else system for system in DRAFT.systems)
        return replace(DRAFT, systems=systems)

    model_side = {RecordedSetting.MODEL, RecordedSetting.PROMPTS, RecordedSetting.TOOL_SURFACE}
    assert not model_side & set(setting_differences(registered(), record))
    other = ModelConfiguration(model.model_id, (Setting("temperature", 1),))
    for changes, setting in (
        ({"model": other}, RecordedSetting.MODEL),
        ({"prompt_digests": (("system", "c" * 64),)}, RecordedSetting.PROMPTS),
        ({"prompt_digests": (("system", DIGEST), ("report", DIGEST))}, RecordedSetting.PROMPTS),
        ({"tool_surface_digest": "c" * 64}, RecordedSetting.TOOL_SURFACE),
    ):
        differing = set(setting_differences(registered(**changes), record))
        assert differing & model_side == {setting}
    # A system the registration does not hold at all.
    without_agent = replace(frozen(world), status=RegistrationStatus.DRAFT)
    assert setting_differences(without_agent, record) == (RecordedSetting.SYSTEM,)


# --- Under a frozen registration ---------------------------------------------------------------


def test_a_frozen_registration_reports_and_refuses_a_dirty_harness_tree(
    world: SealedWorld,
) -> None:
    registration = frozen(world)
    content = registration_bytes(registration)
    clean = stored("runs/a", exported(world, world.scenarios[0], registration=registration))
    dirty = stored(
        "runs/b",
        exported(
            world,
            world.scenarios[1],
            registration=registration,
            run_id="run-2",
            tree=TreeState.DIRTY,
        ),
    )
    artifact = artifact_of(world, clean, dirty, registration=content)
    assert artifact.label is Label.REPORTED
    eligible, refused = artifact.inventory
    assert (eligible.disposition, eligible.label) == (Disposition.ELIGIBLE, Label.REPORTED)
    assert (refused.disposition, refused.label) == (Disposition.DIRTY_HARNESS, None)
    assert refused.evaluation is not None
    assert made(artifact) == 1
    # Under a draft the same dirty run is a development run like any other.
    under_draft = stored(
        "runs/b", exported(world, world.scenarios[1], run_id="run-2", tree=TreeState.DIRTY)
    )
    assert only(artifact_of(world, under_draft)).disposition is Disposition.ELIGIBLE


def test_the_label_follows_what_the_registration_declares_and_says_when_the_code_changed(
    world: SealedWorld,
) -> None:
    changed = EvaluatorRevision(
        COMMIT, OTHER_COMMIT, (ChangedPath("src/leaveimpact/evaluator/tables.py", "1" * 40, None),)
    )
    declared = {
        Amendment(None, False): Label.REPORTED,
        Amendment(OTHER_COMMIT, False): Label.REPORTED,
        Amendment(None, True): Label.REPORTED,
        Amendment(OTHER_COMMIT, True): Label.EXPLORATORY,
    }
    for amendment, label in declared.items():
        content = registration_bytes(frozen(world, amendment))
        artifact = artifact_of(world, registration=content, evaluator=changed)
        assert (artifact.label, artifact.registration.declared) == (label, amendment)
        assert artifact.evaluated_by_changed_code
        assert not artifact_of(world, registration=content).evaluated_by_changed_code
    # A draft is development whatever it declares, and changed code is expected of it.
    draft = registration_bytes(replace(DRAFT, amendment=Amendment(OTHER_COMMIT, True)))
    artifact = artifact_of(world, registration=draft, evaluator=changed)
    assert (artifact.label, artifact.evaluated_by_changed_code) == (Label.DEVELOPMENT, False)
    assert artifact.evaluator == changed


# --- What refuses the whole evaluation ---------------------------------------------------------


def test_two_eligible_exports_of_one_run_and_attempt_refuse_naming_their_keys(
    world: SealedWorld,
) -> None:
    export = exported(world, world.scenarios[0])
    with pytest.raises(AmbiguousRuns) as refusal:
        artifact_of(world, stored("runs/a", export), stored("runs/b", export))
    assert str(refusal.value) == (
        "two eligible exports carry one run and attempt: runs/a and runs/b"
    )
    # The same identity on a run that is out of the tables anyway is no ambiguity.
    other = with_record(export, prefetch_rule=PrefetchRule("another-prefetch", DIGEST))
    artifact = artifact_of(world, stored("runs/a", export), stored("runs/b", other))
    assert [entry.disposition for entry in artifact.inventory] == [
        Disposition.ELIGIBLE,
        Disposition.SETTINGS_DIFFER,
    ]


def test_a_registration_this_evaluator_cannot_read_as_a_plan_refuses(world: SealedWorld) -> None:
    with pytest.raises(ValueError, match="not its one written form"):
        artifact_of(world, registration=DRAFT_BYTES.replace(b"\n", b"\r\n"))
    prefetch = replace(DRAFT.prefetch, digest=DIGEST)
    other = registration_bytes(replace(DRAFT, prefetch=prefetch))
    with pytest.raises(ValueError, match="this evaluator checks conformance to"):
        artifact_of(world, registration=other)
    assert RegisteredArm(SystemKind.RULES_ONLY, "normal") in DRAFT.arms


# --- The commits to resolve --------------------------------------------------------------------


def test_the_cited_commits_are_the_exports_own_each_once(world: SealedWorld) -> None:
    export = exported(world, world.scenarios[0])
    elsewhere = with_record(export, preregistration_commit=OTHER_COMMIT)
    runs = [
        stored("runs/a", export),
        StoredRun("runs/x", "v1", b"not json"),
        stored("runs/b", elsewhere),
        stored("runs/c", export),
    ]
    assert cited_commits(runs) == (COMMIT, OTHER_COMMIT)
    assert cited_commits([]) == ()
