"""The manifest on disk: one file, replaced atomically, decoded at any stage.

The store the composition root checkpoints into between and during runs. ``save`` writes
the canonical bytes to a sibling temporary file, flushes them to the device, and renames
over the manifest, so a reader — a restart, a validator — sees the whole previous manifest
or the whole new one and never a truncated middle; the rename is atomic on one volume on
both platforms the project runs on. ``load`` decodes without demanding a stage, because the
root resumes from a checkpoint as readily as from an accepted projection; the validator and
the application decode the same file themselves with ``projected`` required. The world
bucket copy is the sealing step's, not this store's.
"""

from __future__ import annotations

import os
from pathlib import Path

from leaveimpact.adapters.manifest import WorldManifest, decode_manifest, manifest_bytes


class FileManifestStore:
    """The manifest at ``path``; the directory must exist."""

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> WorldManifest | None:
        if not self._path.exists():
            return None
        return decode_manifest(self._path.read_bytes(), stage=None)

    def save(self, manifest: WorldManifest) -> None:
        staged = self._path.with_name(self._path.name + ".tmp")
        with staged.open("wb") as handle:
            handle.write(manifest_bytes(manifest))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staged, self._path)
