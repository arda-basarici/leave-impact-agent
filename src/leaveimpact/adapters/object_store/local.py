"""The reader over a directory: the development twin of the bucket, and the key grammar.

A world sealed on a laptop lands under one root, a key becoming the path below it, so the
sealing sequence and the validator's reads run end to end with no AWS in reach and no
credential in the environment. The twin keeps the contract that matters — absent versus
present, a listing by string prefix and not by directory — and drops what a directory
cannot give: there is no version history, so the version id is derived from the content
(its SHA-256), distinct for distinct bytes and equal for a rewrite of the same bytes.
The writer is a subclass in ``local_write``, gated like the S3 writer's module.

Keys are S3's, ``/``-separated, and this module fixes their grammar for the whole
project rather than trusting the host's path rules: a key is one or more segments of
letters, digits, ``.``, ``_`` and ``-``, none empty and none ``.`` or ``..``. That is
what the generator's keys are made of (hex versions, ids, file names), and it is what
keeps the twin inside its root on every platform — a backslash is a separator to
Windows, and a segment like ``C:`` re-roots a joined path there, so both are refused by
the grammar before a path is ever built, on POSIX too, so a key that would escape on
one development platform is refused on all of them.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from leaveimpact.adapters.filestore import read_if_present
from leaveimpact.adapters.object_store.read import StoredObject

_SEGMENT = re.compile(r"[A-Za-z0-9._-]+")


def key_path(root: Path, key: str) -> Path:
    """The path below ``root`` for ``key``; refuses a key outside the grammar.

    >>> key_path(Path("r"), "worlds/abc/world-manifest.json").as_posix()
    'r/worlds/abc/world-manifest.json'
    >>> for bad in ("", "worlds//x", "../x", "a/./b", "worlds\\\\..\\\\x", "C:/x", "a b"):
    ...     try:
    ...         key_path(Path("r"), bad)
    ...     except ValueError:
    ...         pass
    ...     else:
    ...         print("accepted", bad)
    """
    segments = key.split("/")
    if not all(_SEGMENT.fullmatch(s) and s not in (".", "..") for s in segments):
        raise ValueError(f"not an object key: {key!r}")
    return root.joinpath(*segments)


class LocalObjectReader:
    """``ObjectReader`` over the directory at ``root``: get and list, no write method on it."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    def get(self, key: str) -> StoredObject | None:
        content = read_if_present(key_path(self._root, key))
        if content is None:
            return None
        return StoredObject(key, content, content_version(content))

    def list_keys(self, prefix: str) -> tuple[str, ...]:
        if not self._root.exists():
            return ()
        found = (
            path.relative_to(self._root).as_posix()
            for path in self._root.rglob("*")
            if path.is_file() and not path.name.endswith(".tmp")
        )
        return tuple(sorted(key for key in found if key.startswith(prefix)))


def content_version(content: bytes) -> str:
    """The twin's version id: the content's SHA-256, since a directory keeps no history."""
    return hashlib.sha256(content).hexdigest()
