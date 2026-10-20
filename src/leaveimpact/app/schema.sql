-- The demo surface's own tables, beside the run log in the same database and apart from
-- its schema file: the log is the investigator's record and never learns what the demo
-- publishes (the demo milestone's publishability ruling, "an app-owned table"). Applied
-- idempotently by `python -m leaveimpact.app bootstrap`, which the deploy runs after the
-- log's bootstrap; the version row is written where absent and checked at every read the
-- surface makes, so a database at another layout refuses rather than misreads.

CREATE TABLE IF NOT EXISTS app_schema (
    singleton   boolean PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    version     integer NOT NULL
);

-- One row per attempt the surface may show: the public name a URL carries (never the
-- run id or the attempt number, which are the workflow's naming and the retry history),
-- the attempt it names, the world version and scenario copied from the attempt's
-- admission when the row was written and compared with the admission again before any
-- content is served, the walkthrough title an introduced example carries, and who
-- published it when. The log's attempt row is referenced, so a row for an attempt the
-- log does not hold cannot exist; the log is append-only, so the reference blocks
-- nothing that would otherwise happen. The world version here is a projection for the
-- listing, never the admission itself: the read model's content resolution reads the
-- admission from the log and refuses a row that disagrees with it.
CREATE TABLE IF NOT EXISTS publishable_attempt (
    public_id       text        PRIMARY KEY,
    run_id          text        NOT NULL,
    attempt         integer     NOT NULL,
    world_version   text        NOT NULL,
    scenario_id     text        NOT NULL,
    title           text,
    published_at    timestamptz NOT NULL,
    published_by    text        NOT NULL,
    UNIQUE (run_id, attempt),
    FOREIGN KEY (run_id, attempt) REFERENCES attempt (run_id, attempt)
);
