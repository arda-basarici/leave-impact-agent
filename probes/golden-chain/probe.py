"""Golden chain: are the bytes on record the bytes that were sealed, link by link?

The M1 repository audit's E-002 (the step 1 rulings of the investigator milestone,
2026-09-27): a provenance audit of the golden world, never a semantic one. Every object
the record names is fetched at exactly the version id the record holds, hashed as raw
bytes, and each declared link between objects is checked against those digests. JSON is
decoded only to read declared links; nothing is re-encoded here (that is E-003's job).

The pass criterion, preregistered as the twenty-three predicates below; every one is
evaluated, the
capture is written whole, and the exit is nonzero if any is false:

- ``manifest``: the manifest fetched at its recorded version decodes at ``projected``,
  names the golden world version, and records a version id for the three sealed
  artifacts and every document.
- ``artifacts``: the world spec and the truth manifest (truth bucket) and the scenario
  specs (world bucket), each fetched at the version the manifest records, hash to the
  digest the manifest holds for its role; the world spec's own citations of the other
  two files' digests agree; and the world version recomputed from the three raw byte
  streams (each prefixed by its file name, in the sealing order) equals the golden
  version. This is the content-addressed link the audit asked for above all.
- ``documents``: every document the manifest records a version for is fetched at that
  version and hashes to the canonical bytes of the same document as the world spec
  planted it; the set of ids in the manifest equals the set the world spec plants.
- ``verdicts``: exactly two verdicts with distinct keys, fetched at the inventory's
  version ids, each saying ``approved``, naming the golden version, carrying the
  manifest digest equal to the SHA-256 of the fetched manifest bytes and the three
  artifact digests equal to the manifest's.
- ``audit``: exactly the four sealed audit objects (index, rulings, summary,
  checklist), fetched at the inventory's version ids, hash to the digests the stream's
  sealed-objects record holds; the index hashes to the
  audit identity that names its prefix; the index's rulings, summary and checklist
  digests equal the objects beside it; the index names the golden version, the
  manifest's generator version and one of the two verdict keys; and the stream's
  staging copies hash equal to the sealed objects.
- ``versions``: every response carried exactly the version id requested.

Read-only is a property of this program, not of the principal: every read is a
``GetObject`` with a ``VersionId``; no list, no latest-version read, no write exists
here. It runs from a workstation under the administrative ``leave-impact`` profile,
the one identity that reads both buckets and the identity that wrote the audit, so
FINDINGS says so. The inventory is the stream's fixed record, handed in through
``LEAVE_IMPACT_SEALED_INVENTORY``; the staging copies sit in the same folder. The
capture, under ``captures/golden-chain/``, records locators (bucket, key, version id),
digests and verdicts, and no content: keys and version ids are publishable by ruling
(they are content-addressed or grant nothing without a credential), the objects are the
benchmark's private truth and its unreleased scenarios.

Run: ``uv run python probes/golden-chain/probe.py`` with the profile and the inventory
variable set. Exit 0 only when every predicate is true and the capture was written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from leaveimpact.adapters.manifest import ManifestStage, WorldManifest, decode_manifest
from leaveimpact.adapters.object_store.layout import (
    document_id_of,
    scenario_specs_key,
    truth_manifest_key,
    world_manifest_key,
    world_spec_key,
)
from leaveimpact.adapters.object_store.s3 import s3_client
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import (
    array_field,
    as_object,
    string_field,
)
from leaveimpact.world.artifacts import (
    SCENARIO_SPECS,
    TRUTH_MANIFEST,
    WORLD_SPEC,
    Artifact,
    document_bytes,
    world_version,
)
from leaveimpact.world.decoders import decode_world_spec

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

Json = dict[str, Any]

CAPTURE_ROOT = Path(__file__).resolve().parents[1] / "captures" / "golden-chain"
INVENTORY_VARIABLE = "LEAVE_IMPACT_SEALED_INVENTORY"
_TRUTH_PREFIXES = ("world-spec/", "truth-manifest/")
AUDIT_OBJECTS = frozenset({"index.json", "rulings.md", "summary.md", "checklist.md"})


class ConfigurationError(Exception):
    """Nothing was probed: the inventory or the credentials are not there."""


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# --- the capture: declared predicates, written once -----------------------------------


class Capture:
    """One run's evidence, assembled in memory and written once, never overwritten."""

    def __init__(self, directory: Path, stem: str) -> None:
        self.directory = directory
        self.stem = stem
        self.data: Json = {"execution": "started", "acceptance": "failed", "checks": {}}
        self._required: list[tuple[str, str]] = []

    def require(self, *predicates: tuple[str, str]) -> None:
        """Declare the (check, field) booleans that must all be true for the run to pass."""
        self._required.extend(predicates)

    def judge(self) -> list[str]:
        """The declared predicates that are not true: absent, false or never recorded."""
        checks = cast(Json, self.data["checks"])
        return [
            f"{check}.{field}"
            for check, field in self._required
            if cast(Json, checks.get(check, {})).get(field) is not True
        ]

    def check(self, name: str, **fields: Any) -> Json:
        record = dict(fields)
        cast(Json, self.data["checks"])[name] = record
        print(f"{name}: {json.dumps(record, default=str, ensure_ascii=False)}")
        return record

    def write(self) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        attempt = len(list(self.directory.glob(f"{self.stem}-run-*.json"))) + 1
        path = self.directory / f"{self.stem}-run-{attempt:02d}.json"
        if path.exists():
            raise RuntimeError(f"{path} exists; a capture is never overwritten")
        text = json.dumps({"attempt": attempt, **self.data}, indent=2, ensure_ascii=False)
        path.write_text(text + "\n", encoding="utf-8")
        return path


