"""The serving rule, decided where a sealed world is read: which versions under ``worlds/``
the application may serve, and for each one that may not, why.

DESIGN states the rule and names this as its first consumer: a world is served only on a
verdict that judged its current manifest, never "whatever verdict file exists". Here it is
three clauses over what the world store holds. The world's manifest is present under its
final key and decodes at ``projected`` (a checkpoint lives under ``preparing/`` and is
never served). A verdict under the version's ``verdicts/`` prefix approves, names this
version, and names the SHA-256 of the manifest bytes just read, so a re-projection of the
same world onto other sites, which leaves the version and the artifact digests unchanged
and changes every receipt, is not served on the earlier verdict. The version is what the
manifest says it is. Every clause is read fresh on each admission, and nothing here is a
pointer an operator could move: a newest-approved choice, if one is ever needed, is a
listing and a comparison, as DESIGN asks.

A development world has no manifest by the generator step's ruling 7, since the manifest
is the projection's commit record and an unprojected world must never pass for a
completed projection. Under a bucket such a world is not served, and the reason says so.
On the local twin, which exists for the laptop and is never the instance, the caller says
it is reading a development root and a manifest-less world is admitted as one, the
admission marking it so the cache row carries the fact (fork 3 of the step 9 design). Its
completion record is the levels object, which an unprojected sealing writes last: a
development root whose version holds documents and no levels object is a sealing that
stopped, and it is declined rather than loaded as a partial world marked ready (the
external review's second finding).

Two kinds of outcome are kept apart. ``NotServed`` is the rule's own answer, a world the
listing holds and the rule declines, reported by name and never loaded. ``ServingRefused``
is a fault in what the store holds: a key under ``worlds/`` that is not a version's, a
manifest or a verdict that does not decode, a manifest naming another version than its
key. The layout puts nothing but versions under the prefix and nothing but these objects
under a version, so such a key is a store someone wrote to outside the generator and the
validator, and the loader stops on it rather than serving around it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from leaveimpact.adapters.manifest import ManifestStage, WorldManifest, decode_manifest
from leaveimpact.adapters.object_store.layout import (
    levels_key,
    verdicts_prefix,
    world_manifest_key,
    worlds_prefix,
)
from leaveimpact.adapters.object_store.read import ObjectReader
from leaveimpact.adapters.object_store.verdicts import decode_verdict_summary
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.run_record import WorldProjection
from leaveimpact.world.artifacts import SHA256_HEX


@dataclass(frozen=True, slots=True)
class ServedWorld:
    """A version the rule admits: its manifest and the digest a verdict approved, or neither
    for a development world, and the key of the verdict that approved it."""

    version: WorldVersion
    projection: WorldProjection
    manifest: WorldManifest | None
    manifest_digest: str | None
    verdict_key: str | None


@dataclass(frozen=True, slots=True)
class NotServed:
    """A version the listing holds and the rule declines, with the clause that declined it."""

    version: WorldVersion
    reason: str


class ServingRefused(Exception):
    """The store holds something the layout says cannot be there; the key is in the message."""


def discover_versions(store: ObjectReader) -> tuple[WorldVersion, ...]:
    """Every version with at least one object under ``worlds/``, sorted; a key under the prefix
    whose first segment is not a version is ``ServingRefused``."""
    found: set[WorldVersion] = set()
    for key in store.list_keys(worlds_prefix()):
        segment = key[len(worlds_prefix()) :].split("/", 1)[0]
        if not SHA256_HEX.fullmatch(segment):
            raise ServingRefused(f"{key!r} is under worlds/ and names no world version")
        found.add(WorldVersion(segment))
    return tuple(sorted(found))


def admit(
    store: ObjectReader, version: WorldVersion, *, development: bool
) -> ServedWorld | NotServed:
    """The serving rule over ``version`` in ``store``; ``development`` says the store is a local
    development root, where a manifest-less world is a development world."""
    manifest_key = world_manifest_key(version)
    stored = store.get(manifest_key)
    if stored is None:
        if not development:
            return NotServed(version, "no manifest under its final key: not a completed projection")
        if store.get(levels_key(version)) is None:
            return NotServed(
                version,
                "no levels object: an unprojected sealing writes it last, so the sealing did "
                "not complete, or a generator before the object existed sealed this world",
            )
        return ServedWorld(version, WorldProjection.UNPROJECTED, None, None, None)
    try:
        manifest = decode_manifest(stored.content, stage=ManifestStage.PROJECTED)
    except ValueError as error:
        raise ServingRefused(
            f"{manifest_key!r} does not decode as a projected manifest: {error}"
        ) from error
    if manifest.world_version != version:
        raise ServingRefused(
            f"{manifest_key!r} names world {manifest.world_version}, the key says {version}"
        )
    digest = hashlib.sha256(stored.content).hexdigest()
    verdict_keys = store.list_keys(verdicts_prefix(version))
    for key in verdict_keys:
        verdict = store.get(key)
        if verdict is None:
            raise ServingRefused(f"{key!r} was listed and is not there to read")
        try:
            summary = decode_verdict_summary(verdict.content)
        except ValueError as error:
            raise ServingRefused(f"{key!r} does not decode as a verdict: {error}") from error
        if summary.approves(version, digest):
            return ServedWorld(version, WorldProjection.PROJECTED, manifest, digest, key)
    return NotServed(
        version,
        f"no approved verdict judges manifest {digest[:12]}…: {len(verdict_keys)} verdict(s) read",
    )
