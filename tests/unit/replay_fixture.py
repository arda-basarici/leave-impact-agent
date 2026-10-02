"""A report replayed over a run's reads, for the tests of the grounding replay and of what its
records add up to.

Test infrastructure: builds the export a harness would, observes it against the sealed world
and replays its claims, so a test states a report and a set of reads and gets each claim's
grounding back.
"""

from __future__ import annotations

from collections.abc import Sequence

from leaveimpact.core import Claim, Operation
from leaveimpact.evaluator.observed_view import observe
from leaveimpact.evaluator.replay import ClaimGrounding, replay
from leaveimpact.evaluator.sealed_world import SealedWorld
from leaveimpact.world import Scenario
from tests.unit.export_fixture import run_export


def replayed(
    world: SealedWorld,
    scenario: Scenario,
    claims: Sequence[Claim],
    operations: Sequence[Operation] = (),
) -> dict[Claim, ClaimGrounding]:
    """Each claim of ``claims`` with its grounding, over what ``operations`` returned."""
    export = run_export(world, scenario, claims, operations=operations)
    records = replay(
        observe(world.index, export),
        world.index,
        export.trace.claims,
        scenario.spec.reference_timezone,
    )
    return dict(zip(export.trace.claims, records, strict=True))


__all__ = ["replayed"]
