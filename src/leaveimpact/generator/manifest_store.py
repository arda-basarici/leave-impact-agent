"""The manifest between runs: the composition root's checkpoint store, on disk or in the bucket.

Two stores, one codec. ``FileManifestStore`` rides the byte primitive in
``adapters.filestore`` for the whole-or-nothing replacement a local run depends on;
``ObjectManifestStore`` rides an object writer's ``overwrite`` at the world's checkpoint
key under the mutable ``preparing/`` prefix, the home the step 12 rulings gave the
checkpoint so the runner holds no local state a restart would need. Retargeting the
checkpoint was the store's port swap and not a change to the root, which sees ``load``
and ``save`` either way. ``load`` decodes without demanding a stage, because the root
resumes from a checkpoint as readily as from an accepted projection; the validator and
the application decode the same bytes themselves with ``projected`` required. The final
manifest under ``worlds/`` is the sealing step's, written once, not this store's.
"""

from __future__ import annotations

from pathlib import Path

from leaveimpact.adapters.filestore import read_if_present, replace_atomically
from leaveimpact.adapters.manifest import WorldManifest, decode_manifest, manifest_bytes
from leaveimpact.adapters.object_store.layout import checkpoint_key
from leaveimpact.adapters.object_store.write import ObjectWriter
from leaveimpact.core.ids import WorldVersion


class FileManifestStore:
    """The manifest at ``path``; the directory must exist."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> WorldManifest | None:
        content = read_if_present(self._path)
        return None if content is None else decode_manifest(content, stage=None)

    def save(self, manifest: WorldManifest) -> None:
        replace_atomically(self._path, manifest_bytes(manifest))


class ObjectManifestStore:
    """The manifest at the world's checkpoint key in ``store``, overwritten per save.

    Bound to one world version: a manifest of another version is refused on save, and
    one found under the key on load, so a miswired caller cannot poison the checkpoint
    and the root's own version check never meets a checkpoint this store let through.
    """

    def __init__(self, store: ObjectWriter, version: WorldVersion) -> None:
        self._store = store
        self._version = version
        self._key = checkpoint_key(version)

    @property
    def key(self) -> str:
        return self._key

    def load(self) -> WorldManifest | None:
        stored = self._store.get(self._key)
        if stored is None:
            return None
        manifest = decode_manifest(stored.content, stage=None)
        self._check(manifest, "holds")
        return manifest

    def save(self, manifest: WorldManifest) -> None:
        self._check(manifest, "was given")
        self._store.overwrite(self._key, manifest_bytes(manifest))

    def _check(self, manifest: WorldManifest, how: str) -> None:
        if manifest.world_version != self._version:
            raise ValueError(
                f"the checkpoint store of world {self._version} {how} a manifest of world "
                f"{manifest.world_version}"
            )
