"""Corpus row shapes, both directions: table rows to a document with its sections and back.

Pure: every function takes plain values and gives back entities or parameter tuples, so
where each fact lives in the four tables and what a row set must carry to be read back is
testable without a database. The adapter (``adapter``) owns the reading connection and its
SQL; the loader (``loader``) owns the writing transaction and its SQL.

**Where the facts live.** A world is one row in ``world`` — how it came to be, the
manifest digest its verdict approved, whether it is ready — and one row per sealed level
in ``level``. A document is one row in ``document`` — title, kind as the enum's value, the
effective date, its rank in the pool or null for a scenario-owned one — and one row per
section in ``section``, keyed by the clause id, with the position that keeps the tuple's
order. Every row carries the world version, which is the scope every statement filters
on: the corpus is the project's own system and holds a world per version, the way a
Frappe site holds a company and a Jira site a project.

**Malformed means untranslatable.** A kind outside the enum, a null where a value is
required, positions that do not run from zero without a gap — each raises
``MalformedRecord`` with ``document/<world version>/<id>`` as locator, never a silent
skip, because a dropped record would be graded as absence.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind, Source
from leaveimpact.core.ids import ClauseId, DocumentId, WorldVersion
from leaveimpact.core.ports.errors import MalformedRecord
from leaveimpact.core.run_record import WorldProjection
from leaveimpact.world.levels import SealedLevel

Row = tuple[Any, ...]

KIND_BY_VALUE: dict[str, DocumentKind] = {kind.value: kind for kind in DocumentKind}


def locator(world_version: WorldVersion, id: DocumentId | str) -> str:
    return f"document/{world_version}/{id}"


# --- writing ---------------------------------------------------------------------------


def world_params(
    world_version: WorldVersion, projection: WorldProjection, manifest_digest: str | None
) -> Row:
    """The ``world`` row as the loader first writes it: (world_version, projection,
    manifest_digest, ready), ready false until the loading transaction's last statement."""
    return (world_version, projection.value, manifest_digest, False)


def level_params(world_version: WorldVersion, levels: Sequence[SealedLevel]) -> list[Row]:
    """The ``level`` rows: (world_version, name, filler_count), one per sealed level."""
    return [(world_version, level.name, level.filler_count) for level in levels]


def document_params(
    document: Document, world_version: WorldVersion, pool_rank: int | None
) -> Row:
    """The ``document`` row: (world_version, id, title, kind, effective_from, pool_rank);
    ``pool_rank`` is the document's position in the pool and ``None`` for a scenario-owned
    document, which every level holds."""
    return (
        world_version,
        document.id,
        document.title,
        document.kind.value,
        document.effective_from,
        pool_rank,
    )


def section_params(document: Document, world_version: WorldVersion) -> list[Row]:
    """The ``section`` rows: (world_version, id, document_id, position, body), in order.

    >>> from leaveimpact.core.ids import clause_id, document_id
    >>> policy = Document(document_id(3), "Leave policy", DocumentKind.POLICY, date(2026, 1, 1),
    ...                   (DocumentSection(clause_id(7), "Cover is named."),
    ...                    DocumentSection(clause_id(8), "Handover precedes leave.")))
    >>> section_params(policy, WorldVersion("4f2c"))  # doctest: +NORMALIZE_WHITESPACE
    [('4f2c', 'clause_007', 'doc_003', 0, 'Cover is named.'),
     ('4f2c', 'clause_008', 'doc_003', 1, 'Handover precedes leave.')]
    """
    return [
        (world_version, section.id, document.id, position, section.text)
        for position, section in enumerate(document.sections)
    ]


# --- reading ---------------------------------------------------------------------------


def document_from_rows(
    document_row: Row, section_rows: Sequence[Row], world_version: WorldVersion
) -> Document:
    """A document from its row (id, title, kind, effective_from) and its section rows.

    The section rows are (id, position, body) in position order, as the adapter's
    query returns them; the positions are checked to run from zero without a gap, so
    a section lost between two others is malformed rather than silently absent.

    >>> document_from_rows(("doc_003", "Leave policy", "policy", date(2026, 1, 1)),
    ...                    [("clause_007", 0, "Cover is named.")], WorldVersion("4f2c"))
    ... # doctest: +NORMALIZE_WHITESPACE
    Document(id='doc_003', title='Leave policy', kind=<DocumentKind.POLICY: 'policy'>,
             effective_from=datetime.date(2026, 1, 1),
             sections=(DocumentSection(id='clause_007', text='Cover is named.'),))
    """
    id, title, kind, effective_from = document_row
    where = locator(world_version, str(id))
    if kind not in KIND_BY_VALUE:
        raise MalformedRecord(Source.CORPUS, where, f"kind {kind!r} is not one the domain knows")
    if not isinstance(effective_from, date):
        raise MalformedRecord(Source.CORPUS, where, "effective_from is not a date")
    sections: list[DocumentSection] = []
    for expected, (section_id, position, body) in enumerate(section_rows):
        if position != expected:
            raise MalformedRecord(
                Source.CORPUS, where, f"section positions skip from {expected} to {position}"
            )
        sections.append(
            DocumentSection(
                ClauseId(_text(section_id, "section id", where)),
                _text(body, "section body", where),
            )
        )
    return Document(
        id=DocumentId(_text(id, "id", where)),
        title=_text(title, "title", where),
        kind=KIND_BY_VALUE[kind],
        effective_from=effective_from,
        sections=tuple(sections),
    )


def _text(value: Any, what: str, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise MalformedRecord(Source.CORPUS, where, f"no {what}")
    return value
