"""The serving rule over a world store, and the verdict summary it reads.

A world is served only on a verdict that judged its current manifest (DESIGN; the M2
step 9 design, forks 2 and 3): the manifest present and projected, a verdict approving
exactly this version under exactly these manifest bytes. These tests hold each clause on
an in-memory store: the listing yields versions and refuses a foreign key; a manifest-less
world is declined under a bucket and admitted as a development world on a development
root; a verdict over another manifest digest, a refused verdict and a verdict at another
format each do what the rule says; the summary reads what the validator wrote.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from leaveimpact.adapters.manifest import ManifestStage, manifest_bytes
from leaveimpact.adapters.object_store import layout
from leaveimpact.adapters.object_store.serving import (
    NotServed,
    ServedWorld,
    ServingRefused,
    admit,
    discover_versions,
)
from leaveimpact.adapters.object_store.verdicts import (
    VALIDATOR_VERSION,
    Approval,
    VerdictSummary,
    decode_verdict_summary,
)
from leaveimpact.core.enums import EntityKind
from leaveimpact.core.ids import WorldVersion
from leaveimpact.core.run_record import WorldProjection
from leaveimpact.validator.checks import CheckStatus, LevelsResult
from leaveimpact.validator.verdict import FidelityResult, ValidationVerdict, verdict_bytes
from leaveimpact.world.artifacts import levels_bytes
from leaveimpact.world.levels import BASE_CORPUS_LEVELS
from tests.unit.in_memory_object_store import InMemoryObjectStore
from tests.unit.test_manifest import VERSION, manifest

OTHER = WorldVersion("b" * 64)


def verdict(
    *, judged: bytes, version: WorldVersion = VERSION, passed: bool = True
) -> ValidationVerdict:
    """A verdict over the manifest bytes ``judged``: approved when ``passed``."""
    status = CheckStatus.PASSED if passed else CheckStatus.FAILED
    return ValidationVerdict(
        world_version=version,
        validator_version=VALIDATOR_VERSION,
        manifest_digest=hashlib.sha256(judged).hexdigest(),
        artifacts=manifest().artifacts,
        exactness=(),
        fidelity=(FidelityResult(EntityKind.DOCUMENT, status),),
        views=(),
        levels=LevelsResult(CheckStatus.PASSED, "object"),
    )


def projected_store(*, approved: bool = True) -> tuple[InMemoryObjectStore, bytes]:
    store = InMemoryObjectStore()
    content = manifest_bytes(manifest())
    store.put_if_absent(layout.world_manifest_key(VERSION), content)
    store.put_if_absent(layout.scenario_specs_key(VERSION), b"{}")
    store.put_if_absent(
        layout.verdict_key(VERSION, "100", "1"),
        verdict_bytes(verdict(judged=content, passed=approved)),
    )
    return store, content


def test_the_listing_yields_every_version_once_and_refuses_a_key_that_names_none() -> None:
    store = InMemoryObjectStore()
    store.put_if_absent(layout.scenario_specs_key(OTHER), b"{}")
    store.put_if_absent(layout.scenario_specs_key(VERSION), b"{}")
    store.put_if_absent(layout.document_key(VERSION, "doc_001"), b"{}")  # type: ignore[arg-type]
    store.put_if_absent(layout.runs_prefix(VERSION) + "r-1/export.json", b"{}")
    assert discover_versions(store) == (VERSION, OTHER)

    store.put_if_absent("worlds/notes.txt", b"hello")
    with pytest.raises(ServingRefused, match="names no world version"):
        discover_versions(store)


def test_a_projected_world_with_an_approving_verdict_is_served_on_that_verdict() -> None:
    store, content = projected_store()
    served = admit(store, VERSION, development=False)
    assert isinstance(served, ServedWorld)
    assert served.projection is WorldProjection.PROJECTED
    assert served.manifest is not None and served.manifest.world_version == VERSION
    assert served.manifest_digest == hashlib.sha256(content).hexdigest()
    assert served.verdict_key == layout.verdict_key(VERSION, "100", "1")


def test_a_manifest_less_world_is_declined_under_a_bucket_and_admitted_on_a_root() -> None:
    store = InMemoryObjectStore()
    store.put_if_absent(layout.scenario_specs_key(VERSION), b"{}")
    declined = admit(store, VERSION, development=False)
    assert declined == NotServed(
        VERSION, "no manifest under its final key: not a completed projection"
    )
    # A development world is admitted on its levels object, the last write of an unprojected
    # sealing; without it the sealing stopped (the external review's second finding).
    stopped = admit(store, VERSION, development=True)
    assert isinstance(stopped, NotServed) and stopped.reason.startswith("no levels object")
    store.put_if_absent(layout.levels_key(VERSION), levels_bytes(BASE_CORPUS_LEVELS))
    served = admit(store, VERSION, development=True)
    assert served == ServedWorld(VERSION, WorldProjection.UNPROJECTED, None, None, None)


def test_only_a_verdict_approving_these_manifest_bytes_serves() -> None:
    # A re-projection onto other sites keeps the version and changes every receipt, so the
    # earlier verdict's manifest digest no longer matches: not served on it.
    store, content = projected_store(approved=False)
    declined = admit(store, VERSION, development=False)
    assert isinstance(declined, NotServed) and "1 verdict(s) read" in declined.reason

    other_bytes = manifest_bytes(manifest(observed_sites={}))
    assert other_bytes != content
    store.put_if_absent(
        layout.verdict_key(VERSION, "101", "1"), verdict_bytes(verdict(judged=other_bytes))
    )
    declined = admit(store, VERSION, development=False)
    assert isinstance(declined, NotServed) and "2 verdict(s) read" in declined.reason

    store.put_if_absent(
        layout.verdict_key(VERSION, "102", "1"), verdict_bytes(verdict(judged=content))
    )
    served = admit(store, VERSION, development=False)
    assert isinstance(served, ServedWorld)
    assert served.verdict_key == layout.verdict_key(VERSION, "102", "1")


def test_a_wrong_stage_a_wrong_version_and_an_undecodable_verdict_refuse() -> None:
    store = InMemoryObjectStore()
    store.put_if_absent(
        layout.world_manifest_key(VERSION), manifest_bytes(manifest(ManifestStage.PREPARING))
    )
    with pytest.raises(ServingRefused, match="does not decode as a projected manifest"):
        admit(store, VERSION, development=False)

    store = InMemoryObjectStore()
    store.put_if_absent(layout.world_manifest_key(OTHER), manifest_bytes(manifest()))
    with pytest.raises(ServingRefused, match="names world"):
        admit(store, OTHER, development=False)

    store, _ = projected_store()
    store.put_if_absent(layout.verdict_key(VERSION, "099", "1"), b'{"format": 1}')
    with pytest.raises(ServingRefused, match="does not decode as a verdict"):
        admit(store, VERSION, development=False)


def test_the_summary_reads_what_the_validator_wrote_and_refuses_another_format_or_word() -> None:
    content = manifest_bytes(manifest())
    full = verdict(judged=content)
    summary = decode_verdict_summary(verdict_bytes(full))
    assert summary == VerdictSummary(
        VERSION, VALIDATOR_VERSION, full.manifest_digest, Approval.APPROVED
    )
    assert summary.approval is full.approval
    assert summary.approves(VERSION, full.manifest_digest)
    assert not summary.approves(OTHER, full.manifest_digest)
    assert decode_verdict_summary(
        verdict_bytes(verdict(judged=content, passed=False))
    ).approval is (Approval.REFUSED)

    encoded = json.loads(verdict_bytes(full))
    # Format 1 verdicts, the ones the bucket holds from validator version 1, still decode;
    # they approve nothing for serving, since an older logic judged a shorter list.
    older = decode_verdict_summary(json.dumps({**encoded, "format": 1, "validator_version": "1"}))
    assert older.approval is Approval.APPROVED
    assert not older.approves(VERSION, full.manifest_digest)
    assert summary.validator_version == VALIDATOR_VERSION
    with pytest.raises(ValueError, match="one of formats \\[1, 2\\], got 3"):
        decode_verdict_summary(json.dumps({**encoded, "format": 3}))
    with pytest.raises(ValueError, match="approval is one of"):
        decode_verdict_summary(json.dumps({**encoded, "approval": "maybe"}))
