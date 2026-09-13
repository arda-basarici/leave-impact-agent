"""The validator's configuration boundary and its composition: a version in, a verdict published.

The validation job takes one value from the command line, the world version, because
everything else it needs is in the bucket under that version: the manifest names the
Frappe company, the Jira project and its fields and the calendar map, the truth bucket
holds the world spec, and the world bucket the scenario specs and the documents. The
run's identifiers — the GitHub run id and attempt that key the verdict, since a rerun
shares the id — come from the runner's environment or, for a local run, from the command
line. The environment's half of the configuration is the shared wiring's, the same names
the generator reads.

The composition here reads three objects, builds the readers from the manifest through
the shared wiring, hands them to the validator's composition, and publishes the verdict
through the one narrow callable the wiring provides: this package names no writer and
chooses no key, so its read-only role holds at source level while its one artifact still
lands (the verdict ruling of the step 12 interview). A verdict is published whether it
approves or refuses — a refusal is evidence too, immutable per execution — and the exit
status says which, so the workflow run is red on a refused world without hiding the
verdict that says why.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from leaveimpact.adapters.manifest import ManifestStage, decode_manifest
from leaveimpact.adapters.object_store.layout import (
    scenario_specs_key,
    verdict_key,
    world_manifest_key,
    world_spec_key,
)
from leaveimpact.adapters.object_store.read import ObjectReader
from leaveimpact.adapters.wiring import (
    ConfigurationError,
    Hosts,
    ObjectReaders,
    Readers,
    VerdictPublisher,
    build_readers,
)
from leaveimpact.core.ids import WorldVersion
from leaveimpact.validator.verdict import Approval, ValidationVerdict, verdict_bytes
from leaveimpact.validator.verify import LiveSystems, validate
from leaveimpact.world.artifacts import SHA256_HEX


@dataclass(frozen=True, slots=True)
class ValidationRequest:
    """What the command line and the runner's identifiers define: which world, which execution."""

    world_version: WorldVersion
    run_id: str
    run_attempt: str


@dataclass(frozen=True, slots=True)
class Published:
    """The verdict as judged and where it landed."""

    verdict: ValidationVerdict
    key: str
    version_id: str

    @property
    def approval(self) -> Approval:
        return self.verdict.approval


def parse_request(argv: Sequence[str], env: Mapping[str, str]) -> ValidationRequest:
    """The request from ``argv``, the run's identifiers from the flags or ``GITHUB_RUN_*``."""
    parser = argparse.ArgumentParser(
        prog="python -m leaveimpact.validator",
        description="Validate a sealed world against its live systems and publish the verdict.",
        exit_on_error=False,
    )
    parser.add_argument("--world-version", required=True, help="the 64-hex world version")
    parser.add_argument("--run-id", default=env.get("GITHUB_RUN_ID", "").strip())
    parser.add_argument("--run-attempt", default=env.get("GITHUB_RUN_ATTEMPT", "").strip())
    try:
        parsed = parser.parse_args(argv)
    except (argparse.ArgumentError, SystemExit) as error:
        raise ConfigurationError(
            f"the command line is not a validation request: {error}"
        ) from error
    if not SHA256_HEX.fullmatch(parsed.world_version):
        raise ConfigurationError(
            f"--world-version is a 64-hex world version, got {parsed.world_version!r}"
        )
    for name, value in (("--run-id", parsed.run_id), ("--run-attempt", parsed.run_attempt)):
        if not value or "/" in value:
            raise ConfigurationError(
                f"{name} is required (or GITHUB_RUN_ID / GITHUB_RUN_ATTEMPT in the environment) "
                f"and carries no slash, got {value!r}"
            )
    return ValidationRequest(WorldVersion(parsed.world_version), parsed.run_id, parsed.run_attempt)


def validate_world(
    request: ValidationRequest,
    hosts: Hosts,
    stores: ObjectReaders,
    publish: VerdictPublisher,
    readers_of: Callable[[Hosts, ObjectReader], Readers] | None = None,
) -> Published:
    """Read the sealed world, judge the live systems, publish the verdict; the result."""
    version = request.world_version
    manifest_bytes = _read(stores.world, world_manifest_key(version), "the world manifest")
    spec_bytes = _read(stores.truth, world_spec_key(version), "the world spec")
    specs_bytes = _read(stores.world, scenario_specs_key(version), "the scenario specs")
    manifest = decode_manifest(manifest_bytes, stage=ManifestStage.PROJECTED)

    readers = (
        build_readers(hosts, manifest, stores.world)
        if readers_of is None
        else readers_of(hosts, stores.world)
    )
    try:
        systems = LiveSystems(
            readers.people,
            readers.work,
            readers.calendar,
            readers.documents,
            readers.documents.held_document_ids,
        )
        verdict = validate(manifest_bytes, spec_bytes, specs_bytes, systems)
    finally:
        readers.close()

    version_id = publish(version, request.run_id, request.run_attempt, verdict_bytes(verdict))
    return Published(verdict, verdict_key(version, request.run_id, request.run_attempt), version_id)


def _read(store: ObjectReader, key: str, what: str) -> bytes:
    stored = store.get(key)
    if stored is None:
        raise ConfigurationError(f"{what} is not in the store at {key!r}: no such sealed world")
    return stored.content
