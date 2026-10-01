"""The sealed world joined: loading the three files rebuilds the very construction records the
world was sealed from, with where each file was read; and every proof refuses the whole world by
name — a file absent, a file the world spec does not cite, three consistent files under another
version's keys, a file that does not decode, the four scenario listings disagreeing, a plan row
and its key disagreeing, a key sealed before its derived sets, three records that describe no one
scenario, a key today's rules do not reproduce. A refusal names files, scenarios and counts and
prints nothing a sealed file holds, in its message or anywhere in its traceback."""

import traceback
from dataclasses import replace

import pytest

from leaveimpact.adapters.object_store.layout import (
    scenario_specs_key,
    truth_manifest_key,
    world_spec_key,
)
from leaveimpact.core import AssessmentReason, ConstraintKey, RunContext, Verdict
from leaveimpact.core.ids import ClauseId, LeaveId, ScenarioId, WorldVersion
from leaveimpact.evaluator.sealed_world import (
    KeysNotReproduced,
    SealedWorld,
    SealedWorldRefused,
    join_scenarios,
    load_sealed_world,
    require_reproduced,
)
from leaveimpact.world import (
    AuthoredVerdict,
    Bundle,
    PlantedWorldSpec,
    ScenarioSpec,
    Tier,
    TruthManifest,
    WorldSpec,
    bundle,
    decode_scenario_specs,
    decode_world_spec,
    truth_manifest_of,
)
from leaveimpact.world.artifacts import digest
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.throwaway_world import SealedStores, composed_world, sealed_stores


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return composed_world("golden")


@pytest.fixture(scope="module")
def sealed(world: WorldSpec) -> Bundle:
    return bundle(world)


@pytest.fixture(scope="module")
def other() -> Bundle:
    """Another world entirely, for files that are well-formed and not this world's."""
    return bundle(composed_world("tier1", seed=3))


@pytest.fixture
def stores(sealed: Bundle) -> SealedStores:
    return sealed_stores(sealed)


@pytest.fixture(scope="module")
def kept(sealed: Bundle) -> SealedStores:
    """The stores the read-only tests share, never mutated."""
    return sealed_stores(sealed)


@pytest.fixture(scope="module")
def loaded(sealed: Bundle, kept: SealedStores) -> SealedWorld:
    """The world loaded once: a load runs the whole-world verification."""
    return load(sealed, kept)


def load(sealed: Bundle, stores: SealedStores) -> SealedWorld:
    return load_sealed_world(sealed.world_version, stores.truth, stores.world)


def replace_object(store: InMemoryObjectStore, key: str, content: bytes) -> None:
    """Another object under ``key``, as a store that held different bytes there would return."""
    del store.objects[key]
    store.put_if_absent(key, content)


# --- The join -----------------------------------------------------------------------------


def test_loading_rebuilds_the_construction_records_the_world_was_sealed_from(
    world: WorldSpec, sealed: Bundle, loaded: SealedWorld
) -> None:
    assert loaded.scenarios == world.scenarios
    assert (loaded.org, loaded.facts) == (world.org, world.facts)
    assert (loaded.version, loaded.generator_version) == (
        sealed.world_version,
        world.generator_version,
    )
    # The golden plan is what makes the equality worth stating: every tier's key shapes,
    # briefs, and keys whose two derived sets hold entries.
    assert len(loaded.scenarios) == 30
    assert any(scenario.briefs for scenario in loaded.scenarios)
    assert any(scenario.key.expected_conflicts for scenario in loaded.scenarios)


def test_each_file_is_recorded_with_its_key_the_version_read_and_its_digest(
    sealed: Bundle, kept: SealedStores, loaded: SealedWorld
) -> None:
    version = sealed.world_version
    for source, key, store, artifact in (
        (loaded.world_spec, world_spec_key(version), kept.truth, sealed.world_spec),
        (loaded.scenario_specs, scenario_specs_key(version), kept.world, sealed.scenario_specs),
        (loaded.truth_manifest, truth_manifest_key(version), kept.truth, sealed.truth_manifest),
    ):
        assert (source.key, source.digest) == (key, artifact.digest)
        assert source.version_id == store.objects[key].version_id


