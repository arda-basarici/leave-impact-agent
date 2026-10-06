-- The event log's tables: the attempt rows the store locks, the events they own, the
-- admission requests, the shared ledger and the publication records. Schema version 1.
--
-- Idempotent DDL, applied whole by the store's ensure_schema as bootstrap, never as
-- migration (the event log step's ruling on placement and acceptance, part 3): no ALTER
-- over old rows, no migration framework. Unlike the corpus cache, whose rows are
-- regenerated from the world bundle, a log's rows are not regenerable, so the schema's
-- version is a row here and the store refuses a connection to another version instead
-- of guessing. The rules of what a log may hold are the transition function's and are
-- not written a second time here: the keys enforce identity (one event per position, one
-- event per identifier, one segment start per claim nonce) and nothing about legality.

CREATE TABLE IF NOT EXISTS log_schema (
    singleton   boolean PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    version     integer NOT NULL
);

-- One row per run: locked to number attempts and to check the predecessor before an
-- attempt row exists to lock. attempts is the highest attempt number admitted.
CREATE TABLE IF NOT EXISTS run (
    run_id      text PRIMARY KEY,
    attempts    integer NOT NULL DEFAULT 0
);

-- The attempt row: the generation a claim increments, the segments opened, the last
-- position taken, open or closed, the log format set at admission, and the ledger the
-- reservation was made against (null exactly when nothing was reserved). Coordination
-- only; the log below is the history.
CREATE TABLE IF NOT EXISTS attempt (
    run_id      text    NOT NULL REFERENCES run (run_id),
    attempt     integer NOT NULL,
    generation  integer NOT NULL,
    segments    integer NOT NULL,
    positions   integer NOT NULL,
    closed      boolean NOT NULL,
    log_format  integer NOT NULL,
    ledger_id   text,
    PRIMARY KEY (run_id, attempt)
);

-- The log: record is the logged event whole (position, timestamp, envelope, kind,
-- content), key is the identifier's one text form, digest the content's, claim_nonce the
-- claiming process's nonce on a segment start.
CREATE TABLE IF NOT EXISTS event (
    run_id      text        NOT NULL,
    attempt     integer     NOT NULL,
    position    integer     NOT NULL,
    kind        text        NOT NULL,
    key         text        NOT NULL,
    claim_nonce text,
    recorded_at timestamptz NOT NULL,
    digest      text        NOT NULL,
    record      jsonb       NOT NULL,
    PRIMARY KEY (run_id, attempt, position),
    UNIQUE (run_id, attempt, kind, key),
    FOREIGN KEY (run_id, attempt) REFERENCES attempt (run_id, attempt)
);

CREATE UNIQUE INDEX IF NOT EXISTS event_claim_nonce
    ON event (run_id, attempt, claim_nonce) WHERE claim_nonce IS NOT NULL;

-- The recorded result of an admission request, committed before it is returned, so a
-- repeated request returns it and never reserves twice or advances the attempt number.
CREATE TABLE IF NOT EXISTS admission_request (
    request_id  text        PRIMARY KEY,
    run_id      text        NOT NULL,
    attempt     integer     NOT NULL,
    outcome     text        NOT NULL,
    result      jsonb       NOT NULL,
    recorded_at timestamptz NOT NULL
);

-- The shared ledger: one locked head per ledger, append-only entries whose revision is
-- the count of entries written, refusals and threshold changes included.
CREATE TABLE IF NOT EXISTS ledger_head (
    ledger_id           text    PRIMARY KEY,
    total_pico_usd      bigint  NOT NULL,
    revision            integer NOT NULL,
    threshold_pico_usd  bigint
);

CREATE TABLE IF NOT EXISTS ledger_entry (
    ledger_id               text        NOT NULL REFERENCES ledger_head (ledger_id),
    revision                integer     NOT NULL,
    kind                    text        NOT NULL,
    run_id                  text,
    attempt                 integer,
    amount_pico_usd         bigint      NOT NULL,
    total_after_pico_usd    bigint      NOT NULL,
    authority               text,
    registration_commit     text,
    reason                  text,
    recorded_at             timestamptz NOT NULL,
    PRIMARY KEY (ledger_id, revision)
);

-- One publication record per attempt, apart from the log: pending, published or failed
-- with its incident; published is never left.
CREATE TABLE IF NOT EXISTS publication (
    run_id                  text        NOT NULL,
    attempt                 integer     NOT NULL,
    state                   text        NOT NULL,
    reader_commit           text        NOT NULL,
    export_format           integer     NOT NULL,
    log_digest              text        NOT NULL,
    object_identity         text        NOT NULL,
    object_digest           text        NOT NULL,
    incident                text,
    repaired_from_commit    text,
    recorded_at             timestamptz NOT NULL,
    PRIMARY KEY (run_id, attempt),
    FOREIGN KEY (run_id, attempt) REFERENCES attempt (run_id, attempt)
);
