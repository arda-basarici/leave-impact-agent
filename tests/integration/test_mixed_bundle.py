"""The mixed-bundle gate (the M2 step 9 design, fork 10): a development world's three
structured systems read from its plantings and its documents read from the real corpus
cache, the rules-only baseline run on that bundle and on the all-in-memory one, both
exports conforming to the prefetch plan and recording the same operations and the same
claims; and the validator's document identity and field check run with the cache as the
document side, every sealed document present and equal at the base level.

The generator step's unprojected path and this step's loader meet here for the first time
over the real database: a composed world with filler is sealed to a local twin, the cache
job fills PostgreSQL from it, and the baseline reads the cache through the same port the
investigator will. The baseline reads no document, so the gate's claim about the document
side rests on the validator's check and on the port being the real adapter; the claim
about the structured side is that the planted readers and the cache compose into one
executor path with nothing in the export telling the two bundles apart.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from leaveimpact.adapters.corpus import CorpusAdapter, CorpusConfig
from leaveimpact.adapters.object_store.local import LocalObjectReader
from leaveimpact.adapters.object_store.local_write import LocalObjectWriter
from leaveimpact.adapters.plantings import planted_readers
from leaveimpact.agent.execution import ReadPorts
from leaveimpact.agent.registered import rules_only_provenance
from leaveimpact.agent.rules_only import RulesOnlyRun, investigate
from leaveimpact.cache.__main__ import main
from leaveimpact.core import (
    HarnessRevision,
    PricingBasis,
    RunContext,
    RunExport,
    TreeState,
    condition_id,
    decode_export_bytes,
    export_bytes,
)
from leaveimpact.core.entities import Document
from leaveimpact.core.enums import EntityKind
from leaveimpact.evaluator.prefetch_conformance import PrefetchConformance, prefetch_conformance
from leaveimpact.evaluator.sealed_world import SealedWorld, load_sealed_world
from leaveimpact.generator.sealing import seal_unprojected
from leaveimpact.validator.checks import compare_identities, compare_records
from leaveimpact.world import bundle
from tests.integration.corpus_support import database_url, drop_world
from tests.unit.export_fixture import export_baseline
from tests.unit.reads_fixture import systems_holding
from tests.unit.test_evaluator_prefetch_conformance import COMMIT, DIGEST, REGISTRATION
from tests.unit.throwaway_world import composed_world_with_filler

pytestmark = pytest.mark.integration

CONFORMS = PrefetchConformance(True, ())


def exported(result: RulesOnlyRun, context: RunContext) -> RunExport:
    """The real export of a baseline run, read back from its bytes, so the arguments the
    conformance check compares are the ones the wire carries (the unit-level helper's shape,
    over a result rather than over fakes)."""
    provenance = rules_only_provenance(
        REGISTRATION,
        condition_id(()),
        "base",
        harness=HarnessRevision(COMMIT, TreeState.CLEAN),
        preregistration_commit=COMMIT,
        pricing=PricingBasis(DIGEST, "USD", date(2026, 9, 1), ()),
    )
    export = export_baseline(
        result, context, provenance, run_id="run-1", attempt=1, duration_ms=1_200
    )
    return decode_export_bytes(export_bytes(export))


@pytest.fixture
def url() -> str:
    return database_url()


@pytest.fixture
def development_world(tmp_path: Path, url: str) -> Iterator[tuple[SealedWorld, str]]:
    """A composed golden world with two filler documents, sealed unprojected to a local twin,
    loaded as the evaluator loads it, and filled into the cache by the job; the rows dropped
    afterwards."""
    world = composed_world_with_filler(2)
    sealed = bundle(world)
    root = tmp_path / "store"
    seal_unprojected(
        world, sealed, LocalObjectWriter(root / "truth"), LocalObjectWriter(root / "world")
    )
    assert main(env={"LEAVE_IMPACT_OBJECT_STORE_ROOT": str(root), "DATABASE_URL": url}) == 0
    loaded = load_sealed_world(
        sealed.world_version, LocalObjectReader(root / "truth"), LocalObjectReader(root / "world")
    )
    try:
        yield loaded, url
    finally:
        drop_world(url, sealed.world_version)


def test_the_baseline_through_the_mixed_bundle_replays_as_through_the_in_memory_one(
    development_world: tuple[SealedWorld, str],
) -> None:
    world, url = development_world
    readers = planted_readers(world)
    cache = CorpusAdapter(dsn=url, config=CorpusConfig(world.version))
    mixed = ReadPorts(readers.people, readers.work, readers.calendar, cache)
    in_memory = systems_holding(world).ports
    try:
        for scenario in world.scenarios:
            context = world.context_of(scenario)
            through_cache = investigate(context, mixed)
            through_memory = investigate(context, in_memory)
            assert through_cache.operations == through_memory.operations, scenario.spec.id
            assert through_cache.claims == through_memory.claims, scenario.spec.id
            assert through_cache.failure is None and through_cache.abstention is None
            for result in (through_cache, through_memory):
                assert prefetch_conformance(exported(result, context)) == CONFORMS, scenario.spec.id
    finally:
        cache.close()


def test_the_validators_document_check_passes_against_the_cache(
    development_world: tuple[SealedWorld, str],
) -> None:
    # The validator's document side, run over the cache the way the live check runs it over
    # the sealed objects: the identities exact at the padded level, which holds the whole
    # pool, and every record equal field by field.
    world, url = development_world
    sealed_documents = {
        planted.entity.id: planted.entity
        for scenario in world.scenarios
        for planted in scenario.owned.documents
    }
    for ref in world.filler:
        pooled = world.index.records[ref]
        assert isinstance(pooled, Document), f"{ref} is the pool's and not a document"
        sealed_documents[pooled.id] = pooled
    assert len(sealed_documents) > 2, "the world holds planted documents beside the pool"
    padded = CorpusAdapter(dsn=url, config=CorpusConfig(world.version), level="padded")
    base = CorpusAdapter(dsn=url, config=CorpusConfig(world.version))
    try:
        held = padded.held_document_ids()
        exactness = compare_identities(EntityKind.DOCUMENT, sealed_documents, held)
        assert exactness.missing == () and exactness.foreign == ()
        read = {id: padded.document(id) for id in held}
        observed = {id: found.value for id, found in read.items() if found is not None}
        assert set(observed) == set(sealed_documents)
        assert compare_records(sealed_documents, observed) == ()
        pool = {ref.id for ref in world.filler}
        assert len(pool) == 2
        assert base.held_document_ids() == set(sealed_documents) - pool, (
            "the base level holds every planted document and no pool document"
        )
    finally:
        padded.close()
        base.close()
