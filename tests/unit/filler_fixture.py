"""A hand-built filler pool over a real world, for every test that needs one.

The pool's content is the generator's to write (the generator step's group 2); these
helpers mint stand-in documents after the world's own ids, derive every number from the
world rather than guessing it, and write stand-in bodies for whatever the world owes, so a
test holds the world's statements about a pool whoever made it. Test infrastructure, not
an adapter.
"""

from __future__ import annotations

from leaveimpact.core.anchors import SurfaceForm
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind, EntityKind
from leaveimpact.core.ids import clause_id, document_id
from leaveimpact.world import (
    BASE_LEVELS,
    Brief,
    Namespace,
    Planted,
    Register,
    SealedLevel,
    SectionTarget,
    SemanticWorld,
    with_filler,
)

PADDED = SealedLevel("padded", 2)
"""A second level over the first two filler documents, beside the base."""

FILLER_TEXT = "Stand-in filler text."


def number_of(id: str) -> int:
    return int(id.rsplit("_", 1)[-1])


def next_numbers(world: SemanticWorld) -> tuple[int, int]:
    """The first document and clause numbers above every planted one, pending briefs included:
    a pending brief targets a clause no section holds yet, so its id counts too."""
    documents = [p.entity for s in world.scenarios for p in s.owned.documents]
    last_document = max((number_of(d.id) for d in documents), default=0)
    clause_ids = [c.id for d in documents for c in d.sections] + [
        b.target.id
        for s in world.scenarios
        for b in s.briefs
        if isinstance(b.target, SectionTarget)
    ]
    last_clause = max((number_of(id) for id in clause_ids), default=0)
    return last_document + 1, last_clause + 1


def filler_documents(
    world: SemanticWorld, count: int, *, pending: int = 0
) -> tuple[Planted[Document], ...]:
    """``count`` stand-in filler documents minted after the world's own; the first ``pending``
    of them have no section, so a brief can owe one."""
    first_document, first_clause = next_numbers(world)
    observable_from = world.world_start
    pool: list[Planted[Document]] = []
    for offset in range(count):
        number = first_document + offset
        sections = (
            ()
            if offset < pending
            else (DocumentSection(clause_id(first_clause + offset), FILLER_TEXT),)
        )
        pool.append(
            Planted(
                Document(
                    document_id(number),
                    f"Stand-in handbook {number}",
                    DocumentKind.POLICY,
                    observable_from,
                    sections,
                ),
                observable_from,
            )
        )
    return tuple(pool)


def filler_brief(document: Document, clause_number: int) -> Brief:
    """A brief owing ``document`` one section at position zero, with no facts; its namespace
    names the document itself, since a section's writer is told which document it writes."""
    return Brief(
        target=SectionTarget(clause_id(clause_number), document.id, 0),
        required=(),
        allowed=(),
        namespace=Namespace(
            (SurfaceForm(EntityKind.DOCUMENT.value, document.id, document.title),), (), ()
        ),
        register=Register.POLICY,
    )


def stand_in_bodies(world: SemanticWorld) -> dict[str, str]:
    """A body for every part the world still owes, the way the stand-in fixture writes them."""
    return {id: f"Stand-in text for {id}." for id in sorted(world.pending_ids)}


def padded_world(
    world: SemanticWorld,
    count: int = 3,
    *,
    pending: int = 0,
    levels: tuple[SealedLevel, ...] = (*BASE_LEVELS, PADDED),
) -> SemanticWorld:
    """``world`` with ``count`` stand-in filler documents, the first ``pending`` owing a section
    through a brief each, and ``levels`` sealed over the pool."""
    pool = filler_documents(world, count, pending=pending)
    _, first_clause = next_numbers(world)
    briefs = tuple(
        filler_brief(planted.entity, first_clause + count + index)
        for index, planted in enumerate(pool[:pending])
    )
    return with_filler(world, pool, briefs=briefs, levels=levels)
