"""The sealing sequence: a world's bytes into the two buckets in the order that keeps them safe.

One function, ``seal_world``, takes the pure assembly's output — the sealed bundle, whose
bytes, digests and version are fixed before anything is written, proven here to be the
bundle of the world it is handed by reassembling it — and drives it through the five
stages the step 12 rulings fixed, each stage's failure leaving the buckets in a state the
next attempt can resume from and the application can never serve:

1. *Truth first.* The world spec and the truth manifest go to the truth bucket, each by a
   conditional create, before the site preparation makes its first vendor call — the
   Frappe company and Jira project are vendor state too, so "before any vendor call"
   means before ``prepare``, not only before the root's interleaved calls (the part-3
   review's finding). A restart re-seals the same bytes and takes the equal case; bytes
   that differ are ``ObjectConflict``, since the frozen world is never regenerated once
   sealing begins and every world-content encoding — the three artifacts and every
   document — is a deterministic projection of it computed here before the first
   write; the final manifest alone is derived later, on purpose, from those fixed bytes
   and the version ids observed on read-back, since a commit record cannot exist before
   the receipts it records. Truth-only orphans are
   harmless: with no manifest beside them there is no projected world, and the serving
   rule needs both a manifest and an approved verdict. The reverse order would leave
   live vendor state whose answer key is not yet sealed, which is the state the whole
   design exists to avoid.
2. *The site preparation, then the vendor projection*, through the composition root
   with its checkpoint at the world bucket's mutable ``preparing/`` key; the root's
   postflight, then the documents into the final prefix, then the coverage proof, then
   the promotion. Sealing owns the call to ``prepare`` so the order is this function's
   and not the entry point's to get right.
3. *The scenario specs and the levels object* under the final world prefix; the levels
   object is the served side's statement of the pool's order and the levels (the M2
   step 9 design), what the corpus cache filters by, and a projection of the spec that
   never enters the version.
4. *Every sealed object read back*, its bytes compared with what was sealed and its
   version id taken from the read, so the manifest vouches for versions that exist and
   not for versions a put reported; the two truth objects included, since the generator
   role reads what it wrote.
5. *The world manifest last*, carrying the version id of every object above under its
   key — exactly the two truth keys, the scenario specs, the levels object and one key
   per planted document, the filler pool's included, by construction, and asserted so
   before the put — so an
   object under ``worlds/`` with
   a manifest beside it is a completed projection by construction. The manifest is the
   projection's commit record; approval is the validator's separate artifact.

The same world re-sealed produces the same bytes at every key, the version ids read back
are the existing ones, and the final manifest's bytes are therefore equal too: a rerun of
a sealed world writes nothing and ends in the equal case everywhere, which is the proof
that the run before it completed.

Since the prose step that proof holds under *resume*, because a fresh run of one seed is a
new materialization attempt and not entitled to reuse the previous realization (the step 14
rulings). The job has two paths and this function is the same in both::

    FRESH    assemble → verify the truth → materialize → compose → freeze bytes and version
             → print the version, flushed → seal the truth → prepare and project with the
             checkpoint
             → documents → scenario specs → read back → manifest
    RESUME   read the sealed world spec and truth manifest → gate the generator version
             → reassemble and match the semantic digest → decode the record, lift the bodies
             → the same compose and bundle → match the named version → continue here

A fresh run that lands on the same bytes hits the equal case; a fresh run while another
version's unfinished vendor state holds the site is refused by the site inspection, by
name, and the message says to resume or to clean.

``seal_unprojected`` is the development path of the generator step's ruling 7: the same
bundle proven the same way, the truth pair, every planted document, the scenario specs and
the levels object sealed by conditional create and read back, and no vendor touched, no
checkpoint and no manifest. The documents are sealed because the corpus cache is filled
from them and a development world exists to be searched; the manifest is not, because it
is the projection's commit record and the serving rule reads a manifest beside a world as a
completed projection, which an unprojected world must never pass for. The bytes at every
key are the ones a projected sealing of the same world writes, and the truth pair and the
specs hit the equal case under a later ``--resume``; the documents do not promote that way:
the projector finds each one sealed, a found entity reports no receipt and no checkpoint
holds one, so the coverage proof refuses the run (pinned in the sealing tests). Promoting
a development world is the read-side locator recovery the projection module names as its
revisit, and until then a development world stays a development world.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Protocol

from leaveimpact.adapters.manifest import WorldManifest, manifest_bytes
from leaveimpact.adapters.object_store.layout import (
    document_key,
    levels_key,
    scenario_specs_key,
    truth_manifest_key,
    world_manifest_key,
    world_spec_key,
)
from leaveimpact.adapters.object_store.read import StoredObject
from leaveimpact.adapters.object_store.write import ObjectWriter
from leaveimpact.core.ids import WorldVersion
from leaveimpact.generator.manifest_store import ObjectManifestStore
from leaveimpact.generator.projection import world_entities
from leaveimpact.generator.realize import Preparation, Prepared, realize
from leaveimpact.world.artifacts import Bundle, bundle, document_bytes, levels_bytes
from leaveimpact.world.assembly import WorldSpec
from leaveimpact.world.levels import corpus_levels_of


class SealingRefused(Exception):
    """The bundle is not the world's, an object read back changed, or a key unaccounted for."""


