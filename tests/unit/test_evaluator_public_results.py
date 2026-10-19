"""The projection into the public results, run over the artifact codec's own fixture
artifacts (runs chosen to reach every type; named systems at one repeat and at two) before
any hand-built case: every public type is reached, every optional field is seen both set
and null where a fixture can set it, each copied figure equals the typed artifact's, and
the written form carries nothing per scenario, no listing entry and none of the world
objects' digests or version ids."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from typing import cast

import pytest

from leaveimpact.evaluator import artifact_json
from leaveimpact.evaluator.artifact import EvaluationArtifact
from leaveimpact.evaluator.public_results import project_public_results
from leaveimpact.results import public
from leaveimpact.results.codec import decode_public_results, public_results_bytes
from leaveimpact.results.public import PublicResults
from leaveimpact.world.disclosure import Disclosure
from tests.unit.test_evaluator_artifact_json import artifact_of, named_systems
from tests.unit.throwaway_world import loaded_world

PUBLIC_TYPES = frozenset(
    name
    for name in public.__all__
    if isinstance(getattr(public, name), type) and is_dataclass(getattr(public, name))
)
HEX = frozenset("0123456789abcdef")
# Every field of the written form that may hold a commit or a digest; the committed file's
# own test holds the real file to the same list.
HEX_FIELDS = frozenset(
    {
        "provenance.artifact_digest",
        "provenance.evaluator_commit",
        "provenance.registration_commit",
        "provenance.registration_digest",
        "provenance.registration_procedure",
        "provenance.registration_frozen_commit",
        "provenance.inventory_digest",
        "provenance.inventory_builder_commit",
        "provenance.world_version",
        "disclosures.changed[].before",
        "disclosures.changed[].after",
    }
)

Artifacts = tuple[EvaluationArtifact, EvaluationArtifact, EvaluationArtifact]
Projected = tuple[PublicResults, PublicResults, PublicResults]


@pytest.fixture(scope="module")
def artifacts() -> Artifacts:
    world = loaded_world("golden")
    return artifact_of(world), named_systems(world, 1), named_systems(world, 2)


@pytest.fixture(scope="module")
def projected(artifacts: Artifacts) -> Projected:
    first, second, third = (
        project_public_results(
            artifact_json.artifact_bytes(artifact), world_disclosure=Disclosure.OPEN
        )
        for artifact in artifacts
    )
    return first, second, third


def _visit(value: object, seen: set[str], optionals: dict[tuple[str, str], set[bool]]) -> None:
    if is_dataclass(value) and not isinstance(value, type):
        seen.add(type(value).__name__)
        for field in fields(value):
            member = getattr(value, field.name)
            if "None" in str(field.type):
                optionals.setdefault((type(value).__name__, field.name), set()).add(
                    member is None
                )
            _visit(member, seen, optionals)
    elif isinstance(value, tuple):
        for item in cast("tuple[object, ...]", value):
            _visit(item, seen, optionals)


def test_the_fixture_artifacts_reach_every_public_type_and_both_sides_of_every_optional(
    projected: Projected,
) -> None:
    seen: set[str] = set()
    optionals: dict[tuple[str, str], set[bool]] = {}
    for results in projected:
        _visit(results, seen, optionals)
    assert seen == PUBLIC_TYPES
    one_sided = sorted(
        f"{owner}.{name}" for (owner, name), sides in optionals.items() if len(sides) < 2
    )
    # The fixtures hold one changed path (a file that existed before and not after), every
    # degraded run limited or excluded for a reason, draft registrations that amend nothing
    # and are bound to no commit, a resolved mechanism, and only registered arms; each is
    # written the same way as the optionals the fixtures do exercise on both sides.
    assert one_sided == [
        "ChangedPath.after",
        "ChangedPath.before",
        "DegradedRow.reason",
        "Provenance.registration_amends",
        "Provenance.registration_frozen_commit",
        "PublicResults.mechanism",
        "PublicResults.mechanism_pending",
        "ResultArm.reporting",
    ]


def test_each_copied_figure_is_the_typed_artifacts_own(
    artifacts: Artifacts, projected: Projected
) -> None:
    artifact, results = artifacts[0], projected[0]
    analysis = artifact.analysis
    assert results.provenance.artifact_digest == hashlib.sha256(
        artifact_json.artifact_bytes(artifact)
    ).hexdigest()
    assert results.provenance.world_version == artifact.world.version
    assert results.provenance.registration_digest == artifact.registration.digest
    assert results.provenance.coverage.intended == artifact.coverage.intended
    assert results.plan.seed == analysis.plan.seed
    assert len(results.arms) == len(analysis.arms)
    for arm, written in zip(analysis.arms, results.arms, strict=True):
        assert (written.system, written.condition, written.level) == (
            arm.system.kind.value,
            arm.condition,
            arm.level,
        )
        for cell, public_cell in zip(arm.cells, written.cells, strict=True):
            assert public_cell.cost.pico_usd == cell.cost.pico_usd
            assert public_cell.cost.floors == cell.cost.floors
            assert public_cell.accounting.graded == cell.accounting.graded
            assert (cell.checks is None) == (public_cell.checks is None)
            if cell.checks is not None and public_cell.checks is not None:
                for estimate, row in zip(cell.checks, public_cell.checks, strict=True):
                    assert (row.check, row.reading, row.passed) == (
                        estimate.check,
                        estimate.reading.value,
                        estimate.passed,
                    )
                    assert (row.wilson is None) == (estimate.wilson is None)
                    assert row.unresolved == (
                        None if estimate.unresolved is None else estimate.unresolved.value
                    )
    assert results.primary.unavailable == analysis.primary.unavailable
    assert len(results.not_run) == len(analysis.unbuilt)
    assert results.disclosures.provenance_incidents == len(analysis.provenance_incidents)

    # The named-systems artifact at one repeat resolves the primary with its two-by-two
    # table and the bootstrap of the difference.
    named, resolved = artifacts[1].analysis, projected[1]
    overall = named.primary.overall
    assert overall is not None and resolved.primary.overall is not None
    assert resolved.primary.overall.paired == overall.paired
    assert resolved.primary.overall.two_by_two == overall.two_by_two
    assert overall.interval is not None and resolved.primary.overall.interval is not None
    assert resolved.primary.overall.interval.seed == overall.interval.seed
    assert resolved.primary.overall.interval.low == overall.interval.low
    assert [row.stratum.name for row in resolved.primary.breakdowns] == [
        row.stratum.name for row in named.primary.breakdowns
    ]
    assert named.mechanism is not None and resolved.mechanism is not None
    assert len(resolved.mechanism.contrasts) == len(named.mechanism.contrasts)


def test_the_written_form_round_trips_and_carries_nothing_withheld(
    artifacts: Artifacts, projected: Projected
) -> None:
    artifact, results = artifacts[0], projected[0]
    written = public_results_bytes(results)
    assert decode_public_results(written) == results
    text = written.decode("utf-8")
    assert '"listing"' not in text
    for scenario in artifact.analysis.scenarios:
        assert scenario not in text
    world = artifact.world
    for source in (world.world_spec, world.scenario_specs, world.truth_manifest):
        assert source.digest not in text and source.version_id not in text
    hex_fields = {
        path
        for path, value in leaves(json.loads(text))
        if isinstance(value, str) and len(value) in (40, 64) and set(value) <= HEX
    }
    assert hex_fields <= HEX_FIELDS
    # The fixture's revision has no commit after its one changed path and no bound commit.
    assert hex_fields == HEX_FIELDS - {
        "disclosures.changed[].after",
        "provenance.registration_frozen_commit",
    }


def leaves(value: object, at: str = "") -> list[tuple[str, object]]:
    if isinstance(value, dict):
        return [
            leaf
            for key, member in cast("dict[str, object]", value).items()
            for leaf in leaves(member, f"{at}.{key}" if at else key)
        ]
    if isinstance(value, list):
        return [leaf for item in cast("list[object]", value) for leaf in leaves(item, f"{at}[]")]
    return [(at, value)]


def test_another_format_and_a_missing_field_are_refused_by_name(artifacts: Artifacts) -> None:
    written = artifact_json.encode_artifact(artifacts[0])
    written["format_version"] = 9
    with pytest.raises(ValueError, match="reads artifact format 10, got 9"):
        project_public_results(json.dumps(written).encode(), world_disclosure=Disclosure.OPEN)
    written = artifact_json.encode_artifact(artifacts[0])
    del cast("dict[str, object]", written["analysis"])["headroom"]
    with pytest.raises(ValueError, match="headroom is missing"):
        project_public_results(json.dumps(written).encode(), world_disclosure=Disclosure.OPEN)
