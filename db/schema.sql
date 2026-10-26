-- ============================================================
-- QA Agent Database Schema
-- ============================================================
-- This file is the source of truth for the database structure.
-- To apply changes:
--   1. Update this file
--   2. Copy changes to init.sql
--   3. Rebuild postgres container:
--      docker compose down -v && docker compose up
-- ============================================================


-- ------------------------------------------------------------
-- tests
-- Stores saved test definitions created by the user.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    instruction     TEXT NOT NULL,
    variant         TEXT NOT NULL DEFAULT 'original',
    reruns          INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tests_created_at
    ON tests (created_at DESC);


-- ------------------------------------------------------------
-- runs
-- Stores individual test run results.
-- Matches the exact shape of runs.json entries.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    saved_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    test_id                     UUID REFERENCES tests(id) ON DELETE SET NULL,

    title                       TEXT,
    description                 TEXT,

    status                      TEXT NOT NULL
                                    CHECK (status IN ('passed', 'failed', 'flaky')),
    flaky                       BOOLEAN NOT NULL DEFAULT FALSE,
    duration_ms                 INTEGER,
    run_count                   INTEGER NOT NULL DEFAULT 1,

    -- healing summary
    healed_count                INTEGER NOT NULL DEFAULT 0,
    was_healed                  BOOLEAN NOT NULL DEFAULT FALSE,
    total_cost_usd              NUMERIC(10, 6) NOT NULL DEFAULT 0,

    root_cause_title            TEXT,
    root_cause_summary          TEXT,
    root_cause_likely_cause     TEXT,
    root_cause_recommendation   TEXT,
    root_cause_evidence         TEXT,

    accessibility_score         INTEGER,
    accessibility_issue_count   INTEGER NOT NULL DEFAULT 0,
    accessibility_warning_count INTEGER NOT NULL DEFAULT 0,
    accessibility_passed_count  INTEGER NOT NULL DEFAULT 0,

    started_at                  TIMESTAMPTZ,
    finished_at                 TIMESTAMPTZ,
    run_number                  INTEGER,

    instruction                 TEXT,
    variant                     TEXT NOT NULL DEFAULT 'original',

    screenshot_path             TEXT,
    result_json                 JSONB NOT NULL
);

-- indexes for common queries
CREATE INDEX IF NOT EXISTS idx_runs_saved_at
    ON runs (saved_at DESC);

CREATE INDEX IF NOT EXISTS idx_runs_status
    ON runs (status);

CREATE INDEX IF NOT EXISTS idx_runs_test_id
    ON runs (test_id);

CREATE INDEX IF NOT EXISTS idx_runs_started_at
    ON runs (started_at DESC);

CREATE INDEX IF NOT EXISTS idx_runs_result_json
    ON runs USING GIN (result_json);


-- ------------------------------------------------------------
-- healed_selectors
-- Stores confirmed healing decisions approved by the user.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS healed_selectors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    saved_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_id          UUID REFERENCES runs(id) ON DELETE SET NULL,
    step_name       TEXT NOT NULL,
    old_selector    TEXT,
    new_selector    TEXT,
    old_target      TEXT NOT NULL,
    new_target      TEXT NOT NULL,
    decision        TEXT NOT NULL
                        CHECK (decision IN ('approved', 'rejected')),
    confidence      NUMERIC(4, 3),
    strategy        TEXT
);

CREATE INDEX IF NOT EXISTS idx_healed_selectors_old_target
    ON healed_selectors (old_target)
    WHERE decision = 'approved';

CREATE INDEX IF NOT EXISTS idx_healed_selectors_saved_at
    ON healed_selectors (saved_at DESC);

CREATE INDEX IF NOT EXISTS idx_healed_selectors_run_id
    ON healed_selectors (run_id);