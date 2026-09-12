"""The validator's composition over a projection the real projectors landed in the in-memory
ports: a faithful projection is approved with every check passed and the verdict's provenance
naming the manifest it judged; the integrity chain refuses a tampered or swapped input before a
single read; a manifest short of ``projected`` refuses; an unmatched scenario refuses; a foreign
record fails exactness, marks fidelity and every view not run with the reason, and refuses; a
mismatched record and a shifted event each refuse naming the finding; the verdict's bytes are
canonical and carry the validator version; a dead source raises through."""

import hashlib
import json
from dataclasses import replace
from datetime import date, timedelta
from typing import cast

import pytest

from leaveimpact.adapters.manifest import ManifestStage, WorldManifest, manifest_bytes
from leaveimpact.core import Source, SourceUnreachable
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind, EntityKind
from leaveimpact.core.ids import clause_id, document_id, work_item_id
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.generator.realize import realize
from leaveimpact.validator import (
    VALIDATOR_VERSION,
    Approval,
    CheckStatus,
    IntegrityRefused,
    LiveSystems,
    ValidationVerdict,
    validate,
    verdict_bytes,
)
from leaveimpact.world import Bundle, WorldSpec
from tests.unit.test_generator_realize import FakePreparation, MemoryStore, prepared, sealed, world

__all__ = ["sealed", "world"]  # the fixtures, re-exported for pytest to find


@pytest.fixture
def landed(world: WorldSpec, sealed: Bundle) -> tuple[WorldManifest, FakePreparation]:
    """The world projected by the real projectors into the fakes, the manifest at projected."""
    fakes = FakePreparation()
    store = MemoryStore()
    manifest = realize(world, sealed, prepared(sealed), fakes, store)
    assert manifest.stage is ManifestStage.PROJECTED
    return manifest, fakes


def systems_of(fakes: FakePreparation) -> LiveSystems:
    return LiveSystems(
        fakes.people, fakes.work, fakes.calendar, fakes.documents, fakes.documents.held_document_ids
    )


def judged(manifest: WorldManifest, sealed: Bundle, fakes: FakePreparation) -> ValidationVerdict:
    return validate(
        manifest_bytes(manifest),
        sealed.world_spec.content,
        sealed.scenario_specs.content,
        systems_of(fakes),
    )


# --- Approval -----------------------------------------------------------------------------


