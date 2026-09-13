"""The sealing sequence: a world's bytes into the two buckets in the order that keeps them safe.

One function, ``seal_world``, takes the pure assembly's output — the sealed bundle, whose
bytes, digests and version are fixed before anything is written — and drives it through
the five stages the step 12 rulings fixed, each stage's failure leaving the buckets in a
state the next attempt can resume from and the application can never serve:

1. *Truth first.* The world spec and the truth manifest go to the truth bucket, each by a
   conditional create. A restart re-seals the same bytes and takes the equal case; bytes
   that differ are ``ObjectConflict``, since once sealing begins no artifact byte is
   regenerated — a differing byte is the frozen-bytes rule broken, never something to
   overwrite. Truth-only orphans are harmless: with no manifest beside them there is no
   projected world, and the serving rule needs both a manifest and an approved verdict.
   The reverse order would leave live vendor state whose answer key is not yet sealed,
   which is the state the whole design exists to avoid.
2. *The vendor projection*, through the composition root with its checkpoint at the
   world bucket's mutable ``preparing/`` key; the root's postflight, then the documents
   into the final prefix, then the coverage proof, then the promotion.
3. *The scenario specs* under the final world prefix.
4. *Every sealed object read back*, its bytes compared with what was sealed and its
   version id taken from the read, so the manifest vouches for versions that exist and
   not for versions a put reported; the two truth objects included, since the generator
   role reads what it wrote.
5. *The world manifest last*, carrying the version id of every object above under its
   key — exactly the two truth keys, the scenario specs and one key per planted document,
   by construction, and asserted so before the put — so an object under ``worlds/`` with
   a manifest beside it is a completed projection by construction. The manifest is the
   projection's commit record; approval is the validator's separate artifact.

The same world re-sealed produces the same bytes at every key, the version ids read back
are the existing ones, and the final manifest's bytes are therefore equal too: a rerun of
a sealed world writes nothing and ends in the equal case everywhere, which is the proof
that the run before it completed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from leaveimpact.adapters.manifest import WorldManifest, manifest_bytes
from leaveimpact.adapters.object_store.layout import (
    document_key,
    scenario_specs_key,
    truth_manifest_key,
    world_manifest_key,
    world_spec_key,
)
from leaveimpact.adapters.object_store.read import StoredObject
from leaveimpact.adapters.object_store.write import ObjectWriter
from leaveimpact.generator.manifest_store import ObjectManifestStore
from leaveimpact.generator.projection import world_entities
from leaveimpact.generator.realize import Preparation, Prepared, realize
from leaveimpact.world.artifacts import Bundle, document_bytes
from leaveimpact.world.assembly import WorldSpec


class SealingRefused(Exception):
    """A sealed object read back with other bytes than were sealed, or a key is unaccounted for."""


@dataclass(frozen=True, slots=True)
class SealedWorld:
    """What sealing left: the final manifest and the version id of the object holding it."""

    manifest: WorldManifest
    manifest_version_id: str
    manifest_key: str


def seal_world(
    world: WorldSpec,
    sealed: Bundle,
    prepared: Prepared,
    preparation: Preparation,
    truth: ObjectWriter,
    world_store: ObjectWriter,
) -> SealedWorld:
    """Seal ``sealed`` into ``truth`` and ``world_store`` in the ruled order; the final manifest."""
    version = sealed.world_version
    truth_keys = {
        world_spec_key(version): sealed.world_spec.content,
        truth_manifest_key(version): sealed.truth_manifest.content,
    }
    for key, content in truth_keys.items():
        truth.put_if_absent(key, content)

    manifest = realize(
        world, sealed, prepared, preparation, ObjectManifestStore(world_store, version)
    )

    specs_key = scenario_specs_key(version)
    world_store.put_if_absent(specs_key, sealed.scenario_specs.content)

    documents = {
        document_key(version, document.id): document_bytes(document)
        for document in world_entities(world).documents
    }
    _check_document_receipts(manifest, set(documents))
    versions: dict[str, str] = {}
    for key, content in truth_keys.items():
        versions[key] = _read_back(truth, key, content).version_id
    for key, content in {specs_key: sealed.scenario_specs.content, **documents}.items():
        versions[key] = _read_back(world_store, key, content).version_id

    final = replace(manifest, object_versions=versions)
    receipt = world_store.put_if_absent(world_manifest_key(version), manifest_bytes(final))
    return SealedWorld(final, receipt.version_id, world_manifest_key(version))


def _read_back(store: ObjectWriter, key: str, expected: bytes) -> StoredObject:
    """The object at ``key``, refused unless its bytes are ``expected``."""
    stored = store.get(key)
    if stored is None:
        raise SealingRefused(f"{key!r} was sealed and is not there to read back")
    if stored.content != expected:
        raise SealingRefused(f"{key!r} read back with other bytes than were sealed")
    return stored


def _check_document_receipts(manifest: WorldManifest, expected_keys: set[str]) -> None:
    """The root receipted every planted document at its key and nothing else."""
    receipted = set(manifest.receipts.documents.documents.values())
    if receipted != expected_keys:
        raise SealingRefused(
            f"the document receipts name {sorted(receipted ^ expected_keys)} where the planted "
            "documents' keys were expected"
        )
