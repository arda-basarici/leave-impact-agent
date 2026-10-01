"""E-003: the sealed worlds' historical bytes decoded and re-encoded on today's codecs, exactly.

The M1 repository audit could construct old-style values from source but never held the
private byte streams, so it asked for this: every reader-supported shape fetched as the
exact version that was sealed, decoded through the reader a consumer uses, re-encoded
through the writer, and compared canonical bytes to sealed bytes. A codec that "reads old
files" by normalizing them would pass every fixture and fail here, and a field appended
since a world was sealed would show as a re-encode that adds bytes. Five shapes have both a
reader and a writer today and are covered: the world spec, the scenario specs, every
document a world manifest references, the manifest itself, and the truth manifest whole,
through the one decoder the file has (the evaluator milestone's third build step; before
it only the record's section had a reader). The truth manifest is where absent-versus-empty
exists in real bytes, in two places, and each is asserted against a declaration made before
the run, so a silent normalization of absent to empty fails by name and never against
whatever was found: the record's counters, which the inventory states per world (the
measurement world's died with its run, the golden world's were sealed), and a key's two
derived sets, which a world sealed before generator version 13 lacks and this module names.
The verdict has no reader yet; it is owed when its reader lands (the step 1 rulings of the
investigator milestone say where), and nothing here claims it.

The inventory is fixed, never discovered: a JSON file in the private stream naming each
world by its manifest's version id, each truth pair by its two version ids, and each world
ruled unread by today's codecs with the refusals it was ruled on, handed in through
``LEAVE_IMPACT_SEALED_INVENTORY``. The three registered worlds are a constant here, and the
inventory must name exactly them across the three kinds, so the scope cannot narrow without
a code change. An unread world is executable policy, not an ignored note: its world spec
and truth manifest must refuse at exactly the declared fields, and the shapes that still
read (its scenario specs, its manifest) round-trip like any other. The manifest is the
authority for the rest of a world's objects, since it records the store's version id of
everything sealed before it.
Every get names its version id and the returned one must match; nothing here lists a
bucket, reads a latest version or writes. Skipped without the inventory or without
credentials; with both present an access refusal or a decoder refusal is a failure, since
each is a finding and not an absence of setup. Assertions compare digests, never bytes or
decoded records, so a failure discloses a key and two SHA-256 prefixes and no content: the
objects are the benchmark's private truth and its unreleased golden scenarios.

Run from a workstation under the administrative profile, the one identity that reads both
buckets: ``just test-live`` with the inventory variable set. The result enters
``probes/FINDINGS.md``.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import boto3
import pytest

from leaveimpact.adapters.manifest import (
    ManifestStage,
    WorldManifest,
    decode_manifest,
    manifest_bytes,
)
from leaveimpact.adapters.object_store.layout import (
    document_id_of,
    scenario_specs_key,
    truth_manifest_key,
    world_manifest_key,
    world_spec_key,
)
from leaveimpact.adapters.object_store.s3 import s3_client
from leaveimpact.core.entities_json import encode_document
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import (
    array_field,
    as_object,
    canonical_bytes,
    field_of,
    object_field,
    string_field,
    string_item,
)
from leaveimpact.world import decode_scenario_specs, decode_world_spec
from leaveimpact.world.artifacts import (
    digest,
    encode_materialization,
    encode_scenario_specs,
    encode_truth_manifest,
    encode_world_spec,
)
from leaveimpact.world.decoders import decode_document
from leaveimpact.world.truth_decoder import decode_truth_manifest

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

pytestmark = pytest.mark.live

INVENTORY_VARIABLE = "LEAVE_IMPACT_SEALED_INVENTORY"

# The record's three real shapes, declared per truth manifest in the inventory so the test
# asserts an expectation and never merely reports what it found.
RECORD_NONE = "none"  # no model wrote anything: the section is null
RECORD_METRICS_ABSENT = "metrics-absent"  # sealed before the counters existed
RECORD_METRICS_PRESENT = "metrics-present"  # the counters sealed in the record
_RECORD_SHAPES = frozenset({RECORD_NONE, RECORD_METRICS_ABSENT, RECORD_METRICS_PRESENT})
_TRUTH_PREFIXES = ("world-spec/", "truth-manifest/")
# The three sealed worlds on record (the step 1 rulings): the inventory names exactly these.
REGISTERED_WORLDS = frozenset(
    {
        WorldVersion("7b806ed6f405e2d4be39cd02e6f6e99353917c9904cac709cc8b4fee1cd83ad4"),
        WorldVersion("785bc4cdd43d2718a61bf670f352f29ede43b4f7e37f3140fb7255c9cb65dce1"),
        WorldVersion("d674d5763715549f49e82c251977cfe5093b6bf09099c165b5d7c94d7de33046"),
    }
)
# The worlds sealed before a key carried its two derived sets, the expected conflicts and the
# expected unknowns (generator version 13, 2026-09-16; the measurement world was sealed on
# 2026-09-14). Declared before the run, from the dates: every key of a world named here must
# decode both sets as unavailable, every key of any other world both as present.
SEALED_BEFORE_THE_DERIVED_SETS = frozenset(
    {WorldVersion("785bc4cdd43d2718a61bf670f352f29ede43b4f7e37f3140fb7255c9cb65dce1")}
)
# The readers an unread world may declare a refusal for.
_REFUSAL_READERS = ("world_spec", "truth_manifest")


@dataclass(frozen=True, slots=True)
class Versioned:
    """One sealed object as the inventory names it: bucket, key and the version id to fetch."""

    bucket: str
    key: str
    version_id: str


@dataclass(frozen=True, slots=True)
class SealedWorldCase:
    """A completed world: its manifest, the authority for every other object's version id."""

    version: WorldVersion
    manifest: Versioned
    truth_bucket: str
    world_bucket: str
    record: str


