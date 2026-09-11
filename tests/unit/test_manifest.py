"""The world manifest: a projected manifest round-trips through canonical bytes that depend on
its value and never on insertion order; a reader states the stage it can act on and a
checkpoint is refused by name; the record refuses a digest set that is not the three roles
once each, a checkpoint carrying receipts and a corpus scope of another world; the seed,
credentials and every entity, key and fact type are structurally absent; and a malformed
file fails at decode, field by field."""

import ast
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

import leaveimpact.adapters.manifest as manifest_module
from leaveimpact.adapters.calendar.adapter import CalendarConfig
from leaveimpact.adapters.corpus.adapter import CorpusConfig
from leaveimpact.adapters.frappe.adapter import FrappeConfig
from leaveimpact.adapters.jira.adapter import JiraConfig, JiraFields
from leaveimpact.adapters.manifest import (
    MANIFEST_FORMAT,
    ArtifactDigest,
    ArtifactRole,
    CalendarReceipts,
    DocumentReceipts,
    ManifestStage,
    PeopleReceipts,
    Receipts,
    SystemConfigs,
    WorkReceipts,
    WorldManifest,
    decode_manifest,
    encode_manifest,
    manifest_bytes,
)
from leaveimpact.core import Source
from leaveimpact.core.ids import (
    WorldVersion,
    component_id,
    document_id,
    employee_id,
    event_id,
    leave_id,
    team_id,
    work_item_id,
)
from leaveimpact.world import DEFAULT_PARAMS, GENERATOR_VERSION, OrgParams, assemble_world, bundle

VERSION = WorldVersion("a" * 64)
FIELDS = JiraFields(
    ticket_id="customfield_10040",
    owner="customfield_10041",
    opened_on="customfield_10042",
    resolved_on="customfield_10043",
)
SYSTEMS = SystemConfigs(
    frappe=FrappeConfig("World A1B2C3", "WA1"),
    jira=JiraConfig("WAAAAAAAAAA", FIELDS),
    calendar=CalendarConfig(
        {employee_id(1): "cal-one@group.calendar", employee_id(2): "cal-two@group.calendar"}
    ),
    corpus=CorpusConfig(VERSION),
)
RECEIPTS = Receipts(
    people=PeopleReceipts(
        teams={team_id(1): "Department/Platform - WA1"},
        employees={employee_id(2): "Employee/emp_002", employee_id(1): "Employee/emp_001"},
        leaves={leave_id(5): "Leave Application/HR-LAP-2026-00007"},
    ),
    work=WorkReceipts(
        components={component_id(1): "10021"}, work_items={work_item_id(42): "WAAAAAAAAAA-7"}
    ),
    calendar=CalendarReceipts(events={event_id(7): "1f9a0b3c" * 5}),
    documents=DocumentReceipts(documents={document_id(3): "doc_003"}),
)


def digests() -> tuple[ArtifactDigest, ...]:
    return (
        ArtifactDigest(ArtifactRole.WORLD_SPEC, "1" * 64),
        ArtifactDigest(ArtifactRole.SCENARIO_SPECS, "2" * 64),
        ArtifactDigest(ArtifactRole.TRUTH_MANIFEST, "3" * 64),
    )


def manifest(stage: ManifestStage = ManifestStage.PROJECTED, **overrides: object) -> WorldManifest:
    base = WorldManifest(
        stage=stage,
        world_version=VERSION,
        artifacts=digests(),
        generator_version=GENERATOR_VERSION,
        org_params=OrgParams(org_size=8, team_count=2),
        systems=SYSTEMS,
        receipts=RECEIPTS if stage is ManifestStage.PROJECTED else Receipts(),
        observed_sites={Source.JIRA: "jira.example.invalid", Source.FRAPPE: "hr.example.invalid"},
    )
    return replace(base, **overrides) if overrides else base


# --- Round trip and canonical bytes ------------------------------------------------------


def test_a_projected_manifest_round_trips_through_its_bytes() -> None:
    original = manifest()
    decoded = decode_manifest(manifest_bytes(original), stage=ManifestStage.PROJECTED)
    assert decoded == original
    assert decoded.receipts.people.employees[employee_id(2)] == "Employee/emp_002"
    assert decoded.systems.calendar.employee_by_calendar["cal-two@group.calendar"] == employee_id(2)
    assert decoded.digest_of(ArtifactRole.TRUTH_MANIFEST) == "3" * 64


