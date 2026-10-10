"""The corpus cache against PostgreSQL: the claims only the real database can make.

What the loader loaded, the reader returns as the same document, sections in order, and
an absent id is ``None``; a version loaded after a reader's first call is read by the same
reader (autocommit, no snapshot held open); search finds by content under the web-search
grammar (a word, a quoted phrase, an exclusion), ranks the better match first, breaks a
tie by document id, honours the limit, and answers nothing for no match; two worlds
holding the same document and clause ids never read each other; the level filter is
applied before ranking, so the padded level finds a filler document the base level never
returns and the documents both hold come back in the same order (the rank reads no
statistic of the table: the M2 step 9 design, fork 4, probed here on the real service);
a version is served whole or not at all, a second load of a ready version changes
nothing, and a level the world never sealed is loud at the first read; the schema
bootstrap is idempotent, applied by every test's fixture.

No cassette: the corpus is our own system and is tested on the terms it runs on.
``DATABASE_URL`` names the database (the CI service, or ``just db-up`` locally);
without it the tests skip, and fail under ``CI``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import psycopg
import pytest

from leaveimpact.adapters.corpus import CorpusAdapter, CorpusConfig, UnservedCorpus
from leaveimpact.adapters.corpus.loader import LoadOutcome, ensure_schema, load_world
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind, Source
from leaveimpact.core.ids import clause_id, document_id
from leaveimpact.core.ports.errors import SourceUnreachable
from leaveimpact.core.ports.read import shown_order_key
from tests.integration.corpus_support import (
    cache_world,
    database_url,
    drop_world,
    fresh_world,
    loaded_adapter,
)

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
FILLER = Document(
    document_id(5),
    "Office pager etiquette",
    DocumentKind.RUNBOOK,
    date(2026, 4, 1),
    (
        DocumentSection(
            clause_id(7),
            "The pager is handed over at the start of every shift; Kafka alerts and Kafka "
            "digests both page it.",
        ),
    ),
)
ALL = (POLICY, RUNBOOK, NOTE, PROCEDURE)


@pytest.fixture
def url() -> str:
    return database_url()


@pytest.fixture
def adapter(url: str) -> Iterator[CorpusAdapter]:
    yield from loaded_adapter(url, cache_world(fresh_world(), ALL))


def ids(adapter: CorpusAdapter, query: str, limit: int = 10) -> list[str]:
    return [item.value.id for item in adapter.search(query, limit=limit)]


def test_documents_loaded_are_read_back(adapter: CorpusAdapter) -> None:
    policy = adapter.document(POLICY.id)
    assert policy is not None and policy.source is Source.CORPUS and policy.value == POLICY
    for original in (RUNBOOK, NOTE, PROCEDURE):
        found = adapter.document(original.id)
        assert found is not None and found.value == original
    assert adapter.document(document_id(99)) is None
    assert adapter.held_document_ids() == {doc.id for doc in ALL}


def test_a_version_loaded_after_a_readers_first_call_is_read_by_that_reader(url: str) -> None:
    world = cache_world(fresh_world(), (POLICY,))
    ensure_schema(url)
    reader = CorpusAdapter(dsn=url, config=CorpusConfig(world.version))
    try:
        with pytest.raises(UnservedCorpus):
            reader.document(POLICY.id)
        assert load_world(url, world) is LoadOutcome.LOADED
        found = reader.document(POLICY.id)
        assert found is not None and found.value == POLICY, "no snapshot held open"
        assert load_world(url, world) is LoadOutcome.ALREADY_READY
    finally:
        reader.close()
        drop_world(url, world.version)


def test_search_finds_by_content_ranks_and_breaks_ties_by_id(adapter: CorpusAdapter) -> None:
    assert ids(adapter, "handover") == [POLICY.id, PROCEDURE.id]
    kafka = ids(adapter, "kafka")
    assert set(kafka) == {RUNBOOK.id, NOTE.id}
    assert kafka[0] == RUNBOOK.id, "two mentions in a body outrank one; titles are not indexed"
    assert ids(adapter, "pager") == [RUNBOOK.id, NOTE.id], "equal rank falls back to the id"
    assert ids(adapter, "pager", limit=1) == [RUNBOOK.id]
    assert ids(adapter, '"named approver"') == [PROCEDURE.id]
    assert ids(adapter, "handover -release") == [POLICY.id]
    assert ids(adapter, "submarine") == []
    assert ids(adapter, "") == []
    found = adapter.search("holiday", limit=5)
    assert len(found) == 1 and found[0].value == POLICY, "a hit returns the whole document"


def test_the_level_filters_before_ranking_and_the_shared_order_is_unchanged(url: str) -> None:
    # The padded level holds the filler document; the base level never returns it, by id or
    # by search; and the documents both levels hold come back in one order under one
    # query, which is the probe that the rank reads no statistic of the table.
    world = cache_world(fresh_world(), (*ALL, FILLER), pool=(FILLER.id,), padded=1)
    ensure_schema(url)
    load_world(url, world)
    base = CorpusAdapter(dsn=url, config=CorpusConfig(world.version), level="base")
    padded = CorpusAdapter(dsn=url, config=CorpusConfig(world.version), level="padded")
    try:
        assert base.document(FILLER.id) is None
        found = padded.document(FILLER.id)
        assert found is not None and found.value == FILLER
        assert base.held_document_ids() == {doc.id for doc in ALL}
        assert padded.held_document_ids() == {doc.id for doc in ALL} | {FILLER.id}
        # The enumeration is the level's whole corpus in the shown order (the baselines
        # step, forks 8 and 9): the filler at padded only, every document whole, the order
        # the port's key fixes and not the ids' numbering.
        at_base = [seen.value for seen in base.documents()]
        at_padded = [seen.value for seen in padded.documents()]
        assert sorted(doc.id for doc in at_base) == sorted(doc.id for doc in ALL)
        assert sorted(doc.id for doc in at_padded) == sorted(doc.id for doc in (*ALL, FILLER))
        assert [doc.id for doc in at_padded] == sorted(
            (doc.id for doc in (*ALL, FILLER)), key=shown_order_key
        )
        assert all(doc in (*ALL, FILLER) for doc in at_padded)

        assert ids(base, "pager") == [RUNBOOK.id, NOTE.id]
        with_filler = ids(padded, "pager")
        assert FILLER.id in with_filler and len(with_filler) == 3
        assert [id for id in with_filler if id != FILLER.id] == [RUNBOOK.id, NOTE.id]
        # "kafka" is the query whose ranks differ (two mentions outrank one), so an order
        # that leaned on a statistic of the table could change once the filler, with its
        # own two mentions, joins the table: the review found the earlier queries were
        # ties the id tie-break ordered whatever the rank.
        assert ids(base, "kafka") == [RUNBOOK.id, NOTE.id]
        assert ids(padded, "kafka")[:1] == [RUNBOOK.id] or ids(padded, "kafka")[:1] == [FILLER.id]
        assert [id for id in ids(padded, "kafka") if id != FILLER.id] == [RUNBOOK.id, NOTE.id]
    finally:
        base.close()
        padded.close()
        drop_world(url, world.version)


def test_a_level_the_world_never_sealed_is_loud_at_the_first_read(url: str) -> None:
    world = cache_world(fresh_world(), ALL)
    with pytest.raises(UnservedCorpus, match="no level 'padded'"):
        next(iter(loaded_adapter(url, world, level="padded"))).document(POLICY.id)


def test_two_worlds_with_the_same_ids_never_read_each_other(url: str) -> None:
    other = Document(
        POLICY.id,
        "A different policy",
        DocumentKind.POLICY,
        date(2027, 1, 1),
        (DocumentSection(clause_id(1), "Nothing here mentions the handover."),),
    )
    world_a = cache_world(fresh_world(), (POLICY,))
    world_b = cache_world(fresh_world(), (other,))
    ensure_schema(url)
    load_world(url, world_a)
    load_world(url, world_b)
    a = CorpusAdapter(dsn=url, config=CorpusConfig(world_a.version))
    b = CorpusAdapter(dsn=url, config=CorpusConfig(world_b.version))
    try:
        read_a, read_b = a.document(POLICY.id), b.document(POLICY.id)
        assert read_a is not None and read_a.value == POLICY
        assert read_b is not None and read_b.value == other
        assert ids(a, "cover") == [POLICY.id]
        assert a.search("different", limit=5) == ()
        assert [item.value.title for item in b.search("handover", limit=5)] == [other.title]
        assert b.document(RUNBOOK.id) is None
        assert a.held_document_ids() == {POLICY.id} and b.held_document_ids() == {POLICY.id}
    finally:
        a.close()
        b.close()
        drop_world(url, world_a.version)
        drop_world(url, world_b.version)


def test_an_unreachable_database_is_the_ports_fault(url: str) -> None:
    # A port nothing listens on; the seam shortens the timeout the adapter would wait.
    unreachable = CorpusAdapter(
        dsn="postgresql://leaveimpact:none@127.0.0.1:1/leaveimpact",
        config=CorpusConfig(fresh_world()),
        connect=lambda dsn: psycopg.connect(dsn, connect_timeout=1),
    )
    with pytest.raises(SourceUnreachable, match="corpus unreachable: connection refused"):
        unreachable.document(POLICY.id)
    with pytest.raises(SourceUnreachable, match="corpus unreachable: connection refused"):
        load_world(
            "postgresql://leaveimpact:none@127.0.0.1:1/leaveimpact",
            cache_world(fresh_world(), (POLICY,)),
            connect=lambda dsn: psycopg.connect(dsn, connect_timeout=1),
        )


def test_two_loaders_on_a_fresh_version_serialize_and_the_second_finds_the_first(url: str) -> None:
    # A row lock cannot cover a row that is not there yet, so the loader takes the advisory
    # lock keyed by the version before it reads: here the first loader's transaction is
    # played by hand (the lock, the ready row, the level) and held while the second runs the
    # real loader in a thread, which must wait and then find the row rather than insert
    # beside it (the review's second finding, reproduced on the service before the lock).
    import threading

    world = cache_world(fresh_world(), (POLICY,))
    ensure_schema(url)
    outcome: list[LoadOutcome | BaseException] = []

    def second() -> None:
        try:
            outcome.append(load_world(url, world))
        except BaseException as error:  # noqa: BLE001 - the thread reports whatever it got
            outcome.append(error)

    first = psycopg.connect(url, connect_timeout=5)
    try:
        with first.transaction():
            first.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (world.version,))
            first.execute(
                "INSERT INTO world (world_version, projection, manifest_digest, ready) "
                "VALUES (%s, 'unprojected', NULL, true)",
                (world.version,),
            )
            first.execute(
                "INSERT INTO level (world_version, name, filler_count) VALUES (%s, 'base', 0)",
                (world.version,),
            )
            thread = threading.Thread(target=second)
            thread.start()
            thread.join(timeout=1.0)
            assert thread.is_alive(), "the second loader waits on the version's lock"
            assert outcome == []
        thread.join(timeout=10.0)
        assert outcome == [LoadOutcome.ALREADY_READY], outcome
    finally:
        first.close()
        drop_world(url, world.version)