@dataclass(frozen=True, slots=True)
class TruthPairCase:
    """A world sealed only as far as its truth pair, since its projection never completed."""

    version: WorldVersion
    world_spec: Versioned
    truth_manifest: Versioned
    record: str


@dataclass(frozen=True, slots=True)
class UnreadWorldCase:
    """A world today's codecs refuse by ruling: its manifest still vouches for its objects.

    ``refusals`` maps a reader (``world_spec``, ``truth_manifest``) to the fields the
    decoder must report missing, so the ruling is asserted, never merely tolerated.
    """

    version: WorldVersion
    manifest: Versioned
    truth_bucket: str
    world_bucket: str
    refusals: dict[str, tuple[str, ...]]


ManifestWorld = SealedWorldCase | UnreadWorldCase


@dataclass(frozen=True, slots=True)
class RecordCase:
    """One truth manifest with its declared record shape, by whichever path reaches it."""

    version: WorldVersion
    world: SealedWorldCase | None
    direct: Versioned | None
    shape: str

    @property
    def case_id(self) -> str:
        return self.version[:8]


@dataclass(frozen=True, slots=True)
class Inventory:
    worlds: tuple[SealedWorldCase, ...]
    truth_pairs: tuple[TruthPairCase, ...]
    unread: tuple[UnreadWorldCase, ...]

    @property
    def versions(self) -> list[WorldVersion]:
        """Every version the inventory names, one entry per case, duplicates kept."""
        return [
            *(w.version for w in self.worlds),
            *(p.version for p in self.truth_pairs),
            *(u.version for u in self.unread),
        ]

    @property
    def records(self) -> tuple[RecordCase, ...]:
        """Every truth manifest the inventory reaches, with its declared record shape."""
        return (
            *(RecordCase(w.version, w, None, w.record) for w in self.worlds),
            *(RecordCase(p.version, None, p.truth_manifest, p.record) for p in self.truth_pairs),
        )


def _version_id(data: object, what: str) -> str:
    """A recorded version id: a non-empty token, never a placeholder left in the inventory."""
    text = string_field(as_object(data, what), "version_id")
    if not text or any(character.isspace() for character in text):
        raise ValueError(f"{what}: the version id is a non-empty token, got {text!r}")
    return text


def _record_shape(data: object, what: str) -> str:
    shape = string_field(as_object(data, what), "record")
    if shape not in _RECORD_SHAPES:
        raise ValueError(f"{what}: record is one of {sorted(_RECORD_SHAPES)}, got {shape!r}")
    return shape


