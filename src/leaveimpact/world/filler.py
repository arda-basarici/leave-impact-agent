"""The filler pool as a transform over a world, and the one enumeration of a world's documents.

Filler is attached after the whole assembly and before any prose is written, and stripped
for the unchanged-answers test, so both directions are plain transforms over the semantic
world: ``with_filler`` returns the world with a pool, its briefs and its levels, and
``strip_filler`` returns it without. Their composition is the identity, which is the claim
the generator must keep when the pool comes from its own randomness (the generator step's
ruling 6). A composed world is refused by both: its semantic digest is of the world it was
composed from and its materialization record names that world's briefs, so a pool changed
after composition leaves provenance the resume path refuses (the group's external review,
2026-10-08, reproduced on a sealed bundle).

``world_documents`` is the one place that says what "the world's documents" are, owned
first in scenario order and then the pool in rank order. Before the pool existed five
callers enumerated the owned documents each on their own (the projection, the receipt
check, the validator's expected set, the evaluator's index, the writer's lexicon), and
each would have missed filler alone; they read this function now.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol

from leaveimpact.core.entities import Document
from leaveimpact.world.assembly import SemanticWorld, WorldSpec
from leaveimpact.world.briefs import Brief
from leaveimpact.world.levels import BASE_LEVELS, SealedLevel
from leaveimpact.world.scenario import OwnedEntities, Planted


class _Owning(Protocol):
    @property
    def owned(self) -> OwnedEntities: ...


class HoldsDocuments(Protocol):
    """What the enumeration reads: a scenario row per scenario and the pool. The semantic
    world and the sealed spec both are one, so the validator reads the same function."""

    @property
    def scenarios(self) -> Sequence[_Owning]: ...

    @property
    def filler(self) -> tuple[Planted[Document], ...]: ...


def world_documents(world: HoldsDocuments) -> tuple[Planted[Document], ...]:
    """Every document the world seals: the scenarios' own in scenario order, then the pool in
    rank order. The set every projection, receipt, validation and index is held to."""
    owned = (planted for scenario in world.scenarios for planted in scenario.owned.documents)
    return (*owned, *world.filler)


def with_filler(
    semantic: SemanticWorld,
    filler: Sequence[Planted[Document]],
    briefs: Sequence[Brief] = (),
    levels: Sequence[SealedLevel] = BASE_LEVELS,
) -> SemanticWorld:
    """``semantic`` carrying ``filler`` as its pool, ``briefs`` as the parts a model still owes
    the pool, and ``levels`` as the cutoffs sealed over it; the world's own invariants refuse
    a pool that is not minted after every planted document, and a composed world is refused
    (``TypeError``) since its provenance would describe another world."""
    _uncomposed(semantic, "attached")
    return replace(
        semantic, filler=tuple(filler), filler_briefs=tuple(briefs), levels=tuple(levels)
    )


def strip_filler(semantic: SemanticWorld) -> SemanticWorld:
    """``semantic`` with no pool, no filler briefs and the base level alone: the world the
    seed produces without filler, if the pool was minted last; a composed world is refused
    (``TypeError``)."""
    _uncomposed(semantic, "stripped")
    return replace(semantic, filler=(), filler_briefs=(), levels=BASE_LEVELS)


def _uncomposed(semantic: SemanticWorld, verb: str) -> None:
    if isinstance(semantic, WorldSpec):
        raise TypeError(
            f"a pool is {verb} on the semantic world before composition: a composed world's "
            "semantic digest and materialization record are of the world it was composed from"
        )