# --- the inventory and the versioned reader --------------------------------------------


def load_inventory() -> tuple[Json, Path]:
    """The stream's fixed inventory and the folder it lives in (the staging copies' home)."""
    path = os.environ.get(INVENTORY_VARIABLE)
    if path is None:
        raise ConfigurationError(
            f"{INVENTORY_VARIABLE} is not set; the inventory lives in the stream"
        )
    file = Path(path)
    return cast(Json, json.loads(file.read_text(encoding="utf-8"))), file.parent


class Reader:
    """Every get names a version id; the returned one is recorded and must match."""

    def __init__(self, s3: S3Client, capture: Capture) -> None:
        self._s3 = s3
        self._fetched: list[Json] = []
        self._capture = capture

    def get(self, bucket: str, key: str, version_id: str) -> bytes:
        response = self._s3.get_object(Bucket=bucket, Key=key, VersionId=version_id)
        returned = cast("dict[str, Any]", response).get("VersionId")
        content = response["Body"].read()
        self._fetched.append(
            {
                "bucket": bucket,
                "key": key,
                "version_id": version_id,
                "returned_version_id": returned,
                "version_matches": returned == version_id,
                "size": len(content),
                "sha256": sha256(content),
            }
        )
        return content

    def record(self) -> None:
        """The ``versions`` check: one row per fetched object, one predicate over all rows."""
        self._capture.check(
            "versions",
            fetched=len(self._fetched),
            all_match=all(row["version_matches"] for row in self._fetched),
            objects=self._fetched,
        )


def bucket_for(inventory: Json, key: str) -> str:
    buckets = cast(Json, inventory["buckets"])
    return str(buckets["truth"] if key.startswith(_TRUTH_PREFIXES) else buckets["world"])


# --- the links ---------------------------------------------------------------------------