def load_inventory(content: str) -> Inventory:
    """The inventory from its JSON text, every case complete or refused by name.

    >>> text = json.dumps({
    ...     "buckets": {"truth": "t", "world": "w"},
    ...     "worlds": [{"version": "ab" * 32, "manifest": {"version_id": "v1"},
    ...                 "record": "metrics-present"}],
    ...     "truth_pairs": [{"version": "cd" * 32, "world_spec": {"version_id": "v2"},
    ...                      "truth_manifest": {"version_id": "v3"},
    ...                      "record": "metrics-absent"}],
    ... })
    >>> inventory = load_inventory(text)
    >>> inventory.worlds[0].manifest.key[:13], inventory.worlds[0].manifest.bucket, inventory.unread
    ('worlds/ababab', 'w', ())
    >>> inventory.truth_pairs[0].truth_manifest.key[:17], [r.case_id for r in inventory.records]
    ('truth-manifest/cd', ['abababab', 'cdcdcdcd'])
    >>> load_inventory(text.replace('"v2"', '"TODO after listing"'))
    Traceback (most recent call last):
    ...
    ValueError: truth pair cdcd...: the version id is a non-empty token, got 'TODO after listing'
    """
    data = as_object(json.loads(content), "the sealed inventory")
    buckets = object_field(data, "buckets")
    truth_bucket = string_field(buckets, "truth")
    world_bucket = string_field(buckets, "world")
    worlds: list[SealedWorldCase] = []
    for item in array_field(data, "worlds"):
        world = as_object(item, "a world")
        version = WorldVersion(string_field(world, "version"))
        what = f"world {version[:4]}..."
        manifest = Versioned(
            world_bucket,
            world_manifest_key(version),
            _version_id(field_of(world, "manifest"), what),
        )
        shape = _record_shape(world, what)
        worlds.append(SealedWorldCase(version, manifest, truth_bucket, world_bucket, shape))
    pairs: list[TruthPairCase] = []
    for item in array_field(data, "truth_pairs"):
        pair = as_object(item, "a truth pair")
        version = WorldVersion(string_field(pair, "version"))
        what = f"truth pair {version[:4]}..."
        spec = Versioned(
            truth_bucket, world_spec_key(version), _version_id(field_of(pair, "world_spec"), what)
        )
        truth = Versioned(
            truth_bucket,
            truth_manifest_key(version),
            _version_id(field_of(pair, "truth_manifest"), what),
        )
        pairs.append(TruthPairCase(version, spec, truth, _record_shape(pair, what)))
    unread: list[UnreadWorldCase] = []
    unread_items = (
        array_field(data, "unread_by_todays_codecs") if "unread_by_todays_codecs" in data else []
    )
    for item in unread_items:
        world = as_object(item, "an unread world")
        version = WorldVersion(string_field(world, "version"))
        what = f"unread world {version[:4]}..."
        manifest = Versioned(
            world_bucket,
            world_manifest_key(version),
            _version_id(field_of(world, "manifest"), what),
        )
        unread.append(
            UnreadWorldCase(version, manifest, truth_bucket, world_bucket, _refusals(world, what))
        )
    return Inventory(tuple(worlds), tuple(pairs), tuple(unread))


def _refusals(data: Mapping[str, object], what: str) -> dict[str, tuple[str, ...]]:
    """The declared refusals of an unread world: reader name to the fields reported missing."""
    declared = object_field(data, "refusals")
    if not declared or set(declared) - set(_REFUSAL_READERS):
        raise ValueError(
            f"{what}: refusals name readers among {_REFUSAL_READERS}, got {sorted(declared)}"
        )
    result: dict[str, tuple[str, ...]] = {}
    for reader in declared:
        names = tuple(string_item(item, reader) for item in array_field(declared, reader))
        if not names:
            raise ValueError(f"{what}: {reader} declares no missing field")
        result[reader] = names
    return result


def _inventory_from_environment() -> Inventory | None:
    path = os.environ.get(INVENTORY_VARIABLE)
    if path is None:
        return None
    return load_inventory(Path(path).read_text(encoding="utf-8"))


# Read once at import so the cases parametrize; an empty case list is pytest's own skip.
_INVENTORY = _inventory_from_environment()
_WORLDS = list(_INVENTORY.worlds) if _INVENTORY else []
_PAIRS = list(_INVENTORY.truth_pairs) if _INVENTORY else []
_UNREAD = list(_INVENTORY.unread) if _INVENTORY else []
_RECORDS = list(_INVENTORY.records) if _INVENTORY else []
_MANIFEST_WORLDS: list[ManifestWorld] = [*_WORLDS, *_UNREAD]


@pytest.fixture(scope="module")
def s3() -> S3Client:
    if boto3.Session().get_credentials() is None:  # pyright: ignore[reportUnknownMemberType]
        pytest.skip("no AWS credentials in this process; run under the administrative profile")
    return s3_client(os.environ.get("AWS_REGION", "eu-central-1"))


