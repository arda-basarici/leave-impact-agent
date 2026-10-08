"""The corpus loader without a database: the cache world's own refusals, the rows it makes,
and the schema check.

A cache world is one world or nothing: a projected one carries the manifest digest its
verdict approved and an unprojected one carries none, a document is cached once, and the
pool names documents the world holds. The row builders put each fact where the schema
reads it, the pool rank in particular, since a wrong rank is a document in the wrong
level and nothing downstream would notice. The schema check names the columns an older
table lacks, which is how a cache of the previous shape refuses to be altered.
"""

from __future__ import annotations

from datetime import date

import pytest

from leaveimpact.adapters.corpus import records
from leaveimpact.adapters.corpus.loader import (
    DOCUMENT_COLUMNS,
    CacheRefused,
    CacheWorld,
    check_document_columns,
)
from leaveimpact.core.entities import Document, DocumentSection
from leaveimpact.core.enums import DocumentKind
from leaveimpact.core.ids import WorldVersion, clause_id, document_id
from leaveimpact.core.run_record import WorldProjection
from leaveimpact.world.levels import BASE_CORPUS_LEVELS, CorpusLevels, SealedLevel

VERSION = WorldVersion("c" * 64)
DIGEST = "d" * 64
OWNED = Document(
    document_id(1),
    "Leave policy",
    DocumentKind.POLICY,
    date(2026, 1, 1),
    (DocumentSection(clause_id(1), "Cover is named."),),
)
FIRST = Document(document_id(8), "Filler one", DocumentKind.RUNBOOK, date(2026, 2, 1), ())
SECOND = Document(document_id(9), "Filler two", DocumentKind.RUNBOOK, date(2026, 2, 1), ())
PADDED = CorpusLevels((SealedLevel("base", 0), SealedLevel("padded", 2)), (SECOND.id, FIRST.id))


def test_a_projected_world_carries_its_digest_and_an_unprojected_one_none() -> None:
    projected = CacheWorld(VERSION, WorldProjection.PROJECTED, DIGEST, BASE_CORPUS_LEVELS, (OWNED,))
    assert projected.manifest_digest == DIGEST
    with pytest.raises(ValueError, match="manifest digest its verdict approved"):
        CacheWorld(VERSION, WorldProjection.PROJECTED, None, BASE_CORPUS_LEVELS, (OWNED,))
    with pytest.raises(ValueError, match="no manifest and no digest"):
        CacheWorld(VERSION, WorldProjection.UNPROJECTED, DIGEST, BASE_CORPUS_LEVELS, (OWNED,))


def test_a_document_is_cached_once_and_the_pool_names_held_documents() -> None:
    with pytest.raises(ValueError, match="cached once"):
        CacheWorld(VERSION, WorldProjection.UNPROJECTED, None, BASE_CORPUS_LEVELS, (OWNED, OWNED))
    with pytest.raises(ValueError, match="the world does not hold: \\['doc_009'\\]"):
        CacheWorld(VERSION, WorldProjection.UNPROJECTED, None, PADDED, (OWNED, FIRST))


def test_the_pool_rank_is_the_sealed_position_and_a_scenario_owned_document_has_none() -> None:
    world = CacheWorld(VERSION, WorldProjection.UNPROJECTED, None, PADDED, (OWNED, FIRST, SECOND))
    assert world.pool_rank(OWNED.id) is None
    assert world.pool_rank(SECOND.id) == 0, "the pool's order, not the id's"
    assert world.pool_rank(FIRST.id) == 1


def test_the_rows_put_each_fact_where_the_schema_reads_it() -> None:
    assert records.world_params(VERSION, WorldProjection.PROJECTED, DIGEST) == (
        VERSION,
        "projected",
        DIGEST,
        False,
    ), "ready is false until the transaction's last statement"
    assert records.level_params(VERSION, PADDED.levels) == [
        (VERSION, "base", 0),
        (VERSION, "padded", 2),
    ]
    assert records.document_params(FIRST, VERSION, 1) == (
        VERSION,
        FIRST.id,
        "Filler one",
        "runbook",
        date(2026, 2, 1),
        1,
    )
    assert records.document_params(OWNED, VERSION, None)[-1] is None


def test_the_schema_check_names_the_columns_an_older_table_lacks() -> None:
    check_document_columns(sorted(DOCUMENT_COLUMNS))
    check_document_columns([*DOCUMENT_COLUMNS, "a_column_a_later_schema_adds"])
    with pytest.raises(CacheRefused, match="lacks \\['pool_rank'\\]: an older schema"):
        check_document_columns(["world_version", "id", "title", "kind", "effective_from"])
