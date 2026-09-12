"""The validator's verdict: its own artifact, approved only when every check passed.

The verdict is a record of its own and never a flag on the manifest (the verdict ruling
at the validator step): ``projected`` on the manifest means the projection lifecycle
completed, approval is this artifact's word, and serving requires both — the manifest at
``projected``, the verdict approved, and the verdict judging exactly this manifest. That
last clause is why the verdict records the SHA-256 of the manifest bytes it read, beside
the world version and the artifact digests it carries for a human: the version and the
digests identify the world, and a re-projection of the same world onto other sites would
leave them unchanged while changing every receipt, so only the manifest's own digest ties
a verdict to a projection. ``validator_version`` names the logic that judged, since the
same world and manifest can be approved by one version of these checks and refused by the
next; no wall-clock timestamp, as the judged digests and the version are the provenance
that means something.

Every finding is listed in full — missing and foreign identities by id, unequal records
by id with the differing fields named, view disagreements by scenario with both
differences as facts — so one run answers why a world was refused. A check that could not
run says so with its reason; ``not_run`` never counts as passed, so approval is exactly
"every check passed". The encoding is canonical through ``core``'s one byte rule; the
decoder arrives with its first consumer, the serving check.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from leaveimpact.adapters.manifest import ArtifactDigest
from leaveimpact.core.derivation import Derived
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.facts import Fact
from leaveimpact.core.ids import ScenarioId, WorldVersion
from leaveimpact.core.jsonshape import JsonObject, canonical_bytes
from leaveimpact.validator.checks import (
    CheckStatus,
    IdentityExactness,
    RecordMismatch,
    ViewDisagreement,
)
from leaveimpact.world.artifacts import SHA256_HEX, encode_fact, encode_gap

VALIDATOR_VERSION = "1"
"""Bumped with any change that can alter what these checks approve or refuse."""

VERDICT_FORMAT = 1


class Approval(StrEnum):
    """The verdict's one word: approved when every check passed, refused otherwise."""

    APPROVED = "approved"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class ExactnessResult:
    """One kind's identity exactness, with the scope the enumeration was read under."""

    check: IdentityExactness
    scope: str

    @property
    def status(self) -> CheckStatus:
        return self.check.status


@dataclass(frozen=True, slots=True)
class FidelityResult:
    """One kind's record fidelity, or the reason it could not be established."""

    kind: EntityKind
    status: CheckStatus
    mismatches: tuple[RecordMismatch, ...] = ()
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ViewResult:
    """One scenario's view agreement, or the reason it could not be established."""

    scenario_id: ScenarioId
    run_day: date
    status: CheckStatus
    disagreement: ViewDisagreement | None = None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationVerdict:
    """What the validator concluded about one projection of one world, and on what evidence."""

    world_version: WorldVersion
    validator_version: str
    manifest_digest: str
    artifacts: tuple[ArtifactDigest, ...]
    exactness: tuple[ExactnessResult, ...]
    fidelity: tuple[FidelityResult, ...]
    views: tuple[ViewResult, ...]

    def __post_init__(self) -> None:
        if not SHA256_HEX.fullmatch(self.manifest_digest):
            raise ValueError(f"the manifest digest is a SHA-256 hex, got {self.manifest_digest!r}")

    @property
    def approval(self) -> Approval:
        """Approved exactly when every check passed; a check not run refuses."""
        statuses = [
            *(result.status for result in self.exactness),
            *(result.status for result in self.fidelity),
            *(result.status for result in self.views),
        ]
        passed = all(status is CheckStatus.PASSED for status in statuses)
        return Approval.APPROVED if passed and statuses else Approval.REFUSED


def encode_verdict(verdict: ValidationVerdict) -> JsonObject:
    """The verdict as a JSON object, every finding in full."""
    return {
        "format": VERDICT_FORMAT,
        "approval": verdict.approval.value,
        "world_version": verdict.world_version,
        "validator_version": verdict.validator_version,
        "manifest_digest": verdict.manifest_digest,
        "artifacts": [
            {"role": item.role.value, "file_name": item.file_name, "digest": item.digest}
            for item in verdict.artifacts
        ],
        "exactness": [_exactness(result) for result in verdict.exactness],
        "fidelity": [_fidelity(result) for result in verdict.fidelity],
        "views": [_view(result) for result in verdict.views],
    }


def verdict_bytes(verdict: ValidationVerdict) -> bytes:
    """The canonical bytes of the verdict, what the entry point writes beside the manifest."""
    return canonical_bytes(encode_verdict(verdict))


def _exactness(result: ExactnessResult) -> JsonObject:
    return {
        "kind": result.check.kind.value,
        "scope": result.scope,
        "status": result.status.value,
        "missing": list(result.check.missing),
        "foreign": list(result.check.foreign),
    }


def _fidelity(result: FidelityResult) -> JsonObject:
    return {
        "kind": result.kind.value,
        "status": result.status.value,
        "mismatches": [
            {
                "kind": mismatch.ref.kind.value,
                "id": mismatch.ref.id,
                "differing_fields": list(mismatch.differing_fields),
            }
            for mismatch in result.mismatches
        ],
        "reason": result.reason,
    }


def _view(result: ViewResult) -> JsonObject:
    disagreement = result.disagreement
    return {
        "scenario_id": result.scenario_id,
        "run_day": result.run_day.isoformat(),
        "status": result.status.value,
        "missing": []
        if disagreement is None
        else [_derived(item) for item in disagreement.missing],
        "surplus": []
        if disagreement is None
        else [_derived(item) for item in disagreement.surplus],
        "reason": result.reason,
    }


def _derived(item: Derived) -> JsonObject:
    if isinstance(item, Fact):
        return {"fact": encode_fact(item)}
    return {"gap": encode_gap(item)}