def check_manifest(
    reader: Reader, capture: Capture, inventory: Json, version: WorldVersion
) -> tuple[WorldManifest, bytes]:
    world = next(w for w in cast(list[Json], inventory["worlds"]) if w["version"] == version)
    key = world_manifest_key(version)
    content = reader.get(
        bucket_for(inventory, key), key, str(cast(Json, world["manifest"])["version_id"])
    )
    manifest = decode_manifest(content, stage=ManifestStage.PROJECTED)
    documents = [k for k in manifest.object_versions if document_id_of(version, k)]
    artifacts = [world_spec_key(version), truth_manifest_key(version), scenario_specs_key(version)]
    capture.check(
        "manifest",
        key=key,
        sha256=sha256(content),
        decodes_projected=True,
        names_golden_version=manifest.world_version == version,
        generator_version=manifest.generator_version,
        records_the_three_artifacts=all(k in manifest.object_versions for k in artifacts),
        records_documents=bool(documents),
        document_count=len(documents),
        role_digests={a.role.value: a.digest for a in manifest.artifacts},
    )
    return manifest, content


def check_artifacts(
    reader: Reader,
    capture: Capture,
    inventory: Json,
    version: WorldVersion,
    manifest: WorldManifest,
) -> tuple[bytes, dict[str, str]]:
    """The three sealed artifacts against the manifest, the spec's citations, and the version."""
    keys = {
        WORLD_SPEC: world_spec_key(version),
        SCENARIO_SPECS: scenario_specs_key(version),
        TRUTH_MANIFEST: truth_manifest_key(version),
    }
    contents = {
        name: reader.get(bucket_for(inventory, key), key, manifest.object_versions[key])
        for name, key in keys.items()
    }
    digests = {name: sha256(content) for name, content in contents.items()}
    by_file = {a.file_name: a.digest for a in manifest.artifacts}
    spec = decode_world_spec(contents[WORLD_SPEC])
    recomputed = world_version(
        tuple(
            Artifact(name, contents[name], digests[name])
            for name in (WORLD_SPEC, SCENARIO_SPECS, TRUTH_MANIFEST)
        )
    )
    capture.check(
        "artifacts",
        keys=keys,
        sha256=digests,
        each_equals_the_manifests_role_digest=all(digests[n] == by_file[n] for n in keys),
        spec_cites_scenario_specs=spec.scenario_specs_digest == digests[SCENARIO_SPECS],
        spec_cites_truth_manifest=spec.truth_manifest_digest == digests[TRUTH_MANIFEST],
        recomputed_world_version=recomputed,
        recomputed_equals_golden=recomputed == version,
    )
    return contents[WORLD_SPEC], digests


def check_documents(
    reader: Reader,
    capture: Capture,
    inventory: Json,
    version: WorldVersion,
    manifest: WorldManifest,
    spec_bytes: bytes,
) -> None:
    """Every sealed document against the same document as the world spec planted it."""
    spec = decode_world_spec(spec_bytes)
    planted = {
        document.entity.id: document_bytes(document.entity)
        for scenario in spec.scenarios
        for document in scenario.owned.documents
    }
    rows: list[Json] = []
    for key, version_id in manifest.object_versions.items():
        document_id = document_id_of(version, key)
        if document_id is None:
            continue
        content = reader.get(bucket_for(inventory, key), key, version_id)
        expected = planted.get(document_id)
        rows.append(
            {
                "key": key,
                "sha256": sha256(content),
                "planted_sha256": None if expected is None else sha256(expected),
                "equals_planted": expected is not None and sha256(content) == sha256(expected),
            }
        )
    sealed_ids = {document_id_of(version, row["key"]) for row in rows}
    capture.check(
        "documents",
        sealed=len(rows),
        planted=len(planted),
        every_sealed_equals_planted=bool(rows) and all(row["equals_planted"] for row in rows),
        same_id_set=sealed_ids == set(planted),
        objects=rows,
    )


