"""The evaluation artifact. Every listed object comes back in the inventory with one reason: an
eligible run enters the tables; an object that is no export, an export of another world, a
run whose registration does not resolve, was another one (a file of an older format at the
cited commit included, never decoded), or whose recorded settings differ, and under a bound
registration a run from a dirty tree, each keep what can be said of them and enter none. A
model system's roles are compared by name. The label follows the registration's status and
what it declares: development under a draft and under a frozen registration, reported or
exploratory under a bound one. A bound registration is held to its world and to the frozen
procedure it names. A short set shows its shortfall; an ambiguous set and an incompatible
registration refuse."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import date

import pytest

from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import investigate
from leaveimpact.core import (
    Amendment,
    CallConfiguration,
    CallSetting,
    Caps,
    HarnessRevision,
    OutageAssignment,
    PrefetchRule,
    PricingBasis,
    RegisteredRole,
    Registration,
    RegistrationStatus,
    RunExport,
    Source,
    System,
    SystemKind,
    TreeState,
    condition_id,
    export_bytes,
    procedure_digest,
    registration_bytes,
)
from leaveimpact.core.attribution import attribution_table_digest
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.run_ending import ComposingPolicy
from leaveimpact.evaluator import registered as registries
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
    require_binding,
    setting_differences,
)
from leaveimpact.evaluator.cells import StratumKind
from leaveimpact.evaluator.grading import Graded
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from leaveimpact.world.artifacts import digest
from tests.unit.export_fixture import ROLE, agent_export, export_baseline
from tests.unit.reads_fixture import systems_holding
from tests.unit.registration_fixture import DRAFT as COMMITTED
from tests.unit.registration_fixture import MECHANISM, TABLE, bound, frozen, light, named
from tests.unit.throwaway_world import loaded_world

DIGEST = "a" * 64
COMMIT = "b" * 40
OTHER_COMMIT = "c" * 40
FROZEN_COMMIT = "d" * 40
UNCHANGED = EvaluatorRevision(COMMIT, COMMIT, ())
FIRST = Amendment(None, False)
"""What a first registration declares: it amends none and no result existed."""

DRAFT = light(COMMITTED)
DRAFT_BYTES = registration_bytes(DRAFT)
FROZEN = light(frozen())
MODEL_SIDE = {RecordedSetting.MODEL, RecordedSetting.PROMPTS, RecordedSetting.TOOL_SURFACE}


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


@pytest.fixture
def resolved_mechanism(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mechanism measure held by the evaluator, as it is once the fact-stage measures
    exist: a frozen registration names it, and until then the evaluator holds none."""
    monkeypatch.setattr(registries, "MECHANISM_MEASURES", (MECHANISM.name,))


