"""The verdict's serving fields: what the serving rule reads of a validator verdict, at rank 2.

A verdict is the validator's artifact (``validator.verdict`` encodes it whole, every
finding listed), and the rule that decides whether a world is served reads four things of
it and nothing of the findings: that it approves, which world it names, which manifest it
judged (the SHA-256 of the manifest bytes it read) and which validator logic judged. The
corpus cache is a rank-3 shell beside the validator and the shells never import one
another, so the serving fields and their decoder live here, below both, and the validator
imports the format number and the approval word from here so the two cannot drift. The
summary reads the named fields and ignores the rest on purpose: a verdict of a later
validator version with more findings still says whether it approved, and the full decoder
stays the validator's to grow.

A verdict at another format is refused by name, since its fields are not known to mean
this; a field missing or of another shape is a ``ValueError`` naming it, the reader's to
turn into its own refusal with the key.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.jsonshape import as_object, integer_field, string_field
from leaveimpact.world.artifacts import SHA256_HEX

VERDICT_FORMAT = 1


class Approval(StrEnum):
    """The verdict's one word: approved when every check passed, refused otherwise."""

    APPROVED = "approved"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class VerdictSummary:
    """The serving fields of one verdict: its word, the world and the manifest it judged, the
    validator version that judged."""

    world_version: WorldVersion
    validator_version: str
    manifest_digest: str
    approval: Approval

    def __post_init__(self) -> None:
        if not SHA256_HEX.fullmatch(self.manifest_digest):
            raise ValueError(f"the manifest digest is a SHA-256 hex, got {self.manifest_digest!r}")

    def approves(self, version: WorldVersion, manifest_digest: str) -> bool:
        """Whether this verdict approves exactly ``version`` as projected under the manifest
        whose bytes hash to ``manifest_digest``: the serving rule's clause."""
        return (
            self.approval is Approval.APPROVED
            and self.world_version == version
            and self.manifest_digest == manifest_digest
        )


def decode_verdict_summary(content: bytes | str) -> VerdictSummary:
    """The serving fields ``content`` carries; another format is refused by name."""
    data = as_object(json.loads(content), "the verdict")
    fmt = integer_field(data, "format")
    if fmt != VERDICT_FORMAT:
        raise ValueError(f"the verdict is format {VERDICT_FORMAT}, got {fmt}")
    word = string_field(data, "approval")
    try:
        approval = Approval(word)
    except ValueError:
        raise ValueError(
            f"approval is one of {[item.value for item in Approval]}, got {word!r}"
        ) from None
    return VerdictSummary(
        world_version=WorldVersion(string_field(data, "world_version")),
        validator_version=string_field(data, "validator_version"),
        manifest_digest=string_field(data, "manifest_digest"),
        approval=approval,
    )
