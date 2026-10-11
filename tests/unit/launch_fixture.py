"""What the launcher's tests compose over: the prompt check's development-world helper,
loaded by path since ``probes/prompt-check`` is no package, and a throwaway golden world
sealed unprojected into a temporary local root, read back as the launcher reads the
instance's store. The helper is the production path's mirror the forecast names (the first
live run's step, fork 1): the launcher's frozen inputs are held equal to what it builds for
the same scenarios, byte for byte under the canonical codec. The first development world's
own store under ``data/`` is git-ignored and exists on one laptop, so no test reads it; the
order check on an exported tree found the first form of these tests doing exactly that."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest

from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.core.ids import WorldVersion
from leaveimpact.evaluator.sealed_world import SealedWorld, load_sealed_world
from leaveimpact.generator.sealing import seal_unprojected
from leaveimpact.world import bundle
from tests.unit.throwaway_world import composed_world_with_filler

REPOSITORY = Path(__file__).resolve().parents[2]
PROBE_HELPER = REPOSITORY / "probes" / "prompt-check" / "development_world.py"
DEVELOPMENT_SEED = 101
"""The first development world's seed: the throwaway world the tests seal is the golden
plan under it, with stand-in filler, which is the shape and not the bytes of that world."""


@cache
def probe_helper() -> ModuleType:
    """``probes/prompt-check/development_world.py`` as a module."""
    spec = importlib.util.spec_from_file_location("development_world", PROBE_HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before it runs: its dataclasses resolve their postponed annotations
    # through ``sys.modules[__module__]``.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def registration_commit_or_skip(probe: ModuleType) -> str:
    """The commit the registration file was last changed at, which the helper reads from
    git; skipped where the tree is no repository (an exported copy under the order check)."""
    try:
        return str(probe.registration_commit())
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("the registration's commit is read from git, and this tree is no repository")


@dataclass(frozen=True)
class SealedDevelopment:
    """A throwaway development world under a local root: the root the launcher is pointed
    at, the version, and the world as the evaluator loads it."""

    root: Path
    version: WorldVersion
    world: SealedWorld


def seal_development(root: Path) -> SealedDevelopment:
    """The golden plan under the development seed with three stand-in filler documents,
    sealed unprojected into ``root`` (its truth and world halves) and loaded back."""
    spec = composed_world_with_filler(3, "golden", DEVELOPMENT_SEED)
    sealed = bundle(spec)
    seal_unprojected(
        spec, sealed, LocalObjectWriter(root / "truth"), LocalObjectWriter(root / "world")
    )
    version = WorldVersion(sealed.world_version)
    world = load_sealed_world(
        version, LocalObjectReader(root / "truth"), LocalObjectReader(root / "world")
    )
    return SealedDevelopment(root, version, world)


__all__ = [
    "DEVELOPMENT_SEED",
    "PROBE_HELPER",
    "REPOSITORY",
    "SealedDevelopment",
    "probe_helper",
    "registration_commit_or_skip",
    "seal_development",
]