def fetch(s3: S3Client, target: Versioned) -> bytes:
    """The bytes of exactly ``target``'s version; a response for any other version is refused."""
    response = s3.get_object(Bucket=target.bucket, Key=target.key, VersionId=target.version_id)
    returned = cast("dict[str, object]", response).get("VersionId")
    assert returned == target.version_id, (
        f"{target.key}: requested version {target.version_id}, the store returned {returned}"
    )
    return response["Body"].read()


def _mismatch(key: str, sealed: bytes, re_encoded: bytes) -> str | None:
    """A one-line finding when the digests differ: the key and two prefixes, never content."""
    sealed_digest, re_encoded_digest = digest(sealed), digest(re_encoded)
    if sealed_digest == re_encoded_digest:
        return None
    return f"{key}: sealed {sealed_digest[:16]} re-encodes to {re_encoded_digest[:16]}"


def _assert_same_bytes(key: str, sealed: bytes, re_encoded: bytes) -> None:
    finding = _mismatch(key, sealed, re_encoded)
    assert finding is None, finding


def _case_id(case: ManifestWorld | TruthPairCase | RecordCase) -> str:
    return case.case_id if isinstance(case, RecordCase) else case.version[:8]


def _manifest_of(s3: S3Client, world: ManifestWorld) -> WorldManifest:
    return decode_manifest(fetch(s3, world.manifest), stage=ManifestStage.PROJECTED)


def _vouched(s3: S3Client, world: ManifestWorld, key: str) -> tuple[Versioned, bytes]:
    """An object the world's manifest vouches for, fetched at the version the manifest records."""
    manifest = _manifest_of(s3, world)
    assert key in manifest.object_versions, f"{key}: the manifest records no version id for it"
    bucket = world.truth_bucket if key.startswith(_TRUTH_PREFIXES) else world.world_bucket
    target = Versioned(bucket, key, manifest.object_versions[key])
    return target, fetch(s3, target)


@pytest.mark.parametrize("world", _WORLDS, ids=_case_id)
def test_the_world_spec_round_trips(s3: S3Client, world: SealedWorldCase) -> None:
    target, sealed = _vouched(s3, world, world_spec_key(world.version))
    re_encoded = canonical_bytes(encode_world_spec(decode_world_spec(sealed)))
    _assert_same_bytes(target.key, sealed, re_encoded)


@pytest.mark.parametrize("pair", _PAIRS, ids=_case_id)
def test_a_truth_pairs_world_spec_round_trips(s3: S3Client, pair: TruthPairCase) -> None:
    sealed = fetch(s3, pair.world_spec)
    re_encoded = canonical_bytes(encode_world_spec(decode_world_spec(sealed)))
    _assert_same_bytes(pair.world_spec.key, sealed, re_encoded)


@pytest.mark.parametrize("world", _MANIFEST_WORLDS, ids=_case_id)
def test_the_scenario_specs_round_trip(s3: S3Client, world: ManifestWorld) -> None:
    target, sealed = _vouched(s3, world, scenario_specs_key(world.version))
    re_encoded = canonical_bytes(encode_scenario_specs(decode_scenario_specs(sealed)))
    _assert_same_bytes(target.key, sealed, re_encoded)


@pytest.mark.parametrize("world", _MANIFEST_WORLDS, ids=_case_id)
def test_every_referenced_document_round_trips(s3: S3Client, world: ManifestWorld) -> None:
    """Every document the manifest records a version for, not a sample; the findings gathered."""
    manifest = _manifest_of(s3, world)
    keys = [key for key in manifest.object_versions if document_id_of(world.version, key)]
    if not keys:  # a structured-tier world plants none; nothing to round-trip is not a failure
        pytest.skip(f"{world.manifest.key}: the manifest records no document")
    findings: list[str] = []
    for key in keys:
        sealed = fetch(s3, Versioned(world.world_bucket, key, manifest.object_versions[key]))
        finding = _mismatch(key, sealed, canonical_bytes(encode_document(decode_document(sealed))))
        if finding is not None:
            findings.append(finding)
    assert not findings, f"{len(findings)} of {len(keys)} documents:\n" + "\n".join(findings)


@pytest.mark.parametrize("world", _MANIFEST_WORLDS, ids=_case_id)
def test_the_manifest_round_trips(s3: S3Client, world: ManifestWorld) -> None:
    sealed = fetch(s3, world.manifest)
    manifest = decode_manifest(sealed, stage=ManifestStage.PROJECTED)
    _assert_same_bytes(world.manifest.key, sealed, manifest_bytes(manifest))


