"""The manifest on disk: the composition root's checkpoint store, decoded at any stage.

The store the root checkpoints into between and during runs, riding the byte primitive in
``adapters.filestore`` for the whole-or-nothing replacement a restart depends on; what is
typed here is only the manifest's codec on both sides. ``load`` decodes without demanding a
stage, because the root resumes from a checkpoint as readily as from an accepted projection;
the validator and the application decode the same file themselves with ``projected``
required. The world bucket copy is the sealing step's, not this store's.
"""

from __future__ import annotations

from pathlib import Path

from leaveimpact.adapters.filestore import read_if_present, replace_atomically
from leaveimpact.adapters.manifest import WorldManifest, decode_manifest, manifest_bytes


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
