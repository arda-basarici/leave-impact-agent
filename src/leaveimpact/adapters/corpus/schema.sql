-- The corpus cache tables: worlds, their levels, documents in sections, one world version
-- per row set.
--
-- Idempotent DDL, applied whole by the loader's ensure_schema as bootstrap, never as
-- migration: a corpus is regenerated from the sealed world, so a schema change is a
-- rebuilt database, not an ALTER over old rows, and the loader reads the columns back
-- after applying this file and refuses a table of an older shape by name (the M2 step 9
-- design, fork 9). Every key carries the world version so two worlds hold the same
-- document and clause ids side by side without either reading the other (versions
-- isolate rows, and share this DDL); the section's foreign key is composite for the same
-- reason.
--
-- A world row is the cache's statement that a version was filled from a served world:
-- which kind of world (projected and approved, or a development world sealed
-- unprojected), the digest of the manifest the verdict approved where there is one, and
-- `ready`, flipped as the last statement of the loading transaction, which every read
-- joins on so a version is served whole or not at all. A level row is a name and how
-- much of the pool it holds; a document's `pool_rank` is its position in the pool, null
-- for a scenario-owned document, so a level's membership is a filter the reads apply
-- before any ranking. The search column is generated from the section body under the
-- English configuration (the world writes English prose) and indexed with GIN; a
-- section's position keeps the document's order, which a tuple of sections carries and
-- a table would otherwise lose.

CREATE TABLE IF NOT EXISTS world (
    world_version   text    NOT NULL,
    projection      text    NOT NULL,
    manifest_digest text,
    ready           boolean NOT NULL DEFAULT false,
    PRIMARY KEY (world_version)
);

CREATE TABLE IF NOT EXISTS level (
    world_version   text    NOT NULL,
    name            text    NOT NULL,
    filler_count    integer NOT NULL,
    PRIMARY KEY (world_version, name),
    FOREIGN KEY (world_version) REFERENCES world (world_version)
);

CREATE TABLE IF NOT EXISTS document (
    world_version   text    NOT NULL,
    id              text    NOT NULL,
    title           text    NOT NULL,
    kind            text    NOT NULL,
    effective_from  date    NOT NULL,
    pool_rank       integer,
    PRIMARY KEY (world_version, id),
    FOREIGN KEY (world_version) REFERENCES world (world_version),
    UNIQUE (world_version, pool_rank)
);

CREATE TABLE IF NOT EXISTS section (
    world_version   text    NOT NULL,
    id              text    NOT NULL,
    document_id     text    NOT NULL,
    position        integer NOT NULL,
    body            text    NOT NULL,
    search          tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED,
    PRIMARY KEY (world_version, id),
    FOREIGN KEY (world_version, document_id) REFERENCES document (world_version, id),
    UNIQUE (world_version, document_id, position)
);

CREATE INDEX IF NOT EXISTS section_search ON section USING GIN (search);
