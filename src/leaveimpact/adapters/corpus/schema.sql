-- The corpus tables: documents in sections, one world version per row set.
--
-- Idempotent DDL, applied whole by the adapter's ensure_schema as bootstrap, never as
-- migration: a corpus is regenerated from the world bundle, so a schema change is a
-- rebuilt database, not an ALTER over old rows. Every key carries the world version so
-- two worlds hold the same document and clause ids side by side without either reading
-- the other (versions isolate rows, and share this DDL); the section's foreign key is
-- composite for the same reason. The search column is generated from the section
-- body under the English configuration (the world writes English prose) and indexed
-- with GIN; a section's position keeps the document's order, which a tuple of sections
-- carries and a table would otherwise lose.

CREATE TABLE IF NOT EXISTS document (
    world_version   text NOT NULL,
    id              text NOT NULL,
    title           text NOT NULL,
    kind            text NOT NULL,
    effective_from  date NOT NULL,
    PRIMARY KEY (world_version, id)
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
