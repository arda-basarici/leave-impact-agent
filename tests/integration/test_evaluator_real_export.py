"""The evaluator over what the real store and worker produced: the reference run worked to
its closing, published by the publish command, listed by the inventory command, and then
evaluated as the artifact is built, the inventory named by its digest. The chain's first
test over the real producer's output: the evaluation names the inventory it read, the
export is the listed attempt's current publication, and the coverage counts one run
admitted and exported with nothing open or unpublished."""

from __future__ import annotations

import pytest

from leaveimpact.adapters.object_store.layout import runs_prefix
from leaveimpact.adapters.wiring import inventory_publisher_over, run_export_publisher_over
from leaveimpact.agent.commands import (
    InventoryRequest,
    PublishRequest,
    publish,
    write_inventory,
)
from leaveimpact.agent.inventory import PublicationRecord
from leaveimpact.core import PublicationStatus, registration_bytes
from leaveimpact.core.inventory import InventoryScope
from leaveimpact.evaluator.artifact import (
    Disposition,
    EvaluatorRevision,
    StoredRun,
    cited_commits,
    evaluation_artifact,
)
from leaveimpact.evaluator.harness_inventory import is_inventory_object, read_inventory
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import bundle
from tests.integration.log_store_support import Rig, rig
from tests.integration.worker_rig import ATTEMPT, LEDGER, RULES, RUN, completed
from tests.unit import format_fixtures as cases
from tests.unit.registration_fixture import DRAFT, light
from tests.unit.throwaway_world import composed_world, loaded_world, sealed_stores

pytestmark = pytest.mark.integration

_ = rig  # the fixture, imported for pytest to find

INVENTORY_DECIDED = frozenset(
    {
        Disposition.SUPERSEDED,
        Disposition.PUBLICATION_UNFINISHED,
        Disposition.PUBLICATION_ORPHAN,
        Disposition.NOT_IN_INVENTORY,
    }
)


@pytest.fixture(scope="module")
def world() -> SealedWorld:
    return loaded_world("golden")


def test_the_real_export_is_evaluated_under_the_inventory_the_harness_wrote(
    rig: Rig, world: SealedWorld
) -> None:
    store, inputs = completed(rig, world)
    stores = sealed_stores(bundle(composed_world()))
    version = inputs.context.world_version
    assert version == world.version
    record = publish(
        PublishRequest(RUN, ATTEMPT, cases.COMMIT),
        store,
        run_export_publisher_over(stores.world),
        rules=RULES,
    )
    assert isinstance(record, PublicationRecord) and record.state is PublicationStatus.PUBLISHED
    scope = InventoryScope(version, cases.COMMIT, LEDGER)
    written = write_inventory(
        InventoryRequest(scope, cases.COMMIT),
        store,
        inventory_publisher_over(stores.world),
        rules=RULES,
    )

    # As the entry point lists and reads: every object under the runs prefix outside the
    # inventory prefix, and the named inventory apart, verified against its name.
    runs: list[StoredRun] = []
    for key in stores.world.list_keys(runs_prefix(version)):
        if is_inventory_object(version, key):
            continue
        held = stores.world.get(key)
        assert held is not None
        runs.append(StoredRun(key, held.version_id, held.content))
    stored = stores.world.get(written.key)
    assert stored is not None
    inventory, read = read_inventory(version, written.digest, stored.content)
    registration = registration_bytes(light(DRAFT))
    at = {commit: registration for commit in cited_commits(runs, inventory)}
    artifact = evaluation_artifact(
        world,
        registration,
        runs,
        at,
        EvaluatorRevision(cases.COMMIT, cases.COMMIT, ()),
        inventory=inventory,
        inventory_read=read,
    )

    assert artifact.harness_inventory == read
    assert (read.digest, read.attempts, read.refused) == (written.digest, 1, 0)
    (entry,) = artifact.listing
    assert entry.key == record.object_identity
    assert entry.digest == record.object_digest
    # The listed attempt's current publication: whatever its settings make of it, it is
    # none of the dispositions the inventory decides, and its trace was evaluated.
    assert entry.disposition not in INVENTORY_DECIDED
    assert entry.evaluation is not None
    coverage = artifact.coverage
    assert (coverage.admitted, coverage.attempts, coverage.exported) == (1, 1, 1)
    assert (coverage.open, coverage.closed_without_export) == (0, 0)
    assert (coverage.publication_incidents, coverage.unexported) == (0, ())
    assert coverage.never_admitted == coverage.intended - 1