def test_a_runs_expected_context_is_built_from_sealed_data(
    sealed: Bundle, loaded: SealedWorld
) -> None:
    scenario = loaded.scenarios[4]
    assert loaded.scenario(scenario.spec.id) is scenario
    assert loaded.scenario(ScenarioId("scenario_999")) is None
    spec = scenario.spec
    assert loaded.context_of(scenario) == RunContext(
        spec.id, sealed.world_version, spec.leave_id, spec.now, spec.reference_timezone
    )


# --- The proofs over the bytes --------------------------------------------------------------


def test_an_absent_file_refuses_naming_it(sealed: Bundle, stores: SealedStores) -> None:
    version = sealed.world_version
    for store, key, what in (
        (stores.truth, world_spec_key(version), "world spec"),
        (stores.world, scenario_specs_key(version), "scenario specs"),
        (stores.truth, truth_manifest_key(version), "truth manifest"),
    ):
        held = store.objects.pop(key)
        with pytest.raises(SealedWorldRefused, match=f"no sealed {what} for {version}"):
            load(sealed, stores)
        store.objects[key] = held


def test_a_file_the_world_spec_does_not_cite_is_refused(
    sealed: Bundle, other: Bundle, stores: SealedStores
) -> None:
    version = sealed.world_version
    key = truth_manifest_key(version)
    replace_object(stores.truth, key, other.truth_manifest.content)
    with pytest.raises(SealedWorldRefused, match="truth manifest is not the one the world spec"):
        load(sealed, stores)
    replace_object(stores.truth, key, sealed.truth_manifest.content)
    replace_object(stores.world, scenario_specs_key(version), other.scenario_specs.content)
    with pytest.raises(SealedWorldRefused, match="scenario specs is not the one the world spec"):
        load(sealed, stores)


def test_three_consistent_files_under_another_versions_keys_are_refused(
    sealed: Bundle, other: Bundle
) -> None:
    # The files authenticate one another by digest; only the recomputed version shows that
    # they are not the world that was asked for.
    misfiled = sealed_stores(other)
    named = sealed.world_version
    misfiled.truth.put_if_absent(world_spec_key(named), other.world_spec.content)
    misfiled.truth.put_if_absent(truth_manifest_key(named), other.truth_manifest.content)
    misfiled.world.put_if_absent(scenario_specs_key(named), other.scenario_specs.content)
    with pytest.raises(
        SealedWorldRefused, match=f"are world {other.world_version}, not the {named} named"
    ):
        load_sealed_world(named, misfiled.truth, misfiled.world)
    assert load_sealed_world(other.world_version, misfiled.truth, misfiled.world).version == (
        other.world_version
    )


def test_a_file_that_does_not_decode_is_refused_with_the_decoders_reason(
    sealed: Bundle, stores: SealedStores
) -> None:
    replace_object(stores.truth, world_spec_key(sealed.world_version), b'{"artifact":"x"}')
    with pytest.raises(SealedWorldRefused, match="the world spec does not decode$") as refused:
        load(sealed, stores)
    # The decoder's own reason is kept as the detail, out of the message and unchained.
    assert refused.value.detail is not None and "sealed as" in refused.value.detail


def test_a_tampered_world_spec_changes_the_version_it_recomputes_to(
    sealed: Bundle, stores: SealedStores
) -> None:
    # A changed seed still decodes and still cites the other two files' digests.
    tampered = sealed.world_spec.content.replace(b'"seed":7', b'"seed":8', 1)
    assert tampered != sealed.world_spec.content and digest(tampered) != sealed.world_spec.digest
    replace_object(stores.truth, world_spec_key(sealed.world_version), tampered)
    with pytest.raises(SealedWorldRefused, match=f"not the {sealed.world_version} named"):
        load(sealed, stores)
    with pytest.raises(SealedWorldRefused, match="no sealed world spec"):
        load_sealed_world(WorldVersion("f" * 64), stores.truth, stores.world)