def test_the_bytes_depend_on_the_value_and_not_on_insertion_order() -> None:
    """Two receipts maps with the same pairs in different order encode to one byte sequence."""
    reordered = Receipts(
        people=PeopleReceipts(
            teams=RECEIPTS.people.teams,
            employees={employee_id(1): "Employee/emp_001", employee_id(2): "Employee/emp_002"},
            leaves=RECEIPTS.people.leaves,
        ),
        work=RECEIPTS.work,
        calendar=RECEIPTS.calendar,
        documents=RECEIPTS.documents,
    )
    assert manifest_bytes(manifest(receipts=reordered)) == manifest_bytes(manifest())
    text = manifest_bytes(manifest()).decode("utf-8")
    assert text.startswith('{"format":1,"stage":"projected","world_version":"')
    assert list(json.loads(text)) == [
        "format",
        "stage",
        "world_version",
        "artifacts",
        "generator_version",
        "org_params",
        "systems",
        "receipts",
        "observed_sites",
    ]


def test_a_preparing_manifest_carries_configuration_and_no_receipts() -> None:
    checkpoint = manifest(ManifestStage.PREPARING)
    encoded = encode_manifest(checkpoint)
    assert encoded["receipts"] == {
        "people": {"teams": {}, "employees": {}, "leaves": {}},
        "work": {"components": {}, "work_items": {}},
        "calendar": {"events": {}},
        "documents": {"documents": {}},
    }
    assert decode_manifest(manifest_bytes(checkpoint), stage=None) == checkpoint


# --- The stage gate ----------------------------------------------------------------------


def test_a_reader_that_requires_projected_refuses_a_checkpoint_by_name() -> None:
    content = manifest_bytes(manifest(ManifestStage.PREPARING))
    with pytest.raises(ValueError, match="at stage preparing, projected required"):
        decode_manifest(content, stage=ManifestStage.PROJECTED)
    assert decode_manifest(content, stage=None).stage is ManifestStage.PREPARING
    assert decode_manifest(content, stage=ManifestStage.PREPARING).stage is ManifestStage.PREPARING


# --- What the record refuses -------------------------------------------------------------


def test_the_digests_name_each_role_exactly_once() -> None:
    world_spec, specs, truth = digests()
    with pytest.raises(ValueError, match="exactly once"):
        manifest(artifacts=(world_spec, specs))
    with pytest.raises(ValueError, match="exactly once"):
        manifest(artifacts=(world_spec, specs, truth, truth))


def test_the_corpus_scope_must_be_the_manifest_s_own_world() -> None:
    other = SystemConfigs(
        SYSTEMS.frappe, SYSTEMS.jira, SYSTEMS.calendar, CorpusConfig(WorldVersion("b" * 64))
    )
    with pytest.raises(ValueError, match="scoped to b"):
        manifest(systems=other)


def test_a_digest_and_a_world_version_are_sha256_hex() -> None:
    with pytest.raises(ValueError, match="SHA-256 hex"):
        ArtifactDigest(ArtifactRole.WORLD_SPEC, "not-a-digest")
    with pytest.raises(ValueError, match="SHA-256 hex"):
        ArtifactDigest(ArtifactRole.WORLD_SPEC, "1" * 64 + "\n")
    with pytest.raises(ValueError, match="world version is a SHA-256 hex"):
        manifest(
            world_version=WorldVersion("v1"),
            systems=SystemConfigs(
                SYSTEMS.frappe, SYSTEMS.jira, SYSTEMS.calendar, CorpusConfig(WorldVersion("v1"))
            ),
        )


# --- What is structurally absent ---------------------------------------------------------


def test_no_seed_credential_or_truth_can_enter_the_manifest() -> None:
    """The encoded object never carries a seed; the module never imports an entity, key or
    fact type, so no field could hold one."""
    encoded = json.loads(manifest_bytes(manifest()))
    assert "seed" not in encoded and "seed" not in encoded["org_params"]
    assert set(encoded["systems"]) == {"frappe", "jira", "calendar", "corpus"}
    source = Path("src/leaveimpact/adapters/manifest.py").read_text(encoding="utf-8")
    imported = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    forbidden = {
        "leaveimpact.core.entities",
        "leaveimpact.core.facts",
        "leaveimpact.core.claims",
        "leaveimpact.world.scenario",
        "leaveimpact.world.assembly",
    }
    assert not imported & forbidden, imported & forbidden
    lent_by_artifacts = {
        alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module == "leaveimpact.world.artifacts"
        for alias in node.names
    }
    assert lent_by_artifacts <= {"WORLD_SPEC", "SCENARIO_SPECS", "TRUTH_MANIFEST"}, (
        "the sealed bundle must not become importable through the manifest module"
    )
    assert not any(name.endswith("Credential") for name in dir(manifest_module))


