"""The prompt assets as package data, and their digests.

The writer's system text, the checker's system text and one register fragment per register
ship inside the package the way the corpus adapter ships its DDL, so the prompt a world was
written under is the prompt in the tree at that version and nothing an environment could
swap. Each asset's SHA-256 is recorded in the materialization record and pinned in
``world.version`` beside the vocabulary digest: an identity-bearing prompt change updates
the reference provenance deliberately, and a generator bump for another reason leaves the
pins alone (the step 14 rulings in DESIGN, "Materialization"). Read once per process; the
assets are small and immutable.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from types import MappingProxyType

from leaveimpact.world.briefs import Register

WRITER_SYSTEM = "writer_system"
CHECKER_SYSTEM = "checker_system"


@dataclass(frozen=True, slots=True)
class PromptAssets:
    """Every prompt asset by name, with its digest: the two system texts and the registers."""

    texts: Mapping[str, str]

    def text(self, name: str) -> str:
        try:
            return self.texts[name]
        except KeyError:
            raise ValueError(f"no prompt asset named {name!r}") from None

    def register(self, register: Register) -> str:
        return self.text(register_asset(register))

    def digests(self) -> tuple[tuple[str, str], ...]:
        """(name, SHA-256) per asset in name order, the record's ``prompt_digests``."""
        return tuple(
            (name, hashlib.sha256(text.encode("utf-8")).hexdigest())
            for name, text in sorted(self.texts.items())
        )


def register_asset(register: Register) -> str:
    return f"register_{register.value}"


def load_prompt_assets() -> PromptAssets:
    """The assets shipped with this package, read from the tree."""
    root = resources.files(__package__).joinpath("prompts")
    texts: dict[str, str] = {
        WRITER_SYSTEM: root.joinpath("writer_system.md").read_text(encoding="utf-8"),
        CHECKER_SYSTEM: root.joinpath("checker_system.md").read_text(encoding="utf-8"),
    }
    for register in Register:
        fragment = root.joinpath("registers", f"{register.value}.md")
        texts[register_asset(register)] = fragment.read_text(encoding="utf-8")
    return PromptAssets(MappingProxyType(texts))


__all__ = [
    "CHECKER_SYSTEM",
    "WRITER_SYSTEM",
    "PromptAssets",
    "load_prompt_assets",
    "register_asset",
]
