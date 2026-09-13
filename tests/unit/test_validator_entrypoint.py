"""The validator's boundary and composition: the request from the command line with the run's
identifiers from the flags or the runner's environment, a malformed version or a missing
identifier named; and the composition end to end over two in-memory buckets a sealing run
filled — the three objects read, the readers built from the manifest, the verdict judged
against the same in-memory vendors the world was projected into, published at exactly the
execution's key with the approval that every check passed, a world the buckets do not hold
refused by name, and the validator package importing no writer (the import law's claim,
restated here as the composition's: the publisher is the one write and it is a callable)."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.adapters.object_store import layout
from leaveimpact.adapters.object_store.documents import SealedDocumentReader
from leaveimpact.adapters.object_store.read import ObjectReader
from leaveimpact.adapters.wiring import (
    ConfigurationError,
    Hosts,
    ObjectReaders,
    Readers,
    deployment_from_env,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.validator.entrypoint import parse_request, validate_world
from leaveimpact.validator.verdict import Approval, verdict_bytes
from leaveimpact.world import DEFAULT_PARAMS, WorldSpec, assemble_world, bundle
from leaveimpact.world.artifacts import Bundle
from tests.unit.test_adapters_wiring import environment
from tests.unit.test_generator_sealing import Buckets, run

VERSION = WorldVersion("ab" * 32)


@pytest.fixture(scope="module")
def world() -> WorldSpec:
    return assemble_world(7, DEFAULT_PARAMS, date(2026, 1, 1))


@pytest.fixture(scope="module")
def sealed(world: WorldSpec) -> Bundle:
    return bundle(world)


def test_a_request_takes_the_version_and_the_runner_s_identifiers() -> None:
    request = parse_request(
        ["--world-version", VERSION], {"GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "2"}
    )
    assert (request.world_version, request.run_id, request.run_attempt) == (VERSION, "1", "2")
    explicit = parse_request(
        ["--world-version", VERSION, "--run-id", "local", "--run-attempt", "3"], {}
    )
    assert (explicit.run_id, explicit.run_attempt) == ("local", "3")


@pytest.mark.parametrize(
    ("argv", "env", "expected"),
    [
        (["--world-version", "abc"], {"GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1"}, "64-hex"),
        (["--world-version", VERSION], {"GITHUB_RUN_ATTEMPT": "1"}, "--run-id"),
        (["--world-version", VERSION, "--run-id", "a/b", "--run-attempt", "1"], {}, "no slash"),
        ([], {}, "--world-version"),
    ],
)
def test_a_malformed_request_is_named(argv: list[str], env: dict[str, str], expected: str) -> None:
    with pytest.raises(ConfigurationError, match=expected):
        parse_request(argv, env)


def test_the_composition_judges_a_sealed_world_and_publishes_at_the_execution_s_key(
    world: WorldSpec, sealed: Bundle, tmp_path: Path
) -> None:
    buckets = Buckets()
    _, preparation = run(world, sealed, buckets)
    published_verdicts: list[tuple[str, bytes]] = []

    def publish(version: WorldVersion, run_id: str, run_attempt: str, content: bytes) -> str:
        key = layout.verdict_key(version, run_id, run_attempt)
        published_verdicts.append((key, content))
        return buckets.world.put_if_absent(key, content).version_id

    def readers_of(hosts: Hosts, world_store: ObjectReader) -> Readers:
        return Readers(
            preparation.people,
            preparation.work,
            preparation.calendar,
            SealedDocumentReader(world_store, sealed.world_version),
            lambda: None,
        )

    hosts = deployment_from_env(environment(tmp_path)).hosts
    request = parse_request(
        ["--world-version", sealed.world_version, "--run-id", "9", "--run-attempt", "1"], {}
    )
    stores = ObjectReaders(buckets.truth, buckets.world)
    published = validate_world(request, hosts, stores, publish, readers_of)

    assert published.approval is Approval.APPROVED
    assert published.key == layout.verdict_key(sealed.world_version, "9", "1")
    stored = buckets.world.get(published.key)
    assert stored is not None and stored.version_id == published.version_id
    assert stored.content == verdict_bytes(published.verdict)
    assert [key for key, _ in published_verdicts] == [published.key]
    manifest_object = buckets.world.get(layout.world_manifest_key(sealed.world_version))
    assert manifest_object is not None
    assert published.verdict.manifest_digest == hashlib.sha256(manifest_object.content).hexdigest()


def test_a_world_the_buckets_do_not_hold_is_refused_by_name(tmp_path: Path) -> None:
    buckets = Buckets()
    hosts = deployment_from_env(environment(tmp_path)).hosts
    request = parse_request(["--world-version", VERSION, "--run-id", "9", "--run-attempt", "1"], {})

    def never(version: WorldVersion, run_id: str, run_attempt: str, content: bytes) -> str:
        raise AssertionError("nothing is published for a world the buckets do not hold")

    with pytest.raises(ConfigurationError, match="the world manifest is not in the store"):
        validate_world(request, hosts, ObjectReaders(buckets.truth, buckets.world), never)
