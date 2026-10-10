"""The prompt assets as package data, one directory per role, and their digests.

Three texts a role's model sees that are not data the turns render: the system text, the
opening of the first user turn and the finalization request. They ship inside the package
the way the generator's prompts do (``generator.prose.assets``), under ``prompts/<role>/``,
so the prompt a run was made under is the prompt in the tree at that commit and nothing an
environment could swap; each asset's SHA-256 is one of the frozen inputs' ``prompt_digests``
for the role, which the worker compares at claim and the export records. A fourth
model-visible text that is not data is a fourth asset here, never a literal in code (the
graph step, fork 11). The investigator's texts are the prompt check's; the reader's, the
two one-call baselines' (the baselines step, fork 3), start from them with the loop's
sentences removed and one sentence on what the message holds, and are measured by that
step's live probe.

The opening is a template whose only parameters are the leave id and the stamped ``now``,
the same instant every rendered result carries; the template's identifiers are checked at
load so a parameter the text forgot or invented is a load failure, not a request with a
hole. The texts start from the span probe's accepted second-pass configuration, revised for
a loop that reads through tools; what the revision changed is measured by the step's prompt
check, and nothing beyond it is added without that check.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from string import Template
from types import MappingProxyType

from leaveimpact.core.tools import Role

SYSTEM = "system"
OPENING = "opening"
FINALIZATION = "finalization"
ASSET_NAMES: tuple[str, ...] = (SYSTEM, OPENING, FINALIZATION)
"""The three, in the order the frozen inputs sort them."""

OPENING_PARAMETERS: frozenset[str] = frozenset({"leave_id", "now"})
"""The opening template's identifiers, exactly."""


@dataclass(frozen=True, slots=True)
class PromptAssets:
    """Every prompt asset by name, with its digest."""

    texts: Mapping[str, str]

    def text(self, name: str) -> str:
        try:
            return self.texts[name]
        except KeyError:
            raise ValueError(f"no prompt asset named {name!r}") from None

    def opening(self, *, leave_id: str, now: str) -> str:
        """The first user turn's opening text for the leave ``leave_id`` observed at ``now``,
        the stamp's canonical JSON."""
        return Template(self.text(OPENING)).substitute(leave_id=leave_id, now=now)

    def digests(self) -> tuple[tuple[str, str], ...]:
        """(name, SHA-256 of the UTF-8 bytes) per asset, in name order."""
        return tuple(
            (name, hashlib.sha256(text.encode("utf-8")).hexdigest())
            for name, text in sorted(self.texts.items())
        )

    def prompt_digests(self, role: str) -> tuple[tuple[str, str, str], ...]:
        """The frozen inputs' ``prompt_digests`` triples for ``role``: (role, name, digest)
        per asset, in name order."""
        return tuple((role, name, digest) for name, digest in self.digests())


@cache
def load_prompt_assets(role: Role = Role.INVESTIGATOR) -> PromptAssets:
    """The assets shipped with this package for ``role``, read once per process;
    ``ValueError`` when the opening's identifiers are not exactly the leave id and the
    stamp."""
    root = resources.files(__package__).joinpath("prompts", role.value)
    texts = {name: root.joinpath(f"{name}.md").read_text(encoding="utf-8") for name in ASSET_NAMES}
    identifiers = frozenset(Template(texts[OPENING]).get_identifiers())
    if identifiers != OPENING_PARAMETERS:
        raise ValueError(
            f"the opening template takes exactly {sorted(OPENING_PARAMETERS)}, "
            f"got {sorted(identifiers)}"
        )
    return PromptAssets(MappingProxyType(texts))


__all__ = [
    "ASSET_NAMES",
    "FINALIZATION",
    "OPENING",
    "OPENING_PARAMETERS",
    "SYSTEM",
    "PromptAssets",
    "load_prompt_assets",
]
