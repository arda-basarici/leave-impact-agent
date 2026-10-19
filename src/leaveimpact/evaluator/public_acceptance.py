"""The acceptance of a committed public results file against the artifact it claims to be
cut from: regenerate and compare, with the two worlds' sealed disclosure marks held to
what the file states and what the demo serves.

The committed file is the results page's source and the artifact is a local copy fetched
under the administrator profile, so the check runs on the workstation and never in CI
(ruling 7 of the demo milestone's entry): the artifact given is hashed before it is
parsed and refused by name when it is not the one the file records, so a regeneration
never silently reads another artifact; the projection is then regenerated from it under
the measurement world's sealed mark and compared byte for byte with the committed file,
a difference reported as the first path that differs and never as a value, since the
command's output may be pasted into a public record. The served world's mark is held
open, so an embargoed world cannot be allowlisted for the demo without a red run (the
entry's amendment to ruling 1). The two worlds are two identities: the artifact's is the
withheld measurement world, the served one is the demo's, and a change of the demo world
never regenerates the measurement's data.

Pure over bytes and marks; the script under ``scripts`` reads the two specs and the two
files and prints the verdict.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import cast

from leaveimpact.evaluator.public_results import project_public_results
from leaveimpact.results.codec import decode_public_results, public_results_bytes
from leaveimpact.world.disclosure import Disclosure

__all__ = ["Acceptance", "accept_public_results"]


@dataclass(frozen=True, slots=True)
class Acceptance:
    """The verdict: the digest of the artifact given, the digest the committed file records,
    and the findings, none when the file is accepted. A finding names a path or a mark and
    never a figure."""

    artifact_digest: str
    recorded_digest: str | None
    findings: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return not self.findings


def accept_public_results(
    committed: bytes,
    artifact: bytes,
    *,
    measurement_disclosure: Disclosure,
    served_disclosure: Disclosure,
) -> Acceptance:
    """Hold ``committed`` to ``artifact`` under the measurement world's sealed
    ``measurement_disclosure``, and the demo's served world to being open."""
    findings: list[str] = []
    digest = hashlib.sha256(artifact).hexdigest()
    if served_disclosure is not Disclosure.OPEN:
        findings.append(
            f"the served world is sealed {served_disclosure.value}; the demo serves open worlds"
        )
    try:
        recorded = decode_public_results(committed)
    except ValueError as error:
        findings.append(f"the committed file is not of the declared types: {error}")
        return Acceptance(digest, None, tuple(findings))
    if recorded.provenance.artifact_digest != digest:
        findings.append(
            "the artifact given is not the one the committed file records: "
            f"sha256 {digest} against recorded {recorded.provenance.artifact_digest}"
        )
        return Acceptance(digest, recorded.provenance.artifact_digest, tuple(findings))
    regenerated = public_results_bytes(
        project_public_results(artifact, world_disclosure=measurement_disclosure)
    )
    if regenerated != committed:
        findings.append(
            "the regenerated projection differs from the committed file at "
            + _first_difference(json.loads(committed), json.loads(regenerated))
        )
    return Acceptance(digest, recorded.provenance.artifact_digest, tuple(findings))


def _first_difference(committed: object, regenerated: object, at: str = "") -> str:
    """The path of the first leaf or shape that differs, in the committed file's order."""
    if isinstance(committed, dict) and isinstance(regenerated, dict):
        left = cast("dict[str, object]", committed)
        right = cast("dict[str, object]", regenerated)
        if list(left) != list(right):
            return f"{at or '(top)'} (the fields differ)"
        for key in left:
            if left[key] != right[key]:
                return _first_difference(left[key], right[key], f"{at}.{key}" if at else key)
    if isinstance(committed, list) and isinstance(regenerated, list):
        left_items = cast("list[object]", committed)
        right_items = cast("list[object]", regenerated)
        if len(left_items) != len(right_items):
            return f"{at} (the counts differ)"
        for index, (one, other) in enumerate(zip(left_items, right_items, strict=True)):
            if one != other:
                return _first_difference(one, other, f"{at}[{index}]")
    return at or "(top)"