def _truth_manifest_bytes(s3: S3Client, case: RecordCase) -> tuple[Versioned, bytes]:
    """The sealed truth manifest of ``case``: vouched for by its world's manifest, or named
    directly by the inventory when the world was sealed only as far as its truth pair."""
    if case.world is not None:
        return _vouched(s3, case.world, truth_manifest_key(case.world.version))
    assert case.direct is not None
    return case.direct, fetch(s3, case.direct)


@pytest.mark.parametrize("case", _RECORDS, ids=_case_id)
def test_the_truth_manifest_round_trips_with_its_derived_sets_as_declared(
    s3: S3Client, case: RecordCase
) -> None:
    """The whole file through its one decoder and back to the sealed bytes, and every key's
    two derived sets unavailable or present as this module declared before the run.

    The decoder itself refuses bytes that do not re-encode to themselves; the comparison is
    repeated here so a mismatch reads as a key and two digest prefixes like every other.
    """
    target, sealed = _truth_manifest_bytes(s3, case)
    manifest = decode_truth_manifest(sealed)
    _assert_same_bytes(target.key, sealed, canonical_bytes(encode_truth_manifest(manifest)))
    declared = "absent" if case.version in SEALED_BEFORE_THE_DERIVED_SETS else "present"
    for row in manifest.scenarios:
        for name, found in (
            ("expected_conflicts", row.key.expected_conflicts),
            ("expected_unknowns", row.key.expected_unknowns),
        ):
            decoded = "absent" if found is None else "present"
            assert decoded == declared, (
                f"{target.key}: {row.key.scenario_id} {name} declared {declared}, decoded {decoded}"
            )


@pytest.mark.parametrize("case", _RECORDS, ids=_case_id)
def test_the_materialization_record_round_trips_at_its_declared_shape(
    s3: S3Client, case: RecordCase
) -> None:
    """The record's section: canonical bytes of the sealed value against decode and re-encode.

    Absent and present are asserted against the inventory's declaration, so a decoder that
    invented empty counters for the measurement world's record, or dropped the golden's,
    fails by name.
    """
    target, sealed = _truth_manifest_bytes(s3, case)
    section = field_of(as_object(json.loads(sealed), "the truth manifest"), "materialization")
    record = decode_truth_manifest(sealed).materialization
    if case.shape == RECORD_NONE:
        assert section is None and record is None, f"{target.key}: a record where none was declared"
        return
    assert record is not None, f"{target.key}: no record where {case.shape} was declared"
    decoded = "present" if record.metrics is not None else "absent"
    declared = "present" if case.shape == RECORD_METRICS_PRESENT else "absent"
    assert decoded == declared, f"{target.key}: declared metrics {declared}, decoded {decoded}"
    sealed_section = canonical_bytes(dict(as_object(section, "the record")))
    re_encoded = canonical_bytes(encode_materialization(record))
    _assert_same_bytes(f"{target.key}#materialization", sealed_section, re_encoded)


@pytest.mark.parametrize("world", _UNREAD, ids=_case_id)
def test_an_unread_world_refuses_at_exactly_the_declared_fields(
    s3: S3Client, world: UnreadWorldCase
) -> None:
    """The ruling as a claim: each declared reader refuses, naming the declared fields missing.

    Both decoders check the top level first and report its field set at once
    (``missing [...]``); the message is the codecs' error contract, and the test reads it
    as such.
    """
    for reader, fields in world.refusals.items():
        if reader == "world_spec":
            _, sealed = _vouched(s3, world, world_spec_key(world.version))
            with pytest.raises(ValueError, match=re.escape(f"missing {sorted(fields)}")):
                decode_world_spec(sealed)
        else:
            _, sealed = _vouched(s3, world, truth_manifest_key(world.version))
            with pytest.raises(ValueError, match=re.escape(f"missing {sorted(fields)}")):
                decode_truth_manifest(sealed)


def test_the_inventory_names_exactly_the_registered_worlds() -> None:
    """The scope is the code's, not the file's: three worlds, each in exactly one kind."""
    if _INVENTORY is None:
        pytest.skip(f"{INVENTORY_VARIABLE} is not set; the private inventory lives in the stream")
    named = _INVENTORY.versions
    assert sorted(named) == sorted(REGISTERED_WORLDS), (
        f"the inventory names {[v[:8] for v in named]}, the registry "
        f"{sorted(v[:8] for v in REGISTERED_WORLDS)}"
    )