# --- The proof that asks the rules ----------------------------------------------------------


def test_a_key_todays_rules_do_not_reproduce_refuses_the_whole_world_without_its_content(
    loaded: SealedWorld,
) -> None:
    require_reproduced(loaded.version, loaded.facts, loaded.scenarios, loaded.org)
    # One authored verdict turned over: the key no longer says what the rules conclude.
    first, *rest = loaded.scenarios
    impact, *others = first.key.impacts
    authored, *probe = impact.must_assess
    flipped = (
        AuthoredVerdict(authored.employee_id, Verdict.NON_VIABLE, (AssessmentReason.SKILL,))
        if authored.verdict is Verdict.VIABLE
        else AuthoredVerdict(authored.employee_id, Verdict.VIABLE)
    )
    drifted_key = replace(
        first.key, impacts=(replace(impact, must_assess=(flipped, *probe)), *others)
    )
    drifted = (replace(first, key=drifted_key), *rest)
    with pytest.raises(KeysNotReproduced) as refused:
        require_reproduced(loaded.version, loaded.facts, drifted, loaded.org)
    message = str(refused.value)
    assert f"the sealed keys of 1 scenario(s) ({first.spec.id})" in message
    # The findings hold expected against actual, which is truth; the message holds neither.
    assert all(finding.scenario_id == first.spec.id for finding in refused.value.findings)
    assert {"viable", "non_viable"} & {refused.value.findings[0].expected.split()[0]}
    for word in ("viable", authored.employee_id, impact.key.artifact.id):
        assert word not in message
    assert isinstance(refused.value, SealedWorldRefused)


def printed(refused: BaseException) -> str:
    """Everything an uncaught refusal, or one a logger formats, would print: the message and
    the traceback of the exception and of every exception chained to it."""
    return "".join(traceback.format_exception(refused))


def test_a_refusal_prints_nothing_a_sealed_file_holds_in_its_whole_traceback(
    sealed: Bundle,
    stores: SealedStores,
    loaded: SealedWorld,
    planted: PlantedWorldSpec,
    specs: tuple[ScenarioSpec, ...],
    manifest: TruthManifest,
) -> None:
    """The message being clean is not enough: Python prints a chained cause in full, and the
    reasons here name ids and values of the sealed files. Each refusal that has an
    underlying reason keeps it as ``detail`` and carries no cause and no context."""
    first, *rest = specs
    # 1. Three records that describe no one scenario: the reason lists the owned leaves.
    foreign = replace(first, leave_id=LeaveId("leave_999"))
    with pytest.raises(SealedWorldRefused) as no_scenario:
        join_scenarios(planted, (foreign, *rest), manifest)
    # 2. A file that does not decode: the reason quotes what the file held.
    held = b'{"artifact":"a-value-only-the-file-holds"}'
    replace_object(stores.truth, world_spec_key(sealed.world_version), held)
    with pytest.raises(SealedWorldRefused) as no_decode:
        load(sealed, stores)
    # 3. A key the rules cannot be asked about: the reason names the clause.
    scenario, *others = loaded.scenarios
    artifact = scenario.key.impacts[0].key.artifact
    unstated = ConstraintKey(ClauseId("clause_999"), artifact)
    asked = replace(scenario, key=replace(scenario.key, constraints=(unstated,)))
    with pytest.raises(SealedWorldRefused) as no_rule:
        require_reproduced(loaded.version, loaded.facts, (asked, *others), loaded.org)
    for refused, sealed_content in (
        (no_scenario, first.leave_id),
        (no_decode, "a-value-only-the-file-holds"),
        (no_rule, "clause_999"),
    ):
        error = refused.value
        assert error.detail is not None and sealed_content in error.detail
        assert error.__cause__ is None and error.__context__ is None
        assert sealed_content not in printed(error)
        assert error.detail not in printed(error)
    # 4. A key today's rules do not reproduce: the findings are an attribute, never printed.
    impact, *more = scenario.key.impacts
    authored, *probe = impact.must_assess
    flipped = (
        AuthoredVerdict(authored.employee_id, Verdict.NON_VIABLE, (AssessmentReason.SKILL,))
        if authored.verdict is Verdict.VIABLE
        else AuthoredVerdict(authored.employee_id, Verdict.VIABLE)
    )
    drifted_key = replace(
        scenario.key, impacts=(replace(impact, must_assess=(flipped, *probe)), *more)
    )
    with pytest.raises(KeysNotReproduced) as not_reproduced:
        require_reproduced(
            loaded.version, loaded.facts, (replace(scenario, key=drifted_key), *others), loaded.org
        )
    text = printed(not_reproduced.value)
    assert not_reproduced.value.__cause__ is None and not_reproduced.value.__context__ is None
    for finding in not_reproduced.value.findings:
        assert finding.expected not in text and finding.actual not in text
        assert finding.subject not in text and finding.artifact_id not in text