class SitePreparation(Preparation, Protocol):
    """The root's interleaved seam plus the one call before it: the sites prepared."""

    def prepare(self) -> Prepared:
        """The site preparation that needs no checkpoint; the first vendor calls of a run."""
        ...


@dataclass(frozen=True, slots=True)
class SealedWorld:
    """What sealing left: the final manifest and the version id of the object holding it."""

    manifest: WorldManifest
    manifest_version_id: str
    manifest_key: str


@dataclass(frozen=True, slots=True)
class UnprojectedWorld:
    """What an unprojected sealing left: the version and the key of every object it holds,
    the version id read back under each; no manifest exists for it."""

    world_version: WorldVersion
    object_versions: Mapping[str, str]


def seal_world(
    world: WorldSpec,
    sealed: Bundle,
    preparation: SitePreparation,
    truth: ObjectWriter,
    world_store: ObjectWriter,
) -> SealedWorld:
    """Seal ``sealed`` into ``truth`` and ``world_store`` in the ruled order; the final manifest.

    ``sealed`` must be the bundle of ``world``; the reassembly proves it before any write.
    """
    if bundle(world) != sealed:
        raise SealingRefused(
            f"the bundle sealed as {sealed.world_version} is not the bundle of the world given"
        )
    version = sealed.world_version
    truth_keys = _truth_objects(sealed)
    documents = _document_objects(world, version)
    for key, content in truth_keys.items():
        truth.put_if_absent(key, content)

    prepared = preparation.prepare()
    manifest = realize(
        world, sealed, prepared, preparation, ObjectManifestStore(world_store, version)
    )

    served = _served_objects(world, sealed)
    for key, content in served.items():
        world_store.put_if_absent(key, content)

    _check_document_receipts(manifest, set(documents))
    versions: dict[str, str] = {}
    for key, content in truth_keys.items():
        versions[key] = _read_back(truth, key, content).version_id
    for key, content in {**served, **documents}.items():
        versions[key] = _read_back(world_store, key, content).version_id

    final = replace(manifest, object_versions=versions)
    receipt = world_store.put_if_absent(world_manifest_key(version), manifest_bytes(final))
    return SealedWorld(final, receipt.version_id, world_manifest_key(version))


def seal_unprojected(
    world: WorldSpec, sealed: Bundle, truth: ObjectWriter, world_store: ObjectWriter
) -> UnprojectedWorld:
    """Seal ``sealed`` into ``truth`` and ``world_store`` and project nothing; the keys sealed.

    ``sealed`` must be the bundle of ``world``; the reassembly proves it before any write.
    The truth pair, then every planted document, then the scenario specs and the levels
    object, each by conditional create; then every key read back and its bytes compared.
    """
    if bundle(world) != sealed:
        raise SealingRefused(
            f"the bundle sealed as {sealed.world_version} is not the bundle of the world given"
        )
    version = sealed.world_version
    truth_keys = _truth_objects(sealed)
    # The documents, then the specs, then the levels object last: with no manifest on this
    # path, the levels object is the completion record the serving rule admits a
    # development world on, so a sealing that stops earlier is never served.
    world_keys = {**_document_objects(world, version), **_served_objects(world, sealed)}
    for key, content in truth_keys.items():
        truth.put_if_absent(key, content)
    for key, content in world_keys.items():
        world_store.put_if_absent(key, content)
    versions: dict[str, str] = {}
    for key, content in truth_keys.items():
        versions[key] = _read_back(truth, key, content).version_id
    for key, content in world_keys.items():
        versions[key] = _read_back(world_store, key, content).version_id
    return UnprojectedWorld(version, versions)


def _truth_objects(sealed: Bundle) -> dict[str, bytes]:
    """The two truth objects under their keys."""
    version = sealed.world_version
    return {
        world_spec_key(version): sealed.world_spec.content,
        truth_manifest_key(version): sealed.truth_manifest.content,
    }


def _served_objects(world: WorldSpec, sealed: Bundle) -> dict[str, bytes]:
    """The scenario specs and the levels object under their keys: what the application reads
    of a world beside its documents."""
    version = sealed.world_version
    return {
        scenario_specs_key(version): sealed.scenario_specs.content,
        levels_key(version): levels_bytes(corpus_levels_of(world.filler, world.levels)),
    }


def _document_objects(world: WorldSpec, version: WorldVersion) -> dict[str, bytes]:
    """Every planted document's canonical bytes under its key."""
    return {
        document_key(version, document.id): document_bytes(document)
        for document in world_entities(world).documents
    }


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
