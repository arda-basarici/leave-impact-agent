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

-- The backup's capture (the demo milestone's backup ruling, as the exchange with the
-- platform of 2026-10-23 settled it): one row per ledger of the figures the ledger tables hold outright or as a
-- sum over their columns, read by the nightly backup script inside the dump's own
-- repeatable-read transaction and recorded on the dump's object, then read again from
-- the restored scratch database by the restore verification and compared row for row.
-- Open reservations are the admitted entries no settled entry has closed (a visitor who
-- leaves is settled by the sweeper, never released, so admitted-and-not-settled is the
-- ledger's own notion of open). The retained liability is not here on purpose: the
-- account rule derives it from decoded log events, and a second copy of that rule in SQL
-- would drift from the one in `core.run_account`; the verification computes it on the
-- restored database and checks it against the settled entries instead. Replaced, never
-- altered, so a column can join at the end and the version row still names the layout.
CREATE OR REPLACE VIEW ledger_capture AS
SELECT
    head.ledger_id,
    head.total_pico_usd,
    head.revision,
    head.threshold_pico_usd,
    coalesce(open_entries.open_reservation_pico_usd, 0) AS open_reservation_pico_usd,
    coalesce(open_entries.open_attempts, 0)             AS open_attempts
FROM ledger_head AS head
LEFT JOIN (
    SELECT
        admitted.ledger_id,
        sum(admitted.amount_pico_usd)::bigint AS open_reservation_pico_usd,
        count(*)::integer                     AS open_attempts
    FROM ledger_entry AS admitted
    WHERE admitted.kind = 'admitted'
      AND NOT EXISTS (
          SELECT 1 FROM ledger_entry AS settled
          WHERE settled.ledger_id = admitted.ledger_id
            AND settled.run_id    = admitted.run_id
            AND settled.attempt   = admitted.attempt
            AND settled.kind      = 'settled'
      )
    GROUP BY admitted.ledger_id
) AS open_entries ON open_entries.ledger_id = head.ledger_id;

-- One row per attempt a visitor started (the live-path commands step): the public id of
-- the publishable row the start wrote beside it, the attempt, the SHA-256 of the key the
-- initiating browser holds (the request identity the log recorded the admission under,
-- and the capability's hash the decision route compares with; the key itself is stored
-- nowhere), the log's instant of the admission, and the decision as the decision command
-- recorded it, null until then. No deadline column: it derives from the approval
-- request's instant on the log and the configured wait. The log is the authority for
-- every column here; a row that disagrees with it is repaired under its lock, never
-- trusted. Version 3 added this table and nothing else.
CREATE TABLE IF NOT EXISTS live_attempt (
    public_id       text        PRIMARY KEY REFERENCES publishable_attempt (public_id),
    run_id          text        NOT NULL,
    attempt         integer     NOT NULL,
    key_digest      text        NOT NULL UNIQUE,
    started_at      timestamptz NOT NULL,
    decision        text        CHECK (decision IN ('approved', 'declined')),
    decided_at      timestamptz,
    CHECK ((decision IS NULL) = (decided_at IS NULL)),
    UNIQUE (run_id, attempt),
    FOREIGN KEY (run_id, attempt) REFERENCES attempt (run_id, attempt)
);