def check_verdicts(
    reader: Reader,
    capture: Capture,
    inventory: Json,
    version: WorldVersion,
    manifest_bytes: bytes,
    manifest: WorldManifest,
) -> list[str]:
    """Both approved verdicts bound to this manifest's bytes and the manifest's digests."""
    chain = cast(Json, inventory["golden_chain"])
    manifest_digest = sha256(manifest_bytes)
    role_digests = {a.role.value: a.digest for a in manifest.artifacts}
    rows: list[Json] = []
    for entry in cast(list[Json], chain["verdicts"]):
        key, version_id = str(entry["key"]), str(entry["version_id"])
        content = reader.get(bucket_for(inventory, key), key, version_id)
        data = as_object(json.loads(content), "the verdict")
        digests = {
            string_field(as_object(item, "an artifact digest"), "role"): string_field(
                as_object(item, "an artifact digest"), "digest"
            )
            for item in array_field(data, "artifacts")
        }
        rows.append(
            {
                "key": key,
                "sha256": sha256(content),
                "approved": string_field(data, "approval") == "approved",
                "names_golden_version": string_field(data, "world_version") == version,
                "manifest_digest_equals_fetched": string_field(data, "manifest_digest")
                == manifest_digest,
                "artifact_digests_equal_manifests": digests == role_digests,
                "validator_version": string_field(data, "validator_version"),
            }
        )
    fields = (
        "approved",
        "names_golden_version",
        "manifest_digest_equals_fetched",
        "artifact_digests_equal_manifests",
    )
    capture.check(
        "verdicts",
        count=len(rows),
        exactly_two=len(rows) == 2,
        keys_distinct=len({str(row["key"]) for row in rows}) == 2,
        fetched_manifest_sha256=manifest_digest,
        all_bound=bool(rows) and all(row[f] for row in rows for f in fields),
        objects=rows,
    )
    return [str(row["key"]) for row in rows]


def check_audit(
    reader: Reader,
    capture: Capture,
    inventory: Json,
    folder: Path,
    version: WorldVersion,
    manifest: WorldManifest,
    verdict_keys: list[str],
) -> None:
    """The sealed audit prefix: identity, bound digests, declarations, and the staging copies."""
    chain = cast(Json, inventory["golden_chain"])
    audit = cast(Json, chain["audit"])
    prefix, identity = str(audit["prefix"]), str(audit["identity"])
    truth_bucket = str(cast(Json, inventory["buckets"])["truth"])
    fetched: dict[str, bytes] = {}
    rows: list[Json] = []
    for entry in cast(list[Json], audit["objects"]):
        name = str(entry["name"])
        content = reader.get(truth_bucket, prefix + name, str(entry["version_id"]))
        fetched[name] = content
        staging = folder / str(entry["staging_copy"])
        staging_digest = sha256(staging.read_bytes()) if staging.exists() else None
        rows.append(
            {
                "key": prefix + name,
                "sha256": sha256(content),
                "recorded_sha256": entry["sha256"],
                "equals_recorded": sha256(content) == entry["sha256"],
                "staging_copy": staging.name,
                "staging_sha256": staging_digest,
                "staging_equals_sealed": staging_digest == sha256(content),
            }
        )
    index = as_object(json.loads(fetched["index.json"]), "the audit index")
    bound = {
        "rulings.md": string_field(index, "rulings_digest"),
        "summary.md": string_field(index, "summary_digest"),
        "checklist.md": string_field(index, "checklist_digest"),
    }
    capture.check(
        "audit",
        prefix=prefix,
        index_sha256=sha256(fetched["index.json"]),
        index_hashes_to_identity=sha256(fetched["index.json"]) == identity,
        prefix_ends_with_identity=prefix.rstrip("/").endswith(identity),
        object_names_exactly_the_four=frozenset(fetched) == AUDIT_OBJECTS,
        every_object_equals_recorded=all(row["equals_recorded"] for row in rows),
        index_binds_the_three_files=all(sha256(fetched[n]) == d for n, d in bound.items()),
        index_names_golden_version=string_field(index, "world_version") == version,
        index_names_manifests_generator_version=(
            string_field(index, "generator_version") == manifest.generator_version
        ),
        index_names_a_recorded_verdict=string_field(index, "verdict_key") in verdict_keys,
        index_verdict_key=string_field(index, "verdict_key"),
        staging_copies_equal_sealed=all(row["staging_equals_sealed"] for row in rows),
        objects=rows,
    )