def test_a_faithful_projection_is_approved_with_every_check_passed(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    verdict = judged(manifest, sealed, fakes)
    assert verdict.approval is Approval.APPROVED
    assert {r.status for r in (*verdict.exactness, *verdict.fidelity, *verdict.views)} == {
        CheckStatus.PASSED
    }
    assert {r.check.kind for r in verdict.exactness} == {
        EntityKind.EMPLOYEE,
        EntityKind.TEAM,
        EntityKind.COMPONENT,
        EntityKind.WORK_ITEM,
        EntityKind.LEAVE,
        EntityKind.EVENT,
        EntityKind.DOCUMENT,
    }
    assert len(verdict.views) == 10
    assert [v.scenario_id for v in verdict.views] == [
        f"scenario_{n:03d}" for n in range(1, len(verdict.views) + 1)
    ]


def test_the_verdict_names_the_manifest_it_judged_and_the_logic_that_judged(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    verdict = judged(manifest, sealed, fakes)
    assert verdict.world_version == sealed.world_version
    assert verdict.manifest_digest == hashlib.sha256(manifest_bytes(manifest)).hexdigest()
    assert verdict.artifacts == manifest.artifacts
    assert verdict.validator_version == VALIDATOR_VERSION
    encoded = json.loads(verdict_bytes(verdict))
    assert encoded["approval"] == "approved" and encoded["validator_version"] == VALIDATOR_VERSION
    assert verdict_bytes(verdict) == canonical_bytes(cast(JsonObject, encoded))
    assert "timestamp" not in encoded


# --- The integrity chain, before any read -------------------------------------------------


def dead(fakes: FakePreparation) -> LiveSystems:
    """Every source switched off: a read of any kind raises, so a refusal proves no read."""
    for store in (fakes.people, fakes.work, fakes.calendar, fakes.documents):
        store.reachable = False
    return systems_of(fakes)


def test_a_tampered_world_spec_is_refused_before_any_read(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    with pytest.raises(IntegrityRefused, match="the world spec does not match the digest"):
        validate(
            manifest_bytes(manifest),
            sealed.world_spec.content + b" ",
            sealed.scenario_specs.content,
            dead(fakes),
        )


def test_swapped_scenario_specs_are_refused_by_the_world_specs_own_digest(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    with pytest.raises(IntegrityRefused, match="the scenario specs does not match the digest"):
        validate(
            manifest_bytes(manifest),
            sealed.world_spec.content,
            sealed.world_spec.content,
            dead(fakes),
        )


def test_a_manifest_short_of_projected_is_refused(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    preparing = replace(manifest, stage=ManifestStage.PREPARING)
    with pytest.raises(ValueError, match="projected required"):
        validate(
            manifest_bytes(preparing),
            sealed.world_spec.content,
            sealed.scenario_specs.content,
            dead(fakes),
        )


def test_a_manifest_recording_another_truth_is_refused(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    encoded = cast(JsonObject, json.loads(manifest_bytes(manifest)))
    artifacts = cast(list[JsonObject], encoded["artifacts"])
    truth = next(item for item in artifacts if item["role"] == "truth_manifest")
    truth["digest"] = "0" * 64
    with pytest.raises(IntegrityRefused, match="different truth manifests"):
        validate(
            canonical_bytes(encoded),
            sealed.world_spec.content,
            sealed.scenario_specs.content,
            dead(fakes),
        )


def test_a_manifest_recording_other_scenario_specs_is_refused_not_carried_into_the_verdict(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    # The scenario specs authenticate against the world spec, so the manifest's copy of
    # their digest could be wrong and yet reach the verdict as provenance; it is compared.
    manifest, fakes = landed
    encoded = cast(JsonObject, json.loads(manifest_bytes(manifest)))
    artifacts = cast(list[JsonObject], encoded["artifacts"])
    specs = next(item for item in artifacts if item["role"] == "scenario_specs")
    specs["digest"] = "0" * 64
    with pytest.raises(IntegrityRefused, match="different scenario specs"):
        validate(
            canonical_bytes(encoded),
            sealed.world_spec.content,
            sealed.scenario_specs.content,
            dead(fakes),
        )


def test_the_enumerations_are_read_once_and_the_windowed_kinds_per_scenario(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, fakes = landed
    calls: dict[str, int] = {}

    def counted(store: object, name: str) -> None:
        original = getattr(store, name)

        def wrapped(*args: object, **kwargs: object) -> object:
            calls[name] = calls.get(name, 0) + 1
            return original(*args, **kwargs)

        monkeypatch.setattr(store, name, wrapped)

    for store, name in (
        (fakes.people, "employees"),
        (fakes.work, "components"),
        (fakes.work, "work_items"),
        (fakes.people, "leaves_within"),
        (fakes.calendar, "events_within"),
    ):
        counted(store, name)
    verdict = judged(manifest, sealed, fakes)
    assert verdict.approval is Approval.APPROVED
    scenarios = len(verdict.views)
    assert calls == {
        "employees": 1,
        "components": 1,
        "work_items": 1,
        "leaves_within": 1 + scenarios,
        "events_within": 1 + scenarios,
    }


def test_an_unmatched_scenario_between_the_two_files_is_refused(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    specs = cast(JsonObject, json.loads(sealed.scenario_specs.content))
    rows = cast(list[JsonObject], specs["scenarios"])
    rows.pop()
    # The spec's own digest catches the edit first; pin the join by re-citing the edited bytes.
    edited = canonical_bytes(specs)
    spec = cast(JsonObject, json.loads(sealed.world_spec.content))
    cast(JsonObject, spec["artifacts"])["scenario-specs.json"] = hashlib.sha256(edited).hexdigest()
    spec_bytes = canonical_bytes(spec)
    encoded = cast(JsonObject, json.loads(manifest_bytes(manifest)))
    artifacts = cast(list[JsonObject], encoded["artifacts"])
    for role, content in (("world_spec", spec_bytes), ("scenario_specs", edited)):
        row = next(item for item in artifacts if item["role"] == role)
        row["digest"] = hashlib.sha256(content).hexdigest()
    with pytest.raises(
        IntegrityRefused, match="missing from the scenario specs \\['scenario_010'\\]"
    ):
        validate(canonical_bytes(encoded), spec_bytes, edited, dead(fakes))


# --- Findings -----------------------------------------------------------------------------


def test_a_foreign_record_fails_exactness_and_gates_what_depends_on_it(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    stray = replace(next(iter(fakes.work.tickets.values())), id=work_item_id(999))
    fakes.work.add_work_item(stray)
    verdict = judged(manifest, sealed, fakes)
    assert verdict.approval is Approval.REFUSED
    (items,) = [r for r in verdict.exactness if r.check.kind is EntityKind.WORK_ITEM]
    assert items.status is CheckStatus.FAILED and items.check.foreign == ("ticket_999",)
    (fidelity,) = [r for r in verdict.fidelity if r.kind is EntityKind.WORK_ITEM]
    assert fidelity.status is CheckStatus.NOT_RUN and fidelity.reason == "identity exactness failed"
    assert {v.status for v in verdict.views} == {CheckStatus.NOT_RUN}
    assert {v.reason for v in verdict.views} == {"identity exactness failed for work_item"}
    others = [r for r in verdict.exactness if r.check.kind is not EntityKind.WORK_ITEM]
    assert {r.status for r in others} == {CheckStatus.PASSED}


def test_a_foreign_document_is_seen_only_through_the_versions_inspection(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    # The structured tier plants no documents, so the port's reads by id would find nothing
    # to compare and the foreign direction is visible through the inspection alone.
    manifest, fakes = landed
    stray = Document(
        document_id(999),
        "A policy nobody planted",
        DocumentKind.POLICY,
        date(2026, 1, 1),
        (DocumentSection(clause_id(999), "Cover is optional."),),
    )
    fakes.documents.add_document(stray)
    verdict = judged(manifest, sealed, fakes)
    (docs,) = [r for r in verdict.exactness if r.check.kind is EntityKind.DOCUMENT]
    assert docs.status is CheckStatus.FAILED and docs.check.foreign == ("doc_999",)
    assert "by inspection" in docs.scope
    assert {v.status for v in verdict.views} == {CheckStatus.PASSED}, "documents gate no view"
    assert verdict.approval is Approval.REFUSED


def test_a_record_read_back_with_other_content_refuses_naming_the_fields(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    first = next(iter(fakes.people.leaves))
    fakes.people.leaves[first] = replace(
        fakes.people.leaves[first], end=fakes.people.leaves[first].end + timedelta(days=1)
    )
    verdict = judged(manifest, sealed, fakes)
    (leaves,) = [r for r in verdict.fidelity if r.kind is EntityKind.LEAVE]
    (mismatch,) = leaves.mismatches
    assert mismatch.ref.id == first and mismatch.differing_fields == ("end",)
    assert verdict.approval is Approval.REFUSED


def test_an_event_read_back_an_hour_late_refuses_in_the_view_of_its_scenario(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle, world: WorldSpec
) -> None:
    manifest, fakes = landed
    owner = next(s for s in world.scenarios if s.owned.events)
    event = owner.owned.events[0].entity
    fakes.calendar.events[event.id] = replace(
        event, start=event.start + timedelta(hours=1), end=event.end + timedelta(hours=1)
    )
    verdict = judged(manifest, sealed, fakes)
    failed = [v for v in verdict.views if v.status is CheckStatus.FAILED]
    assert [v.scenario_id for v in failed] == [owner.spec.id]
    assert failed[0].disagreement is not None and failed[0].disagreement.missing
    encoded = json.loads(verdict_bytes(verdict))
    row = next(v for v in encoded["views"] if v["scenario_id"] == owner.spec.id)
    assert row["missing"] and row["surplus"] and row["status"] == "failed"
    assert verdict.approval is Approval.REFUSED


def test_a_dead_source_raises_through(
    landed: tuple[WorldManifest, FakePreparation], sealed: Bundle
) -> None:
    manifest, fakes = landed
    fakes.calendar.reachable = False
    with pytest.raises(SourceUnreachable) as caught:
        judged(manifest, sealed, fakes)
    assert caught.value.source is Source.CALENDAR
