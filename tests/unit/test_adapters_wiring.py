"""The shared wiring: the deployment from the environment with each missing name named, a base
URL required to carry its scheme, the Google credential read from the file the variable names
and refused when absent or not the authorized-user JSON, the local twin and the buckets
exclusive, the credential values absent from every repr; the stores opened as readers only;
the four readers built from a manifest's resolved configuration, the object-store ones with
no write method at runtime and the vendor ones typed at their read ports; no writer class
nameable through the wiring module; and the verdict publisher writing exactly its one key
under the verdicts prefix, a second execution a new object and the same execution again
the equal case."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from leaveimpact.adapters.manifest import ManifestStage
from leaveimpact.adapters.object_store import layout
from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.adapters.wiring import (
    PREFIX,
    ConfigurationError,
    Stores,
    UploadOutcome,
    build_readers,
    deployment_from_env,
    hosts_from_env,
    inventory_publisher,
    inventory_publisher_over,
    jira_gateway_root,
    readers_for,
    run_export_publisher,
    run_export_publisher_over,
    verdict_publisher,
    world_store_from_env,
    world_store_reader,
)
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.test_manifest import manifest


def environment(tmp_path: Path, **overrides: str) -> dict[str, str]:
    google = tmp_path / "google.json"
    google.write_text(
        json.dumps(
            {"client_id": "cid", "client_secret": "cs", "refresh_token": "refresh-token-value"}
        ),
        encoding="utf-8",
    )
    env = {
        "FRAPPE_BASE_URL": "https://hr.example.invalid/",
        "FRAPPE_API_KEY": "frappe-key-value",
        "FRAPPE_API_SECRET": "s",
        "JIRA_BASE_URL": "https://jira.example.invalid",
        "JIRA_EMAIL": "ops@example.invalid",
        "JIRA_TOKEN": "t",
        "GOOGLE_AUTHORIZED_USER_FILE": str(google),
        "WORLD_BUCKET": "world-bucket",
        "TRUTH_BUCKET": "truth-bucket",
        "AWS_REGION": "eu-central-1",
    }
    env.update(overrides)
    return {PREFIX + name: value for name, value in env.items()}


def local_environment(tmp_path: Path) -> dict[str, str]:
    env = environment(tmp_path, OBJECT_STORE_ROOT=str(tmp_path / "store"))
    for name in ("WORLD_BUCKET", "TRUTH_BUCKET", "AWS_REGION"):
        del env[PREFIX + name]
    return env


def test_the_hosts_read_on_their_own_need_no_store_name(tmp_path: Path) -> None:
    """The investigator's composition is never handed the truth bucket, which a deployment
    requires; the hosts alone read from an environment naming no store."""
    env = environment(tmp_path)
    assert hosts_from_env(env) == deployment_from_env(env).hosts
    for name in ("WORLD_BUCKET", "TRUTH_BUCKET", "AWS_REGION"):
        del env[PREFIX + name]
    assert hosts_from_env(env).jira_base_url == "https://jira.example.invalid"
    with pytest.raises(ConfigurationError, match="WORLD_BUCKET"):
        deployment_from_env(env)
    with pytest.raises(ConfigurationError, match="gateway root"):
        hosts_from_env(env, jira_at_gateway=True)


def test_a_deployment_reads_every_name_once_and_strips_the_url(tmp_path: Path) -> None:
    deployment = deployment_from_env(environment(tmp_path))
    assert deployment.hosts.frappe_base_url == "https://hr.example.invalid"
    assert deployment.hosts.frappe_credential.api_key == "frappe-key-value"
    assert deployment.hosts.jira_credential.email == "ops@example.invalid"
    assert deployment.hosts.calendar_credential.refresh_token == "refresh-token-value"
    assert deployment.buckets is not None
    assert (deployment.buckets.world, deployment.buckets.truth, deployment.buckets.region) == (
        "world-bucket",
        "truth-bucket",
        "eu-central-1",
    )
    assert deployment.local_root is None
    shown = repr(deployment)
    assert "refresh-token-value" not in shown and "frappe-key-value" not in shown


@pytest.mark.parametrize(
    "missing", ["FRAPPE_API_SECRET", "JIRA_TOKEN", "GOOGLE_AUTHORIZED_USER_FILE", "TRUTH_BUCKET"]
)
def test_a_missing_variable_is_named(tmp_path: Path, missing: str) -> None:
    env = environment(tmp_path)
    del env[PREFIX + missing]
    with pytest.raises(ConfigurationError, match=PREFIX + missing):
        deployment_from_env(env)


def test_a_url_without_a_scheme_and_a_bad_google_file_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="FRAPPE_BASE_URL is a base URL"):
        deployment_from_env(environment(tmp_path, FRAPPE_BASE_URL="hr.example.invalid"))
    with pytest.raises(ConfigurationError, match="cannot be read"):
        deployment_from_env(
            environment(tmp_path, GOOGLE_AUTHORIZED_USER_FILE=str(tmp_path / "absent.json"))
        )
    env = environment(tmp_path)
    for content in ('{"client_id": "cid"}', "not json"):
        (tmp_path / "google.json").write_text(content, encoding="utf-8")
        with pytest.raises(ConfigurationError, match="not the authorized-user JSON"):
            deployment_from_env(env)


GATEWAY = "https://api.atlassian.com/ex/jira/9a47936a-48cf-49fb-83c1-c720400755af"


@pytest.mark.parametrize(
    "rejected",
    [
        "http://api.atlassian.com/ex/jira/9a47936a-48cf-49fb-83c1-c720400755af",
        "https://leave-impact-probe.atlassian.net",
        "https://user:pw@api.atlassian.com/ex/jira/9a47936a-48cf-49fb-83c1-c720400755af",
        GATEWAY + "?x=1",
        GATEWAY + "#frag",
        GATEWAY + "/extra",
        GATEWAY + "/rest/api/3",
        "https://api.atlassian.com/ex/jira/",
        "https://api.atlassian.com/ex/jira/not-a-cloud-id",
        "https://api.atlassian.com/ex/confluence/9a47936a-48cf-49fb-83c1-c720400755af",
        "https://api.atlassian.com.evil.invalid/ex/jira/9a47936a-48cf-49fb-83c1-c720400755af",
        "",
    ],
)
def test_the_jira_gateway_root_refuses_everything_but_the_gateway(rejected: str) -> None:
    """A credential-boundary control: read-only rests on this shape, so the table is wide."""
    with pytest.raises(ConfigurationError, match="gateway root"):
        jira_gateway_root(rejected)


def test_the_jira_gateway_root_accepts_the_gateway_and_strips_the_slash() -> None:
    assert jira_gateway_root(GATEWAY) == GATEWAY
    assert jira_gateway_root(" " + GATEWAY + "/ ") == GATEWAY
    upper = GATEWAY[:-36] + GATEWAY[-36:].upper()  # a pasted cloud id keeps its case
    assert jira_gateway_root(upper) == upper


def test_a_reader_deployment_holds_jira_to_the_gateway_and_the_generator_does_not(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigurationError, match="JIRA_BASE_URL must be Atlassian's gateway"):
        deployment_from_env(environment(tmp_path), jira_at_gateway=True)
    reader = deployment_from_env(
        environment(tmp_path, JIRA_BASE_URL=GATEWAY + "/"), jira_at_gateway=True
    )
    assert reader.hosts.jira_base_url == GATEWAY
    generator = deployment_from_env(environment(tmp_path))
    assert generator.hosts.jira_base_url == "https://jira.example.invalid"


def test_the_local_twin_and_the_buckets_are_exclusive_and_the_stores_are_readers(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigurationError, match="not both"):
        deployment_from_env(environment(tmp_path, OBJECT_STORE_ROOT=str(tmp_path / "store")))
    deployment = deployment_from_env(local_environment(tmp_path))
    assert deployment.buckets is None and deployment.local_root == tmp_path / "store"
    stores = readers_for(deployment)
    assert isinstance(stores.truth, LocalObjectReader)
    assert isinstance(stores.world, LocalObjectReader)
    for store in (stores.truth, stores.world):
        assert not hasattr(store, "put_if_absent") and not hasattr(store, "overwrite")


def test_no_writer_class_is_nameable_through_the_wiring_module() -> None:
    import leaveimpact.adapters.wiring as wiring

    for name in ("S3ObjectWriter", "LocalObjectWriter", "SealedDocumentWriter"):
        assert not hasattr(wiring, name), f"{name} is reachable through the wiring"


def test_the_readers_are_built_from_the_manifest_and_the_object_store_ones_cannot_write(
    tmp_path: Path,
) -> None:
    deployment = deployment_from_env(local_environment(tmp_path))
    stores = readers_for(deployment)
    projected = manifest(ManifestStage.PROJECTED)
    readers = build_readers(deployment.hosts, projected, stores.world)
    try:
        assert readers.documents.world_version == projected.world_version
        assert not hasattr(readers.documents, "add_document")
        assert not hasattr(stores.world, "put_if_absent")
    finally:
        readers.close()


def test_the_publisher_writes_exactly_its_key_and_a_rerun_is_a_new_object(
    tmp_path: Path,
) -> None:
    deployment = deployment_from_env(local_environment(tmp_path))
    publish = verdict_publisher(deployment)
    version = manifest().world_version
    first = publish(version, "34724172889", "1", b'{"approval": "approved"}')
    again = publish(version, "34724172889", "1", b'{"approval": "approved"}')
    second = publish(version, "34724172889", "2", b'{"approval": "refused"}')
    assert first == again and first != second
    world = readers_for(deployment).world
    assert world.list_keys(layout.verdicts_prefix(version)) == (
        layout.verdict_key(version, "34724172889", "1"),
        layout.verdict_key(version, "34724172889", "2"),
    )
    assert world.list_keys("") == world.list_keys(layout.verdicts_prefix(version)), (
        "nothing else was written"
    )


COMMIT = "c" * 40
OTHER_READER = "d" * 40


def test_the_run_export_publisher_writes_its_key_and_another_reader_is_another_object(
    tmp_path: Path,
) -> None:
    stores = Stores(buckets=None, local_root=tmp_path / "store")
    publish = run_export_publisher(stores)
    version = manifest().world_version
    first = publish(version, "37135207381", 1, COMMIT, b'{"export": 1}')
    again = publish(version, "37135207381", 1, COMMIT, b'{"export": 1}')
    repaired = publish(version, "37135207381", 1, OTHER_READER, b'{"export": 2}')
    assert first.key == layout.run_export_key(version, "37135207381", 1, COMMIT)
    assert (first.outcome, again.outcome) == (UploadOutcome.CREATED, UploadOutcome.PRESENT_EQUAL)
    assert repaired.key != first.key and repaired.outcome is UploadOutcome.CREATED
    world = readers_for(deployment_from_env(local_environment(tmp_path))).world
    assert world.list_keys(layout.run_prefix(version, "37135207381", 1)) == (
        first.key,
        repaired.key,
    )


def test_a_conflict_comes_back_as_a_value_naming_the_held_digest_and_nothing_overwrites() -> None:
    memory = InMemoryObjectStore()
    publish = run_export_publisher_over(memory)
    version = manifest().world_version
    publish(version, "37135207381", 1, COMMIT, b"held")
    conflict = publish(version, "37135207381", 1, COMMIT, b"other")
    assert conflict.outcome is UploadOutcome.CONFLICT
    assert conflict.existing_digest == hashlib.sha256(b"held").hexdigest()
    held = memory.get(conflict.key)
    assert held is not None and held.content == b"held"


def test_a_put_only_grant_reports_the_unverified_presence() -> None:
    memory = InMemoryObjectStore(readable=False)
    publish = run_export_publisher_over(memory)
    version = manifest().world_version
    assert publish(version, "37135207381", 1, COMMIT, b"held").outcome is UploadOutcome.CREATED
    unverified = publish(version, "37135207381", 1, COMMIT, b"held")
    assert unverified.outcome is UploadOutcome.PRESENT_UNVERIFIED
    assert unverified.existing_digest is None


def test_the_inventory_publisher_names_the_key_by_the_digest_of_the_bytes(tmp_path: Path) -> None:
    stores = Stores(buckets=None, local_root=tmp_path / "store")
    publish = inventory_publisher(stores)
    version = manifest().world_version
    content = b'{"format_version": 1}'
    upload = publish(version, content)
    assert upload.key == layout.inventory_key(version, hashlib.sha256(content).hexdigest())
    assert upload.outcome is UploadOutcome.CREATED
    assert publish(version, content).outcome is UploadOutcome.PRESENT_EQUAL
    memory = InMemoryObjectStore()
    assert inventory_publisher_over(memory)(version, content).key == upload.key
    assert upload.key.startswith(layout.runs_prefix(version))


def test_the_world_store_reads_the_bucket_or_the_root_and_never_the_truth_name(
    tmp_path: Path,
) -> None:
    # The application's half of the stores: the world bucket with its region, or the local
    # twin's root, never both, and never configured with the truth bucket's name.
    bucket = {PREFIX + "WORLD_BUCKET": "world-bucket", PREFIX + "AWS_REGION": "eu-central-1"}
    store = world_store_from_env(bucket)
    assert (store.bucket, store.region, store.local_root) == ("world-bucket", "eu-central-1", None)
    # The S3 reader is not built here: constructing the SDK client reached for the network
    # and the unit level's ban refused it; the local twin's reader exercises the same seam.

    root = {PREFIX + "OBJECT_STORE_ROOT": str(tmp_path / "store")}
    local = world_store_from_env(root)
    assert local.local_root == tmp_path / "store" and local.bucket is None
    local_reader = world_store_reader(local)
    assert isinstance(local_reader, LocalObjectReader)
    assert local_reader.root == tmp_path / "store" / "world"

    with pytest.raises(ConfigurationError, match="not both"):
        world_store_from_env({**bucket, **root})
    with pytest.raises(ConfigurationError, match="AWS_REGION is not set"):
        world_store_from_env({PREFIX + "WORLD_BUCKET": "world-bucket"})
    with pytest.raises(ConfigurationError, match="never configured with the truth bucket"):
        world_store_from_env({**bucket, PREFIX + "TRUTH_BUCKET": "truth-bucket"})
