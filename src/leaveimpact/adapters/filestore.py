"""One file on disk, replaced whole or not at all: the byte primitive under every local artifact.

The generator checkpoints the world manifest between and during runs; the validator's
verdict will be written the same way at the entry point. Both need the same guarantee and
neither may be the other's dependency: the validator cannot import the generator, and a
store at this level that knew the manifest's or the verdict's type would bind rank 2 to a
rank-3 record. So the primitive here knows bytes and a path, nothing else; each owner
encodes with its own codec and hands the bytes down (the file-store ruling at the
validator step).

Two guarantees, stated apart so that "atomic" is never read as "durable". *Atomic
visibility*, on every platform the project runs on: ``replace_atomically`` writes to a
sibling temporary file, flushes it to the device, and renames over the target, so a
reader sees the whole previous file or the whole new one and never a truncated middle;
the rename is atomic on one volume and the temporary sits beside the target so both are
on that volume. *Crash durability*, on the POSIX production platform only: after the
rename the parent directory is synced, because syncing the file persists its contents
and not necessarily its directory entry, and without that step a host failure after a
successful return could roll the file back to its previous content. Windows cannot open
a directory for syncing, so the development platform has atomic visibility and no
claimed durability barrier. A failing directory sync raises, since the caller must not
be told the barrier completed when it did not; the rename itself may already be visible.

What a lost barrier would cost is bounded by the receipt contract above this module: the
composition root may issue the next external write once a checkpoint returns, so a
rollback can land behind writes already made, stranding the vendor-minted locators the
readers cannot reconstruct — and the post-projection coverage check refuses loudly rather
than certify the world. Arbitrary host-crash recovery is outside the ruled restartability
guarantee; the barrier is cheap where it exists, so it is taken anyway.

One writer per target artifact is the invariant: the temporary's name is fixed, so a
temporary left by a dead process is overwritten by the next attempt rather than adopted,
which is the debris story wanted; two concurrent writers of one path would share that
staging file and are unsupported. ``read_if_present`` distinguishes an absent file from
an empty one, because a first run and a truncated file are different states for a caller
to act on.
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
    """``content`` becomes the file at ``path`` in one step; the directory must exist.

    Atomic visibility everywhere; on POSIX also durable across a host crash once this
    returns (the module docstring's two guarantees).
    """
    staged = path.with_name(path.name + ".tmp")
    with staged.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged, path)
    if SYNCS_DIRECTORIES:
        _sync_directory(path.parent)


SYNCS_DIRECTORIES = os.name != "nt"
"""Whether the platform can sync a directory entry: the durability barrier exists only there."""


def _sync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
