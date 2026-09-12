"""One file on disk, replaced whole or not at all: the byte primitive under every local artifact.

The generator checkpoints the world manifest between and during runs; the validator's
verdict will be written the same way at the entry point. Both need the same guarantee — a
reader sees the whole previous file or the whole new one and never a truncated middle —
and neither may be the other's dependency: the validator cannot import the generator, and
a store at this level that knew the manifest's or the verdict's type would bind rank 2 to
a rank-3 record. So the primitive here knows bytes and a path, nothing else; each owner
encodes with its own codec and hands the bytes down (the file-store ruling at the
validator step).

``replace_atomically`` writes to a sibling temporary file, flushes it to the device, and
renames over the target; the rename is atomic on one volume on both platforms the project
runs on, and the temporary sits beside the target so both are on that volume. A crash
before the rename leaves the temporary, which the next replace overwrites, and the target
untouched. ``read_if_present`` distinguishes an absent file from an empty one, because a
first run and a truncated file are different states for a caller to act on.
"""

from __future__ import annotations

import os
from pathlib import Path


def read_if_present(path: Path) -> bytes | None:
    """The bytes at ``path``, or ``None`` when no file is there."""
    if not path.exists():
        return None
    return path.read_bytes()


def replace_atomically(path: Path, content: bytes) -> None:
    """``content`` becomes the file at ``path`` in one step; the directory must exist."""
    staged = path.with_name(path.name + ".tmp")
    with staged.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged, path)
