"""The corpus adapter without a database: the row translation, and the connection fault seam.

The claims PostgreSQL cannot make cheaply: a document's rows read back as the entity
they were made from, sections in position order; a kind the domain does not know, a
null where a value is required, and a gap in the positions are each malformed with
the document as locator; a connection that cannot be opened is ``SourceUnreachable``
after one attempt, and a statement that fails on a broken connection discards it so
the next call opens a fresh one; a negative limit is the caller's bug and a zero
limit asks the database nothing.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import psycopg
import pytest

from leaveimpact.adapters.corpus import CorpusAdapter, CorpusConfig, records
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind
from leaveimpact.core.ids import WorldVersion, clause_id, document_id
from leaveimpact.core.ports.errors import MalformedRecord, SourceUnreachable
from leaveimpact.core.ports.read import DocumentReader
from leaveimpact.core.ports.write import DocumentWriter

WORLD = WorldVersion("test-world")
POLICY = Document(
    document_id(3),
    "Leave policy",
    DocumentKind.POLICY,
    date(2026, 1, 1),
    (
        DocumentSection(clause_id(7), "Cover is named before leave starts."),
        DocumentSection(clause_id(8), "A handover precedes any leave over five days."),
    ),
)


def rows(document: Document) -> tuple[records.Row, list[records.Row]]:
    """The rows as the adapter's two selects return them, made from the write params."""
    _, id, title, kind, effective_from = records.document_params(document, WORLD)
    sections = [
        (section_id, position, body)
        for _, section_id, _, position, body in records.section_params(document, WORLD)
    ]
    return (id, title, kind, effective_from), sections


def test_rows_read_back_as_the_document_in_position_order() -> None:
    document_row, section_rows = rows(POLICY)
    assert records.document_from_rows(document_row, section_rows, WORLD) == POLICY
    assert records.document_from_rows(document_row, [], WORLD).sections == ()


@pytest.mark.parametrize(
    ("document_row", "section_rows", "reason"),
    [
        (("doc_003", "Leave policy", "memo", date(2026, 1, 1)), [], "kind 'memo' is not one"),
        (("doc_003", None, "policy", date(2026, 1, 1)), [], "no title"),
        (("doc_003", "Leave policy", "policy", "2026-01-01"), [], "effective_from is not a date"),
        (
            ("doc_003", "Leave policy", "policy", date(2026, 1, 1)),
            [("clause_007", 0, "a"), ("clause_009", 2, "c")],
            "section positions skip from 1 to 2",
        ),
        (
            ("doc_003", "Leave policy", "policy", date(2026, 1, 1)),
            [("clause_007", 0, "")],
            "no section body",
        ),
    ],
)
def test_untranslatable_rows_are_malformed_with_the_document_as_locator(
    document_row: records.Row, section_rows: list[records.Row], reason: str
) -> None:
    with pytest.raises(MalformedRecord, match=re.escape(reason)) as caught:
        records.document_from_rows(document_row, section_rows, WORLD)
    assert caught.value.locator == "document/test-world/doc_003"


class Refusing:
    """A connect seam that refuses, counting the attempts."""

    def __init__(self) -> None:
        self.attempts = 0

    def __call__(self, dsn: str) -> psycopg.Connection[Any]:
        self.attempts += 1
        raise psycopg.OperationalError("connection refused")


def adapter(connect: Any) -> CorpusAdapter:
    return CorpusAdapter(
        dsn="postgresql://nobody@localhost/none", config=CorpusConfig(WORLD), connect=connect
    )


def test_the_adapter_conforms_to_both_document_ports() -> None:
    built = adapter(Refusing())
    reader: DocumentReader = built
    writer: DocumentWriter = built
    assert reader is writer


def test_construction_opens_nothing_and_a_refused_connection_is_unreachable_after_one_attempt() -> (
    None
):
    refusing = Refusing()
    built = adapter(refusing)
    assert refusing.attempts == 0
    with pytest.raises(SourceUnreachable, match="corpus unreachable: connection refused"):
        built.document(POLICY.id)
    assert refusing.attempts == 1
    with pytest.raises(SourceUnreachable):
        built.search("cover", limit=5)
    assert refusing.attempts == 2, "no retry within a call; a fresh attempt per call"


class Breaking:
    """A connection whose every statement fails as the wire would; ``closed`` counts discards."""

    closed = 0

    def execute(self, *args: Any) -> Any:
        raise psycopg.OperationalError("server closed the connection unexpectedly")

    def close(self) -> None:
        Breaking.closed += 1


def test_a_statement_that_fails_on_the_wire_discards_the_connection() -> None:
    made: list[Breaking] = []

    def connect(dsn: str) -> Any:
        made.append(Breaking())
        return made[-1]

    built = adapter(connect)
    with pytest.raises(SourceUnreachable, match="statement failed: OperationalError"):
        built.document(POLICY.id)
    with pytest.raises(SourceUnreachable):
        built.document(POLICY.id)
    assert len(made) == 2 and Breaking.closed == 2, "a broken connection is dropped, not reused"


def test_a_negative_limit_is_the_callers_bug_and_zero_asks_nothing() -> None:
    refusing = Refusing()
    built = adapter(refusing)
    with pytest.raises(ValueError, match="limit must not be negative"):
        built.search("cover", limit=-1)
    assert built.search("cover", limit=0) == ()
    assert refusing.attempts == 0