# --- the run -----------------------------------------------------------------------------


def run(capture: Capture) -> None:
    inventory, folder = load_inventory()
    chain = cast(Json, inventory["golden_chain"])
    version = WorldVersion(str(chain["world_version"]))
    region = str(inventory.get("region", "eu-central-1"))
    import boto3

    if boto3.Session().get_credentials() is None:  # pyright: ignore[reportUnknownMemberType]
        raise ConfigurationError(
            "no AWS credentials in this process; run under the administrative profile"
        )
    reader = Reader(s3_client(region), capture)
    capture.data["world_version"] = version
    capture.data["inventory"] = (
        str(folder.name) + "/" + str(Path(os.environ[INVENTORY_VARIABLE]).name)
    )

    manifest, manifest_bytes = check_manifest(reader, capture, inventory, version)
    spec_bytes, _ = check_artifacts(reader, capture, inventory, version, manifest)
    check_documents(reader, capture, inventory, version, manifest, spec_bytes)
    verdict_keys = check_verdicts(reader, capture, inventory, version, manifest_bytes, manifest)
    check_audit(reader, capture, inventory, folder, version, manifest, verdict_keys)
    reader.record()


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.parse_args(argv)
    capture = Capture(CAPTURE_ROOT, "golden-chain")
    capture.require(
        ("manifest", "decodes_projected"),
        ("manifest", "names_golden_version"),
        ("manifest", "records_the_three_artifacts"),
        ("manifest", "records_documents"),
        ("artifacts", "each_equals_the_manifests_role_digest"),
        ("artifacts", "spec_cites_scenario_specs"),
        ("artifacts", "spec_cites_truth_manifest"),
        ("artifacts", "recomputed_equals_golden"),
        ("documents", "every_sealed_equals_planted"),
        ("documents", "same_id_set"),
        ("verdicts", "exactly_two"),
        ("verdicts", "keys_distinct"),
        ("verdicts", "all_bound"),
        ("audit", "index_hashes_to_identity"),
        ("audit", "prefix_ends_with_identity"),
        ("audit", "object_names_exactly_the_four"),
        ("audit", "every_object_equals_recorded"),
        ("audit", "index_binds_the_three_files"),
        ("audit", "index_names_golden_version"),
        ("audit", "index_names_manifests_generator_version"),
        ("audit", "index_names_a_recorded_verdict"),
        ("audit", "staging_copies_equal_sealed"),
        ("versions", "all_match"),
    )
    capture.data["started_at"] = datetime.now(UTC).isoformat()
    written = False
    try:
        run(capture)
        capture.data["execution"] = "completed"
    except ConfigurationError as error:  # nothing was probed: no capture, the message says what
        print(f"configuration: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # the failure is the finding: capture, then re-raise
        capture.data["execution"] = "crashed"
        capture.data["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        # Execution and acceptance are two facts (the step 0 probe's repair): a completed
        # run with one predicate false is a recorded failure, never a pass.
        failed = capture.judge()
        passed = capture.data["execution"] == "completed" and not failed
        capture.data["acceptance"] = "passed" if passed else "failed"
        capture.data["failed_predicates"] = failed
        print(
            f"acceptance: {capture.data['acceptance']}"
            + (f" ({', '.join(failed)})" if failed else "")
        )
        if capture.data["checks"]:
            print(f"capture: {capture.write()}")
            written = True
    return 0 if passed and written else 1


if __name__ == "__main__":
    sys.exit(main())
