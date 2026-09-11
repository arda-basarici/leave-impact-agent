"""The corpus adapter against PostgreSQL: the claims only the real database can make.

What the writer added, the reader returns as the same document, sections in order,
and an absent id is ``None``; a document added after a read missed it survives the
adapter's close and is read by a fresh one — the projector's find-or-create sequence,
which a default connection's open transaction lost at the first review; search finds
by content under the web-search grammar
(a word, a quoted phrase, an exclusion), ranks the better match first, breaks a tie
by document id, honours the limit, and answers nothing for no match; two worlds
holding the same document and clause ids never read each other; a duplicate id is
refused whole — a second document whose clause id is taken leaves no document row,
the transaction the atomic write relies on — and the adapter goes on working after
the refusal; the schema bootstrap is idempotent, applied twice by every test's
fixture.

No cassette: the corpus is our own system and is tested on the terms it runs on.
``DATABASE_URL`` names the database (the CI service, or ``just db-up`` locally);
without it the tests skip, and fail under ``CI``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import psycopg
import pytest

from leaveimpact.adapters.corpus import CorpusAdapter, CorpusConfig
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind, Source
from leaveimpact.core.ids import clause_id, document_id
from leaveimpact.core.ports.errors import SourceUnreachable
from tests.integration.corpus_support import adapter_for, database_url, drop_world, fresh_world

pytestmark = pytest.mark.integration

POLICY = Document(
    document_id(1),
    "Leave policy",
    DocumentKind.POLICY,
    date(2026, 1, 1),
    (
        DocumentSection(clause_id(1), "Cover is named before leave starts."),
        DocumentSection(clause_id(2), "A handover precedes any leave over five days."),
        DocumentSection(clause_id(3), "Contractors follow the client's holiday calendar."),
    ),
)
RUNBOOK = Document(
    document_id(2),
    "Kafka ingest runbook",
    DocumentKind.RUNBOOK,
    date(2026, 3, 15),
    (
        DocumentSection(
            clause_id(4),
            "The Kafka ingest is owned by the Platform team; Kafka alerts page Deniz, "
            "who holds the pager.",
        ),
    ),
)
NOTE = Document(
    document_id(3),
    "Acme client note",
    DocumentKind.CLIENT_NOTE,
    date(2026, 6, 1),
    (
        DocumentSection(
            clause_id(5),
            "Acme's contact is Mara; escalations go through Kafka alerts and the pager.",
        ),
    ),
)
PROCEDURE = Document(
    document_id(4),
    "Release procedure",
    DocumentKind.PROCEDURE,
    date(2026, 2, 1),
    (DocumentSection(clause_id(6), "A release needs a named approver and a handover note."),),
)


@pytest.fixture
def url() -> str:
    return database_url()


@pytest.fixture
def adapter(url: str) -> Iterator[CorpusAdapter]:
    yield from adapter_for(url, fresh_world())


def test_documents_written_are_read_back(adapter: CorpusAdapter) -> None:
    adapter.ensure_schema()  # idempotent: the fixture already applied it
    locators = [adapter.add_document(doc) for doc in (POLICY, RUNBOOK, NOTE, PROCEDURE)]
    assert len(set(locators)) == 4 and all(locators)

    policy = adapter.document(POLICY.id)
    assert policy is not None and policy.source is Source.CORPUS and policy.value == POLICY
    for original in (RUNBOOK, NOTE, PROCEDURE):
        found = adapter.document(original.id)
        assert found is not None and found.value == original
    assert adapter.document(document_id(99)) is None


def test_a_document_added_after_a_missed_read_survives_the_close(url: str) -> None:
    world = fresh_world()
    first = CorpusAdapter(dsn=url, config=CorpusConfig(world))
    try:
        first.ensure_schema()
        assert first.document(POLICY.id) is None, "the projector's find"
        first.add_document(POLICY)
        first.close()
        second = CorpusAdapter(dsn=url, config=CorpusConfig(world))
        found = second.document(POLICY.id)
        assert found is not None and found.value == POLICY, "the write outlived the connection"
        second.close()
    finally:
        first.close()
        drop_world(url, world)


def test_search_finds_by_content_ranks_and_breaks_ties_by_id(adapter: CorpusAdapter) -> None:
    for doc in (POLICY, RUNBOOK, NOTE, PROCEDURE):
        adapter.add_document(doc)

    def ids(query: str, limit: int = 10) -> list[str]:
        return [item.value.id for item in adapter.search(query, limit=limit)]

    assert ids("handover") == [POLICY.id, PROCEDURE.id]
    kafka = ids("kafka")
    assert set(kafka) == {RUNBOOK.id, NOTE.id}
    assert kafka[0] == RUNBOOK.id, "two mentions in a body outrank one; titles are not indexed"
    assert ids("pager") == [RUNBOOK.id, NOTE.id], "equal rank falls back to the document id"
    assert ids("pager", limit=1) == [RUNBOOK.id]
    assert ids('"named approver"') == [PROCEDURE.id]
    assert ids("handover -release") == [POLICY.id]
    assert ids("submarine") == []
    assert ids("") == []
    found = adapter.search("holiday", limit=5)
    assert len(found) == 1 and found[0].value == POLICY, "a hit returns the whole document"


def test_two_worlds_with_the_same_ids_never_read_each_other(url: str) -> None:
    world_a, world_b = fresh_world(), fresh_world()
    a = CorpusAdapter(dsn=url, config=CorpusConfig(world_a))
    b = CorpusAdapter(dsn=url, config=CorpusConfig(world_b))
    try:
        a.ensure_schema()
        a.add_document(POLICY)
        other = Document(
            POLICY.id,
            "A different policy",
            DocumentKind.POLICY,
            date(2027, 1, 1),
            (DocumentSection(clause_id(1), "Nothing here mentions the handover."),),
        )
        b.add_document(other)
        read_a, read_b = a.document(POLICY.id), b.document(POLICY.id)
        assert read_a is not None and read_a.value == POLICY
        assert read_b is not None and read_b.value == other
        assert [item.value.id for item in a.search("cover", limit=5)] == [POLICY.id]
        assert a.search("different", limit=5) == ()
        assert [item.value.title for item in b.search("handover", limit=5)] == [other.title]
        assert b.document(RUNBOOK.id) is None
    finally:
        a.close()
        b.close()
        drop_world(url, world_a)
        drop_world(url, world_b)


def test_a_duplicate_id_is_refused_whole_and_the_adapter_goes_on(adapter: CorpusAdapter) -> None:
    adapter.add_document(POLICY)
    with pytest.raises(ValueError, match="already exists"):
        adapter.add_document(POLICY)
    clashing = Document(
        document_id(7),
        "Clashing runbook",
        DocumentKind.RUNBOOK,
        date(2026, 5, 1),
        (
            DocumentSection(clause_id(8), "A fresh clause."),
            DocumentSection(clause_id(2), "This clause id belongs to the policy."),
        ),
    )
    with pytest.raises(ValueError, match="already exists"):
        adapter.add_document(clashing)
    assert adapter.document(clashing.id) is None, "no document row without its sections"
    assert adapter.add_document(RUNBOOK)
    found = adapter.document(RUNBOOK.id)
    assert found is not None and found.value == RUNBOOK


def test_an_unreachable_database_is_the_ports_fault(url: str) -> None:
    # A port nothing listens on; the seam shortens the timeout the adapter would wait.
    unreachable = CorpusAdapter(
        dsn="postgresql://leaveimpact:none@127.0.0.1:1/leaveimpact",
        config=CorpusConfig(fresh_world()),
        connect=lambda dsn: psycopg.connect(dsn, connect_timeout=1),
    )
    with pytest.raises(SourceUnreachable, match="corpus unreachable: connection refused"):
        unreachable.document(POLICY.id)
