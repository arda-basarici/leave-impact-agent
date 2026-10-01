"""The sealed world joined: the three sealed files read as the one world a run is graded against.

A world is sealed as three files with three audiences: the world spec holds what was
planted and each scenario's stable interval, the scenario specs what a run is asked, the
truth manifest every key, the authored facts and the dated fact base. No one of them is
the answer key a grader can use. The key the manifest seals has no stable interval, the
plantings carry no key, and a scenario's ``now`` is in the third file. The evaluator is
the one reader of all three, so the join is here: it rebuilds, per scenario, the very
record the world was constructed with (spec, key, owned records, authored facts,
briefs), which is what the rules were proven against before sealing and what they are
asked again when a run is graded.

The join trusts nothing it can check. The world spec cites the other two files by
digest and both are compared with the bytes read. The world version is recomputed from
the three byte streams and must be the one asked for, since every key embeds the version
and three consistent files filed under another version's keys would otherwise grade a
run against the wrong world. The four listings of the world's scenarios (the plan, the
plantings, the scenario specs, the truth rows) must name the same scenarios in the same
order, and the tier, class and modifiers a plan row and its key both state must agree.
A key sealed before it carried its expected conflicts or its expected unknowns is
refused here: unavailable is not "none expected", and letting it through would grade a
run as though the world expected none.

Every failure is ``SealedWorldRefused`` and refuses the whole world. These are faults of
the sealed files or of this code, never of a run, so nothing is graded against a world
the join could not prove; the loader raises and the job that called it fails.

The loader reads by key through the object-store reader and records, for each file, the
version id the store returned and the digest of the bytes, which the evaluation cites.
It compares no version id with an expected one: the port reads the current version of a
key, the prefixes are create-only, and identity is proven by content, the recomputed
world version. The world spec and the truth manifest come from the truth bucket, the
scenario specs from the world bucket.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from leaveimpact.adapters.object_store.layout import (
    scenario_specs_key,
    truth_manifest_key,
    world_spec_key,
)
from leaveimpact.adapters.object_store.read import ObjectReader, StoredObject
from leaveimpact.core.facts import FactBase
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.worldtime import DateSpan, RunContext
from leaveimpact.world.artifacts import (
    SCENARIO_SPECS,
    TRUTH_MANIFEST,
    WORLD_SPEC,
    Artifact,
    PlantedWorldSpec,
    TruthKey,
    TruthManifest,
    digest,
    world_version,
)
from leaveimpact.world.decoders import decode_scenario_specs, decode_world_spec
from leaveimpact.world.org import OrgSpec
from leaveimpact.world.scenario import Scenario, ScenarioKey, ScenarioSpec
from leaveimpact.world.truth_decoder import decode_truth_manifest
from leaveimpact.world.version import GeneratorVersion


class SealedWorldRefused(Exception):
    """The sealed files cannot be read as the world named; the message says which proof failed."""


@dataclass(frozen=True, slots=True)
class SealedSource:
    """One sealed file as it was read: its key, the version id the store returned, its SHA-256."""

    key: str
    version_id: str
    digest: str


@dataclass(frozen=True, slots=True)
class SealedWorld:
    """The world a run is graded against: the organization, every scenario's construction
    record, the dated fact base, and where each of the three files was read from.

    ``scenarios`` are in the plan's order. ``facts`` is the dated base as sealed; the
    runtime truth the evaluator derives from is built from the scenarios' plantings and
    authored facts, never from this base's dates.
    """

    version: WorldVersion
    generator_version: GeneratorVersion
    org: OrgSpec
    scenarios: tuple[Scenario, ...]
    facts: FactBase
    world_spec: SealedSource
    scenario_specs: SealedSource
    truth_manifest: SealedSource

    def scenario(self, id: ScenarioId) -> Scenario | None:
        """The scenario ``id`` names, or ``None`` when the world holds no such scenario."""
        for scenario in self.scenarios:
            if scenario.spec.id == id:
                return scenario
        return None

    def context_of(self, scenario: Scenario) -> RunContext:
        """The context a run of ``scenario`` on this world must carry, built from sealed data."""
        spec = scenario.spec
        return RunContext(spec.id, self.version, spec.leave_id, spec.now, spec.reference_timezone)


def load_sealed_world(
    version: WorldVersion, truth: ObjectReader, world: ObjectReader
) -> SealedWorld:
    """The sealed world ``version``, read from the two buckets and joined.

    ``truth`` reads the truth bucket, ``world`` the world bucket. Raises
    ``SealedWorldRefused`` when a file is absent or the join cannot prove the three files
    are the world named; a store fault propagates as the store's own exception.
    """
    return join_sealed_world(
        version,
        _read(truth, world_spec_key(version), "world spec", version),
        _read(world, scenario_specs_key(version), "scenario specs", version),
        _read(truth, truth_manifest_key(version), "truth manifest", version),
    )


def join_sealed_world(
    version: WorldVersion,
    world_spec: StoredObject,
    scenario_specs: StoredObject,
    truth_manifest: StoredObject,
) -> SealedWorld:
    """The three files as read, proven to be the world ``version`` and joined.

    Pure over the objects' bytes and version ids. Checked in order: the world spec
    decodes; the digests it cites are those of the other two files; the version recomputed
    from the three byte streams is ``version``; the other two decode; the scenarios join
    (``join_scenarios``).
    """
    planted = _decoded("world spec", decode_world_spec, world_spec.content, version)
    for name, read, cited in (
        ("scenario specs", scenario_specs, planted.scenario_specs_digest),
        ("truth manifest", truth_manifest, planted.truth_manifest_digest),
    ):
        if digest(read.content) != cited:
            raise SealedWorldRefused(
                f"{version}: the sealed {name} is not the one the world spec cites"
            )
    recomputed = world_version(
        (
            _artifact(WORLD_SPEC, world_spec),
            _artifact(SCENARIO_SPECS, scenario_specs),
            _artifact(TRUTH_MANIFEST, truth_manifest),
        )
    )
    if recomputed != version:
        raise SealedWorldRefused(
            f"the three sealed files are world {recomputed}, not the {version} named"
        )
    specs = _decoded("scenario specs", decode_scenario_specs, scenario_specs.content, version)
    manifest = _decoded("truth manifest", decode_truth_manifest, truth_manifest.content, version)
    return SealedWorld(
        version=version,
        generator_version=planted.generator_version,
        org=planted.org,
        scenarios=join_scenarios(planted, specs, manifest),
        facts=manifest.facts,
        world_spec=_source(world_spec),
        scenario_specs=_source(scenario_specs),
        truth_manifest=_source(truth_manifest),
    )


def join_scenarios(
    planted: PlantedWorldSpec, specs: Sequence[ScenarioSpec], manifest: TruthManifest
) -> tuple[Scenario, ...]:
    """Every scenario's construction record, rebuilt from the three decoded files.

    The plan, the plantings, the scenario specs and the truth rows name the same scenarios
    in the same order; a plan row and its key agree on the tier, class and modifiers both
    state; each key is completed with its planting's stable interval; and the three records
    of a scenario describe one scenario, which the record's own constructor checks.
    ``SealedWorldRefused`` names the listing or the scenario that fails.
    """
    listed = {
        "the plan": [row.scenario_id for row in planted.plan],
        "the plantings": [planting.scenario_id for planting in planted.scenarios],
        "the scenario specs": [spec.id for spec in specs],
        "the truth manifest": [row.key.scenario_id for row in manifest.scenarios],
    }
    reference = listed["the plan"]
    for name, ids in listed.items():
        if ids != reference:
            raise SealedWorldRefused(
                f"{name} lists scenarios {ids} and the plan {reference}: the sealed files "
                "hold the same scenarios in the same order"
            )
    scenarios: list[Scenario] = []
    for row, planting, spec, truth in zip(
        planted.plan, planted.scenarios, specs, manifest.scenarios, strict=True
    ):
        key = truth.key
        stated = (key.tier, key.scenario_class, key.modifiers)
        if (row.tier, row.scenario_class, row.modifiers) != stated:
            raise SealedWorldRefused(
                f"{row.scenario_id}: the plan row and the key disagree on the tier, class or "
                f"modifiers ({row.tier.value}, {row.scenario_class.value}, "
                f"{[modifier.value for modifier in row.modifiers]} against {key.tier.value}, "
                f"{key.scenario_class.value}, {[modifier.value for modifier in key.modifiers]})"
            )
        complete = complete_key(key, planting.stable_interval)
        try:
            scenarios.append(
                Scenario(spec, complete, planting.owned, truth.authored_facts, truth.briefs)
            )
        except ValueError as problem:
            raise SealedWorldRefused(
                f"{row.scenario_id}: the sealed records do not describe one scenario: {problem}"
            ) from problem
    return tuple(scenarios)


def complete_key(key: TruthKey, stable_interval: DateSpan) -> ScenarioKey:
    """The key a grader uses: the sealed key with the stable interval its planting carries.

    A key sealed before it carried its expected conflicts or its expected unknowns is
    refused, naming the set: unavailable is a different statement from "none expected",
    and grading it as none would count a report's conflicts and unknowns as errors.
    """
    conflicts, unknowns = key.expected_conflicts, key.expected_unknowns
    if conflicts is None or unknowns is None:
        unavailable = " and ".join(
            name
            for name, value in (
                ("expected conflicts", conflicts),
                ("expected unknowns", unknowns),
            )
            if value is None
        )
        raise SealedWorldRefused(
            f"{key.scenario_id} was sealed before a key carried its {unavailable}; unavailable "
            "is not none expected, and this evaluator does not grade such a key"
        )
    return ScenarioKey(
        scenario_id=key.scenario_id,
        tier=key.tier,
        scenario_class=key.scenario_class,
        modifiers=key.modifiers,
        impacts=key.impacts,
        constraints=key.constraints,
        distractors=key.distractors,
        stable_interval=stable_interval,
        required_sources=key.required_sources,
        expected_conflicts=conflicts,
        expected_unknowns=unknowns,
    )


def _read(store: ObjectReader, key: str, what: str, version: WorldVersion) -> StoredObject:
    stored = store.get(key)
    if stored is None:
        raise SealedWorldRefused(f"no sealed {what} for {version}: nothing to grade against")
    return stored


def _decoded[T](
    what: str, decode: Callable[[bytes], T], content: bytes, version: WorldVersion
) -> T:
    try:
        return decode(content)
    except ValueError as problem:
        raise SealedWorldRefused(f"{version}: the {what} does not decode: {problem}") from problem


def _artifact(name: str, stored: StoredObject) -> Artifact:
    return Artifact(name, stored.content, digest(stored.content))


def _source(stored: StoredObject) -> SealedSource:
    return SealedSource(stored.key, stored.version_id, digest(stored.content))


__all__ = [
    "SealedSource",
    "SealedWorld",
    "SealedWorldRefused",
    "complete_key",
    "join_sealed_world",
    "join_scenarios",
    "load_sealed_world",
]