# --- Decode failures ---------------------------------------------------------------------


def test_a_manifest_of_another_format_or_shape_fails_at_decode() -> None:
    encoded = encode_manifest(manifest())
    with pytest.raises(ValueError, match=f"format {MANIFEST_FORMAT}, got 2"):
        decode_manifest(json.dumps({**encoded, "format": 2}), stage=None)
    with pytest.raises(ValueError, match="surplus \\['seed'\\]"):
        decode_manifest(json.dumps({**encoded, "seed": 7}), stage=None)
    with pytest.raises(ValueError, match="missing \\['receipts'\\]"):
        decode_manifest(
            json.dumps({key: value for key, value in encoded.items() if key != "receipts"}),
            stage=None,
        )


def test_a_receipt_key_of_the_wrong_kind_or_an_empty_locator_fails_at_decode() -> None:
    encoded = encode_manifest(manifest())
    receipts = json.loads(json.dumps(encoded["receipts"]))
    receipts["people"]["employees"]["LIA-42"] = "Employee/LIA-42"
    with pytest.raises(ValueError, match="'LIA-42' is not a emp_ id"):
        decode_manifest(json.dumps({**encoded, "receipts": receipts}), stage=None)
    receipts = json.loads(json.dumps(encoded["receipts"]))
    receipts["work"]["work_items"]["ticket_042"] = ""
    with pytest.raises(ValueError, match="locator of ticket_042 is a non-empty string"):
        decode_manifest(json.dumps({**encoded, "receipts": receipts}), stage=None)
    receipts = json.loads(json.dumps(encoded["receipts"]))
    receipts["work"]["work_items"]["emp_001"] = "WAAAAAAAAAA-9"
    with pytest.raises(ValueError, match="'emp_001' is not a ticket_ id"):
        decode_manifest(json.dumps({**encoded, "receipts": receipts}), stage=None)


def test_a_calendar_map_holding_two_people_on_one_calendar_fails_at_decode() -> None:
    encoded = encode_manifest(manifest())
    systems = json.loads(json.dumps(encoded["systems"]))
    systems["calendar"]["calendar_by_employee"]["emp_003"] = "cal-one@group.calendar"
    with pytest.raises(ValueError, match="configured for more than one person"):
        decode_manifest(json.dumps({**encoded, "systems": systems}), stage=None)


# --- From a sealed bundle -----------------------------------------------------------------


def test_a_sealed_bundle_s_digests_record_under_their_roles_and_names() -> None:
    sealed = bundle(assemble_world(7, DEFAULT_PARAMS, date(2026, 1, 1)))
    recorded = manifest(
        world_version=sealed.world_version,
        artifacts=(
            ArtifactDigest(ArtifactRole.TRUTH_MANIFEST, sealed.truth_manifest.digest),
            ArtifactDigest(ArtifactRole.SCENARIO_SPECS, sealed.scenario_specs.digest),
            ArtifactDigest(ArtifactRole.WORLD_SPEC, sealed.world_spec.digest),
        ),
        systems=SystemConfigs(
            SYSTEMS.frappe, SYSTEMS.jira, SYSTEMS.calendar, CorpusConfig(sealed.world_version)
        ),
    )
    assert recorded.digest_of(ArtifactRole.WORLD_SPEC) == sealed.world_spec.digest
    assert [artifact.file_name for artifact in recorded.artifacts] == [
        artifact.name for artifact in sealed.artifacts
    ]
    assert decode_manifest(manifest_bytes(recorded), stage=ManifestStage.PROJECTED) == recorded


def test_a_preparing_manifest_refuses_receipts() -> None:
    with pytest.raises(ValueError, match="preparing manifest carries no receipts"):
        manifest(ManifestStage.PREPARING, receipts=RECEIPTS)


def test_an_artifact_named_under_another_role_s_file_fails_at_decode() -> None:
    encoded = encode_manifest(manifest())
    artifacts = json.loads(json.dumps(encoded["artifacts"]))
    artifacts[0]["file_name"] = "truth-manifest.json"
    with pytest.raises(ValueError, match="world_spec artifact is sealed as world-spec.json"):
        decode_manifest(json.dumps({**encoded, "artifacts": artifacts}), stage=None)
