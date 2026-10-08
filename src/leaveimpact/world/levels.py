"""The corpus levels a world seals, and what a filler pool must hold to be sealed.

A world may carry a pool of answer-neutral *filler* documents owned by no scenario, in
rank order, and a short list of levels, each a name and a count: a level holds every
scenario-owned document and the first ``filler_count`` documents of the pool. Membership
is derived from those two things and listed nowhere, so levels are nested and every
answer-bearing document is in every level by construction, which is the size contract
the arms interview fixed (2026-10-04). The base level is the world with no filler added;
it is always sealed, so the evaluator's level reader answers it for a world sealed before
any pool existed and answers nothing for a name the world never sealed.

The registration's ``CorpusLevel`` carries the token size a level was built to; this
type carries a count, because a token count is one tokenizer's and the world is
model-neutral (the generator step's rulings 1 and 6).

The invariants live here, apart from the world types, because the semantic world and
the sealed spec both hold a pool and must state the same things of it, and so does the
served side: ``CorpusLevels`` is what the world seals beside its documents for the corpus
cache to read (the M2 step 9 design, fork 1), since the pool's order and the levels are on
the world spec in the truth bucket and the instance may read only the world bucket. It
carries the levels and the pool's ids in rank order and nothing of what a document says,
so membership is derivable where the documents are served and the answer key stays where
it is.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from leaveimpact.core.entities import Document
from leaveimpact.core.ids import DocumentId, is_numbered_id
from leaveimpact.core.run_record import BASE_CORPUS_LEVEL
from leaveimpact.world.briefs import Brief, SectionTarget
from leaveimpact.world.scenario import Planted


@dataclass(frozen=True, slots=True)
class SealedLevel:
    """One corpus level as the world seals it: its name and how much of the pool it holds."""

    name: str
    filler_count: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a level has a name")
        if self.filler_count < 0:
            raise ValueError(f"{self.name}: a level's filler count is non-negative")
        if self.name == BASE_CORPUS_LEVEL and self.filler_count != 0:
            raise ValueError(
                f"the {BASE_CORPUS_LEVEL} level is the world with no filler added, "
                f"got {self.filler_count}"
            )


BASE_LEVELS: tuple[SealedLevel, ...] = (SealedLevel(BASE_CORPUS_LEVEL, 0),)
"""What a world seals when it seals no pool: the base level alone."""


@dataclass(frozen=True, slots=True)
class FillerPlan:
    """What a pool is asked to be: how many documents, how many sections each, and the
    levels beyond the base sealed over it.

    A sealed input of the assembly (the generator step's group 2): the pool is minted inside
    the assembly from this and the seed, and a resume reproduces it from the same, the two
    counts out of the provenance and the levels out of the spec's own ``levels`` field, so
    no byte is written twice. ``NO_FILLER`` is the plan every caller had before pools
    existed and the one a pinned world is assembled under.
    """

    documents: int
    sections_per_document: int
    levels: tuple[SealedLevel, ...] = ()

    def __post_init__(self) -> None:
        if self.documents < 0:
            raise ValueError(
                f"a filler plan's document count is non-negative, got {self.documents}"
            )
        if self.documents and self.sections_per_document < 1:
            raise ValueError("a filler document holds at least one section")
        if not self.documents and self.sections_per_document:
            raise ValueError("a plan with no documents has no sections")
        if not self.documents and self.levels:
            # The provenance writes a plan only when it has documents, so a level over an
            # empty pool would be sealed and never read back (the group 2 review).
            raise ValueError("a plan with no documents seals no level beyond the base")
        names = [level.name for level in self.levels]
        if BASE_CORPUS_LEVEL in names:
            raise ValueError(f"the {BASE_CORPUS_LEVEL} level is always sealed and never planned")
        if len(set(names)) != len(names):
            raise ValueError(f"a level is sealed once, got {names}")
        over = [
            (level.name, level.filler_count)
            for level in self.levels
            if level.filler_count > self.documents
        ]
        if over:
            raise ValueError(
                f"a level holds at most the pool's {self.documents} documents, got {over}"
            )


NO_FILLER = FillerPlan(0, 0)
"""No pool: what every assembly built before pools existed and what a pinned world takes."""


def check_plan_describes_pool(
    plan: FillerPlan,
    filler: Sequence[Planted[Document]],
    briefs: Sequence[Brief],
    levels: Sequence[SealedLevel],
) -> None:
    """Refuse a world whose sealed plan and sealed pool disagree: the document count, the
    levels (the base and then the plan's), and every document holding exactly the planned
    sections between the ones present and the ones a brief still owes, each brief at a
    position the document can hold and no two at one position. A brief whose section is
    present is composed and counted once, so the check reads the semantic and the
    composed world alike."""
    if len(filler) != plan.documents:
        raise ValueError(
            f"the plan asks {plan.documents} filler documents and the pool holds {len(filler)}"
        )
    if tuple(levels) != (*BASE_LEVELS, *plan.levels):
        raise ValueError(
            f"the sealed levels {[level.name for level in levels]} are not the base and the "
            f"plan's {[level.name for level in plan.levels]}"
        )
    present = {section.id for planted in filler for section in planted.entity.sections}
    positions: dict[str, list[int]] = {planted.entity.id: [] for planted in filler}
    for brief in briefs:
        target = brief.target
        if not isinstance(target, SectionTarget) or target.id in present:
            continue
        if target.document_id in positions:
            positions[target.document_id].append(target.position)
    for planted in filler:
        owed = positions[planted.entity.id]
        held = len(planted.entity.sections) + len(owed)
        if held != plan.sections_per_document:
            raise ValueError(
                f"{planted.entity.id}: the plan gives a filler document "
                f"{plan.sections_per_document} sections, got {held}"
            )
        if len(set(owed)) != len(owed) or any(p < 0 or p >= held for p in owed):
            raise ValueError(
                f"{planted.entity.id}: briefed positions {sorted(owed)} do not fit {held} sections"
            )


def check_pool(
    filler: Sequence[Planted[Document]],
    levels: Sequence[SealedLevel],
    briefs: Sequence[Brief],
    owned_document_ids: Iterable[str],
) -> None:
    """Refuse a pool, its levels or its briefs that cannot describe one world.

    Filler ids are unique, and every filler id is numbered above every planted document's,
    which also keeps the two sets apart, because the pool is minted after the whole
    assembly so the planted part of a world is what the seed produces without filler (the
    generator step's ruling 3). Level names are unique, the base level is present and no
    level holds more than the pool. A filler brief targets a section of a filler document
    and no brief is written twice.
    """
    owned = tuple(owned_document_ids)
    ids = [planted.entity.id for planted in filler]
    if len(set(ids)) != len(ids):
        raise ValueError(f"a filler document is sealed once, got {ids}")
    if ids and owned:
        last_planted = max(owned, key=_number)
        first_filler = min(ids, key=_number)
        if _number(first_filler) <= _number(last_planted):
            raise ValueError(
                f"filler is minted after every planted document, got {first_filler} "
                f"beside {last_planted}"
            )
    names = [level.name for level in levels]
    if len(set(names)) != len(names):
        raise ValueError(f"a level is sealed once, got {names}")
    if BASE_CORPUS_LEVEL not in names:
        raise ValueError(f"the {BASE_CORPUS_LEVEL} level is always sealed, got {names}")
    over = [(level.name, level.filler_count) for level in levels if level.filler_count > len(ids)]
    if over:
        raise ValueError(f"a level holds at most the pool's {len(ids)} documents, got {over}")
    brief_ids = [brief.id for brief in briefs]
    if len(set(brief_ids)) != len(brief_ids):
        raise ValueError(f"a filler part is briefed once, got {brief_ids}")
    pool = set(ids)
    for brief in briefs:
        if not isinstance(brief.target, SectionTarget) or brief.target.document_id not in pool:
            raise ValueError(
                f"a filler brief targets a section of a filler document, got {brief.id} "
                f"on {brief.target.id}"
            )


@dataclass(frozen=True, slots=True)
class CorpusLevels:
    """The levels a world seals and the pool's document ids in rank order: the served side's
    statement of membership, from which ``level_members`` answers for any sealed level.

    Refuses what cannot describe one world: a level sealed twice, no base level, a level
    holding more than the pool, a pool id sealed twice or one that is not a document id.
    A world with no pool is the base level over an empty pool.

    >>> CorpusLevels((SealedLevel("base", 0), SealedLevel("padded", 1)), (DocumentId("doc_009"),))
    ... # doctest: +ELLIPSIS
    CorpusLevels(levels=(SealedLevel(name='base', filler_count=0), ...), pool=('doc_009',))
    >>> CorpusLevels((SealedLevel("padded", 1),), (DocumentId("doc_009"),))
    Traceback (most recent call last):
    ...
    ValueError: the base level is always sealed, got ['padded']
    """

    levels: tuple[SealedLevel, ...]
    pool: tuple[DocumentId, ...]

    def __post_init__(self) -> None:
        names = [level.name for level in self.levels]
        if len(set(names)) != len(names):
            raise ValueError(f"a level is sealed once, got {names}")
        if BASE_CORPUS_LEVEL not in names:
            raise ValueError(f"the {BASE_CORPUS_LEVEL} level is always sealed, got {names}")
        over = [
            (level.name, level.filler_count)
            for level in self.levels
            if level.filler_count > len(self.pool)
        ]
        if over:
            raise ValueError(
                f"a level holds at most the pool's {len(self.pool)} documents, got {over}"
            )
        if len(set(self.pool)) != len(self.pool):
            raise ValueError(f"a pool document is sealed once, got {list(self.pool)}")
        foreign = [id for id in self.pool if not (id.startswith("doc_") and is_numbered_id(id))]
        if foreign:
            raise ValueError(f"a pool holds document ids, got {foreign}")

    def filler_count(self, name: str) -> int | None:
        """How much of the pool the level ``name`` holds, or ``None`` for a level never sealed."""
        for level in self.levels:
            if level.name == name:
                return level.filler_count
        return None


BASE_CORPUS_LEVELS = CorpusLevels(BASE_LEVELS, ())
"""What a world sealed before the levels object existed states: the base level, no pool."""


def corpus_levels_of(
    filler: Sequence[Planted[Document]], levels: Sequence[SealedLevel]
) -> CorpusLevels:
    """The served-side record of a world's pool and levels, in the pool's sealed order."""
    return CorpusLevels(tuple(levels), tuple(DocumentId(planted.entity.id) for planted in filler))


def level_members(
    name: str,
    levels: Sequence[SealedLevel],
    owned_document_ids: Iterable[str],
    filler_document_ids: Sequence[str],
) -> frozenset[str] | None:
    """The document ids the level ``name`` holds, or ``None`` when the world seals no such level.

    ``None`` is the statement that nothing says what that level holds; it is not an empty
    level, and the level check reads it as not evaluated.

    >>> levels = (SealedLevel("base", 0), SealedLevel("padded", 2))
    >>> sorted(level_members("padded", levels, ["doc_001"], ["doc_002", "doc_003", "doc_004"]))
    ['doc_001', 'doc_002', 'doc_003']
    >>> sorted(level_members("base", levels, ["doc_001"], ["doc_002"]))
    ['doc_001']
    >>> level_members("huge", levels, ["doc_001"], ["doc_002"]) is None
    True
    """
    for level in levels:
        if level.name == name:
            return frozenset(owned_document_ids) | frozenset(
                filler_document_ids[: level.filler_count]
            )
    return None


def _number(id: str) -> int:
    """The number a numbered id ends in, the order the minting book handed ids out in."""
    return int(id.rsplit("_", 1)[-1])