# --- The proofs over the decoded files ------------------------------------------------------


@pytest.fixture(scope="module")
def planted(sealed: Bundle) -> PlantedWorldSpec:
    return decode_world_spec(sealed.world_spec.content)


@pytest.fixture(scope="module")
def specs(sealed: Bundle) -> tuple[ScenarioSpec, ...]:
    return decode_scenario_specs(sealed.scenario_specs.content)


@pytest.fixture(scope="module")
def manifest(world: WorldSpec) -> TruthManifest:
    return truth_manifest_of(world)


def test_the_four_listings_name_the_same_scenarios_in_the_same_order(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...], manifest: TruthManifest
) -> None:
    assert len(join_scenarios(planted, specs, manifest)) == len(specs)
    with pytest.raises(SealedWorldRefused, match="the truth manifest lists scenarios"):
        join_scenarios(planted, specs, replace(manifest, scenarios=manifest.scenarios[:-1]))
    with pytest.raises(SealedWorldRefused, match="the scenario specs lists scenarios"):
        join_scenarios(planted, (specs[1], specs[0], *specs[2:]), manifest)


def test_a_plan_row_and_its_key_agree_on_what_both_state(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...], manifest: TruthManifest
) -> None:
    first, *rest = manifest.scenarios
    assert first.key.tier is not Tier.ADVERSARIAL
    moved = replace(first, key=replace(first.key, tier=Tier.ADVERSARIAL))
    with pytest.raises(SealedWorldRefused, match=f"{first.key.scenario_id}: the plan row and"):
        join_scenarios(planted, specs, replace(manifest, scenarios=(moved, *rest)))


def test_a_key_sealed_before_a_derived_set_is_refused_naming_the_set(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...], manifest: TruthManifest
) -> None:
    first, *rest = manifest.scenarios
    for older, named in (
        (replace(first.key, expected_unknowns=None), "its expected unknowns;"),
        (
            replace(first.key, expected_conflicts=None, expected_unknowns=None),
            "its expected conflicts and expected unknowns;",
        ),
    ):
        unavailable = replace(manifest, scenarios=(replace(first, key=older), *rest))
        with pytest.raises(
            SealedWorldRefused, match=f"{first.key.scenario_id} was sealed.*{named}"
        ):
            join_scenarios(planted, specs, unavailable)


def test_three_records_that_describe_no_one_scenario_are_refused_naming_the_scenario(
    planted: PlantedWorldSpec, specs: tuple[ScenarioSpec, ...], manifest: TruthManifest
) -> None:
    first, *rest = specs
    # Each record is well-formed alone; together they name a leave the scenario does not own.
    foreign = replace(first, leave_id=LeaveId("leave_999"))
    with pytest.raises(
        SealedWorldRefused, match=f"{first.id}: the sealed records do not describe one scenario$"
    ) as refused:
        join_scenarios(planted, (foreign, *rest), manifest)
    assert refused.value.detail is not None and "leave_999" in refused.value.detail
