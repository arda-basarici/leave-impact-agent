"""The evaluator's own checkout, read through git: what an evaluation needs of the repository
and nothing more.

An evaluation binds itself to a commit three ways (the investigator milestone's sixth
build step, ruling 7). It runs from a clean tree, so the commit it records is the code
that ran. It reads the registration each export cites at the commit the export names, to
compare its bytes with the evaluator's own. And it records which paths of its declared
implementation changed between the commit its registration was last changed at and its
own, by the identity of their content at each.

Everything here is a read of the object database. A cited commit is resolved and one file
is read out of it as bytes; nothing from it is checked out, imported or executed. A commit
arrives as the forty-hex string an export's record holds, validated there, and is passed
to git as one argument, never through a shell.

``IMPLEMENTATION`` is the declared manifest: the packages the evaluator imports, with the
assets inside them, and the two files that fix its dependencies. A change outside it (the
harness, a workflow, a document) is not a change to how an evaluation is computed.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from leaveimpact.evaluator.artifact import ChangedPath, EvaluatorRevision

REGISTRATION_PATH = "preregistration/registration.json"
"""Where the registration lives in the repository, at every commit."""

IMPLEMENTATION: tuple[str, ...] = (
    "src/leaveimpact/evaluator",
    "src/leaveimpact/core",
    "src/leaveimpact/world",
    "src/leaveimpact/adapters",
    "pyproject.toml",
    "uv.lock",
)
"""The paths whose content is the evaluator's implementation."""


class RepositoryRefused(Exception):
    """The checkout cannot give an evaluation what it needs; the message names paths and
    commits only."""


@dataclass(frozen=True, slots=True)
class Repository:
    """A git checkout by its root directory."""

    root: Path

    def head(self) -> str:
        """The commit checked out."""
        return self._git("rev-parse", "--verify", "HEAD").decode().strip()

    def require_clean(self) -> None:
        """Refuse a tree with a change git tracks or a file it does not: the commit recorded
        would not be the code that ran."""
        status = self._git("status", "--porcelain").decode()
        if status.strip():
            changed = len(status.splitlines())
            raise RepositoryRefused(
                f"the evaluator runs from a clean tree, and {changed} path(s) differ from HEAD"
            )

    def last_changed(self, path: str) -> str:
        """The latest commit that changed ``path``."""
        commit = self._git("log", "-1", "--format=%H", "--", path).decode().strip()
        if not commit:
            raise RepositoryRefused(f"no commit of this history holds {path}")
        return commit

    def file_at(self, commit: str, path: str) -> bytes | None:
        """The bytes of ``path`` at ``commit`` as committed, or ``None`` when the commit is
        not in this history or holds no such file."""
        resolved = self._try("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
        if resolved is None:
            return None
        return self._try("cat-file", "blob", f"{commit}:{path}")

    def changed(self, before: str, after: str, paths: tuple[str, ...]) -> tuple[ChangedPath, ...]:
        """The files under ``paths`` whose content differs between two commits, in path
        order, each with the identity of its content at either."""
        earlier, later = self._blobs(before, paths), self._blobs(after, paths)
        return tuple(
            ChangedPath(path, earlier.get(path), later.get(path))
            for path in sorted(earlier.keys() | later.keys())
            if earlier.get(path) != later.get(path)
        )

    def _blobs(self, commit: str, paths: tuple[str, ...]) -> dict[str, str]:
        listing = self._git("ls-tree", "-r", "-z", commit, "--", *paths).decode()
        blobs: dict[str, str] = {}
        for entry in filter(None, listing.split("\0")):
            described, path = entry.split("\t", 1)
            blobs[path] = described.split()[2]
        return blobs

    def _git(self, *arguments: str) -> bytes:
        try:
            return self._run(*arguments)
        except subprocess.CalledProcessError as failed:
            raise RepositoryRefused(f"git {arguments[0]} failed in the checkout") from failed

    def _try(self, *arguments: str) -> bytes | None:
        try:
            return self._run(*arguments)
        except subprocess.CalledProcessError:
            return None

    def _run(self, *arguments: str) -> bytes:
        done = subprocess.run(
            ["git", "-C", str(self.root), *arguments], check=True, capture_output=True
        )
        return done.stdout


def evaluator_revision(repository: Repository) -> EvaluatorRevision:
    """The evaluator as it runs from ``repository``: its commit, the commit its registration
    was last changed at, and what of its implementation changed between them."""
    head = repository.head()
    registered = repository.last_changed(REGISTRATION_PATH)
    return EvaluatorRevision(head, registered, repository.changed(registered, head, IMPLEMENTATION))


__all__ = [
    "IMPLEMENTATION",
    "REGISTRATION_PATH",
    "Repository",
    "RepositoryRefused",
    "evaluator_revision",
]