def exported(
    world: SealedWorld,
    scenario: Scenario,
    *down: Source,
    registration: Registration = DRAFT,
    level: str = "base",
    run_id: str = "run-1",
    tree: TreeState = TreeState.CLEAN,
) -> RunExport:
    """The real baseline's export of ``scenario`` under ``registration`` at ``level``."""
    systems = systems_holding(world)
    for port in (systems.people, systems.work, systems.calendar, systems.documents):
        port.reachable = port.source not in down
    context = world.context_of(scenario)
    provenance = rules_only_provenance(
        registration,
        condition_id(down),
        level,
        harness=HarnessRevision(COMMIT, tree),
        preregistration_commit=COMMIT,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    return export_baseline(
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
    """The runs the tables hold, over every arm."""
    return sum(
        cell.accounting.made
        for arm in artifact.analysis.arms
        for cell in arm.cells
        if cell.stratum.kind is StratumKind.OVERALL
    )


def with_record(export: RunExport, **changes: object) -> RunExport:
    return replace(export, record=replace(export.record, **changes))


def bound_to(world: SealedWorld, amendment: Amendment = FIRST) -> Registration:
    """A registration bound to ``world``, declaring ``amendment``."""
    return bound(world.version, replace(FROZEN, amendment=amendment), frozen_commit=FROZEN_COMMIT)


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
    assert artifact.registration.procedure == procedure_digest(DRAFT)
    assert artifact.registration.frozen_commit is None
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


def test_the_baseline_at_each_level_is_a_run_of_its_own_cell(world: SealedWorld) -> None:
    scenario = world.scenarios[0]
    artifact = artifact_of(
        world,
        stored("runs/a", exported(world, scenario)),
        stored("runs/b", exported(world, scenario, level="padded", run_id="run-2")),
    )
    assert [entry.disposition for entry in artifact.inventory] == [Disposition.ELIGIBLE] * 2
    by_level = {
        arm.level: arm.cells[0].accounting.made
        for arm in artifact.analysis.arms
        if arm.condition == "normal"
    }
    assert by_level == {"base": 1, "padded": 1}
    # The two exports are graded alike: the baseline reads no document.
    base, padded = (entry.evaluation for entry in artifact.inventory)
    assert base is not None and padded is not None
    assert (base.level, padded.level) == ("base", "padded")
    assert isinstance(base.outcome, Graded) and isinstance(padded.outcome, Graded)
    assert base.outcome.rows == padded.outcome.rows


def test_a_short_set_shows_its_shortfall_and_an_empty_one_every_run_missing(
    world: SealedWorld,
) -> None:
    one = artifact_of(world, stored("runs/a", exported(world, world.scenarios[0])))
    normal = next(
        arm for arm in one.analysis.arms if (arm.condition, arm.level) == ("normal", "base")
    )
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
    reseeded = registration_bytes(replace(DRAFT, statistics=replace(DRAFT.statistics, seed=8)))
    # A file of the format this one replaced, and bytes that are no registration at all:
    # the comparison is of bytes, and nothing at the cited commit is decoded.
    for other in (reseeded, b'{\n  "format_version": 1\n}\n', b"not a registration"):
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
    other_policy = ComposingPolicy("rules-composer", DIGEST)
    composition = replace(export.trace.composition, policy=other_policy)
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
            (RecordedSetting.CELL,),
        ),
        # A level nobody registered is no cell, and neither is an outage at the padded level.
        (with_record(export, corpus_level="doubled"), (RecordedSetting.CELL,)),
        (
            with_record(
                export,
                corpus_level="padded",
                outage=OutageAssignment(frozenset({Source.JIRA}), record.outage.schedule_digest),
            ),
            (RecordedSetting.CELL,),
        ),
        (
            with_record(export, outage=OutageAssignment(frozenset(), DIGEST)),
            (RecordedSetting.OUTAGE_SCHEDULE,),
        ),
        (
            with_record(export, prefetch_rule=PrefetchRule("another-prefetch", DIGEST)),
            (RecordedSetting.PREFETCH,),
        ),
        # Claims composed under a policy other than the registered one.
        (
            replace(export, trace=replace(export.trace, composition=composition)),
            (RecordedSetting.COMPOSING_POLICY,),
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


def test_a_run_in_a_cell_whose_group_is_not_decided_as_run_is_not_a_run_of_the_plan(
    world: SealedWorld,
) -> None:
    record = agent_export(world, world.scenarios[0], ()).record
    under_outage = replace(
        agent_export(world, world.scenarios[0], ()),
        record=replace(
            record,
            system=System(SystemKind.FULL_CONTEXT, "all-documents"),
            outage=OutageAssignment(frozenset({Source.JIRA}), record.outage.schedule_digest),
        ),
    )
    # Named, with the group still pending: the cell is registered and nobody runs it.
    assert RecordedSetting.CELL in setting_differences(named(DRAFT), under_outage)


def test_a_run_of_a_system_still_pending_has_nothing_to_be_compared_with(
    world: SealedWorld,
) -> None:
    run = stored("runs/x", agent_export(world, world.scenarios[0], ()))
    entry = only(artifact_of(world, run))
    assert entry.disposition is Disposition.SETTINGS_DIFFER
    assert entry.differing == (RecordedSetting.PENDING,)
    # Named and given its roles, the agent still has nothing to be compared with while the
    # table its dispatches are read by is pending.
    export = agent_export(world, world.scenarios[0], ())
    untabled = replace(named(DRAFT), attribution=DRAFT.attribution)
    assert setting_differences(untabled, export) == (RecordedSetting.PENDING,)


def test_a_model_systems_roles_are_compared_by_name_each_with_its_three_settings(
    world: SealedWorld,
) -> None:
    export = agent_export(world, world.scenarios[0], ())
    record = export.record
    ((_, model),) = record.model_configurations
    role = RegisteredRole(ROLE, model, (("system", DIGEST),), DIGEST)

    def differing(*roles: RegisteredRole, of: RunExport = export) -> set[RecordedSetting]:
        registration = named(DRAFT, agent=record.system.variant, roles=roles)
        return set(setting_differences(registration, of))

    assert not MODEL_SIDE & differing(role)
    other = CallConfiguration(model.model_id, (CallSetting("temperature", 1),))
    for changed, setting in (
        (replace(role, configuration=other), RecordedSetting.MODEL),
        (replace(role, prompt_digests=(("system", "c" * 64),)), RecordedSetting.PROMPTS),
        (
            replace(role, prompt_digests=(("system", DIGEST), ("report", DIGEST))),
            RecordedSetting.PROMPTS,
        ),
        (replace(role, tool_surface_digest="c" * 64), RecordedSetting.TOOL_SURFACE),
    ):
        assert differing(changed) & MODEL_SIDE == {setting}
    # The same three settings under another role's name are another role's: a role the
    # registration does not name, and one it names that the run did not record.
    assert differing(replace(role, name="checker")) & MODEL_SIDE == MODEL_SIDE
    assert differing(role, replace(role, name="checker")) & MODEL_SIDE == MODEL_SIDE

    # The attribution table the dispatches were read by is the registered one's digest.
    assert RecordedSetting.ATTRIBUTION_TABLE in differing(role)
    tabled = with_record(export, attribution_table=attribution_table_digest(TABLE))
    assert RecordedSetting.ATTRIBUTION_TABLE not in differing(role, of=tabled)

    # A system the registration does not hold at all: the frozen fixture has no single-shot.
    stranger = with_record(export, system=System(SystemKind.SINGLE_SHOT, "one-call"))
    assert setting_differences(FROZEN, stranger) == (RecordedSetting.SYSTEM,)


def test_every_role_holds_its_own_registered_prompt_set(world: SealedWorld) -> None:
    # Two roles that hold one registered prompt each cover the set between them and
    # neither ran under it.
    export = agent_export(world, world.scenarios[0], ())
    record = export.record
    ((_, model),) = record.model_configurations
    ((_, selection),) = record.pricing_selections
    both = (("report", DIGEST), ("system", DIGEST))
    roles = tuple(RegisteredRole(name, model, both, DIGEST) for name in ("checker", ROLE))
    registration = named(DRAFT, agent=record.system.variant, roles=roles)
    assert ROLE > "checker"

    def two_roles(*prompts: tuple[str, str, str]) -> RunExport:
        return with_record(
            export,
            model_configurations=(("checker", model), (ROLE, model)),
            pricing_selections=(("checker", selection), (ROLE, selection)),
            tool_surface_digests=(("checker", DIGEST), (ROLE, DIGEST)),
            prompt_digests=prompts,
        )

    split = two_roles(("checker", "report", DIGEST), (ROLE, "system", DIGEST))
    assert set(setting_differences(registration, split)) & MODEL_SIDE == {RecordedSetting.PROMPTS}
    whole = two_roles(
        ("checker", "report", DIGEST),
        ("checker", "system", DIGEST),
        (ROLE, "report", DIGEST),
        (ROLE, "system", DIGEST),
    )
    assert not MODEL_SIDE & set(setting_differences(registration, whole))


# --- Under a bound registration ----------------------------------------------------------------


@pytest.mark.usefixtures("resolved_mechanism")
def test_a_bound_registration_reports_and_refuses_a_dirty_harness_tree(
    world: SealedWorld,
) -> None:
    registration = bound_to(world)
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
    assert artifact.registration.status is RegistrationStatus.BOUND
    assert artifact.registration.frozen_commit == FROZEN_COMMIT
    assert artifact.registration.procedure == procedure_digest(FROZEN)
    eligible, refused = artifact.inventory
    assert (eligible.disposition, eligible.label) == (Disposition.ELIGIBLE, Label.REPORTED)
    assert (refused.disposition, refused.label) == (Disposition.DIRTY_HARNESS, None)
    assert refused.evaluation is not None
    assert made(artifact) == 1
    # Under a draft the same dirty run is a development run like any other, and so it is
    # under a frozen registration, whose world does not exist yet.
    under_draft = stored(
        "runs/b", exported(world, world.scenarios[1], run_id="run-2", tree=TreeState.DIRTY)
    )
    assert only(artifact_of(world, under_draft)).disposition is Disposition.ELIGIBLE
    under_frozen = stored(
        "runs/b",
        exported(
            world, world.scenarios[1], registration=FROZEN, run_id="run-2", tree=TreeState.DIRTY
        ),
    )
    frozen_artifact = artifact_of(world, under_frozen, registration=registration_bytes(FROZEN))
    assert frozen_artifact.label is Label.DEVELOPMENT
    assert only(frozen_artifact).disposition is Disposition.ELIGIBLE


@pytest.mark.usefixtures("resolved_mechanism")
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
        content = registration_bytes(bound_to(world, amendment))
        artifact = artifact_of(world, registration=content, evaluator=changed)
        assert (artifact.label, artifact.registration.declared) == (label, amendment)
        assert artifact.evaluated_by_changed_code
        assert not artifact_of(world, registration=content).evaluated_by_changed_code
    # A draft and a frozen registration are development whatever they declare, and changed
    # code is expected of them.
    for unbound in (DRAFT, FROZEN):
        content = registration_bytes(replace(unbound, amendment=Amendment(OTHER_COMMIT, True)))
        artifact = artifact_of(world, registration=content, evaluator=changed)
        assert (artifact.label, artifact.evaluated_by_changed_code) == (Label.DEVELOPMENT, False)
        assert artifact.evaluator == changed


@pytest.mark.usefixtures("resolved_mechanism")
def test_a_bound_registration_evaluated_against_another_world_refuses(world: SealedWorld) -> None:
    elsewhere = bound("e" * 64, FROZEN, frozen_commit=FROZEN_COMMIT)
    with pytest.raises(ValueError, match=f"bound to the world {'e' * 64}, and this evaluation"):
        artifact_of(world, registration=registration_bytes(elsewhere))


def test_a_bound_registration_is_held_to_the_frozen_one_it_names(world: SealedWorld) -> None:
    made_bound = bound_to(world)
    frozen_bytes = registration_bytes(FROZEN)
    require_binding(made_bound, frozen_bytes)
    # A registration that is not bound binds nothing.
    require_binding(DRAFT, None)
    require_binding(FROZEN, None)
    with pytest.raises(ValueError, match=f"the frozen commit {FROZEN_COMMIT} holds no registr"):
        require_binding(made_bound, None)
    with pytest.raises(ValueError, match="does not decode: this code reads registration format"):
        require_binding(made_bound, b'{"format_version": 1}')
    with pytest.raises(ValueError, match=f"at the frozen commit {FROZEN_COMMIT} is draft, not"):
        require_binding(made_bound, DRAFT_BYTES)
    # A bound file is not a frozen one, even its own.
    with pytest.raises(ValueError, match="is bound, not frozen"):
        require_binding(made_bound, registration_bytes(made_bound))
    # Binding changes the status, the world's version and the commit named, nothing else:
    # each other change is named by the section it is in.
    accounting = replace(made_bound.run_accounting, repeats=made_bound.run_accounting.repeats + 1)
    for changed, section in (
        (replace(made_bound, run_accounting=accounting), "run_accounting"),
        (replace(made_bound, amendment=Amendment(OTHER_COMMIT, True)), "amendment"),
        (
            replace(made_bound, budget=replace(made_bound.budget, ceiling_usd=299)),
            "budget",
        ),
    ):
        with pytest.raises(ValueError, match=f"they differ in {section}$"):
            require_binding(changed, frozen_bytes)


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
    # A frozen registration names the mechanism measure, which this evaluator does not
    # hold until the fact-stage measures are built.
    with pytest.raises(ValueError, match="no mechanism measure is registered as"):
        artifact_of(world, registration=registration_bytes(FROZEN))


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
