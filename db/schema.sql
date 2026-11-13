-- ============================================================
-- QA Agent Database Schema
-- ============================================================
-- Fresh-install schema reference. Existing databases use ordered migrations
-- in python-services/migrations/. Never remove volumes to upgrade a schema.
-- See docs/database-migrations.md for backup, status and apply commands.
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

-- Additive storage only. Native instruction execution remains unchanged.
ALTER TABLE tests ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0);
ALTER TABLE tests ADD COLUMN IF NOT EXISTS plan JSONB CHECK (
    plan IS NULL OR (
        jsonb_typeof(plan) = 'object'
        AND plan->'schema_version' = '1'::jsonb
        AND jsonb_typeof(plan->'steps') = 'array'
        AND plan->'steps' <> '[]'::jsonb
    ) IS TRUE
);

CREATE TABLE IF NOT EXISTS test_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID REFERENCES tests(id) ON DELETE SET NULL,
    original_test_id UUID NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    snapshot JSONB NOT NULL CHECK (jsonb_typeof(snapshot) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (original_test_id, revision)
);

CREATE INDEX IF NOT EXISTS idx_test_revisions_test_id ON test_revisions (test_id);

-- Preserve the definition that exists when this migration is applied, not an
-- invented pre-migration edit history. Rehearsed fresh installs may have it already.
INSERT INTO test_revisions (test_id, original_test_id, revision, snapshot)
SELECT id, id, revision, to_jsonb(tests) FROM tests
ON CONFLICT (original_test_id, revision) DO NOTHING;

CREATE OR REPLACE FUNCTION prepare_test_revision() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.revision := 1;
    ELSE
        -- A legacy instruction edit invalidates a previously stored plan.
        IF NEW.instruction IS DISTINCT FROM OLD.instruction
           AND NEW.plan IS NOT DISTINCT FROM OLD.plan THEN
            NEW.plan := NULL;
        END IF;
        IF ROW(NEW.name, NEW.instruction, NEW.variant, NEW.reruns, NEW.plan)
           IS DISTINCT FROM ROW(OLD.name, OLD.instruction, OLD.variant, OLD.reruns, OLD.plan) THEN
            NEW.revision := OLD.revision + 1;
            NEW.updated_at := clock_timestamp();
        ELSE
            NEW.revision := OLD.revision;
            NEW.updated_at := OLD.updated_at;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION record_test_revision() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.revision IS DISTINCT FROM OLD.revision THEN
        INSERT INTO test_revisions (test_id, original_test_id, revision, snapshot)
        VALUES (NEW.id, NEW.id, NEW.revision, to_jsonb(NEW));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER prepare_test_revision
BEFORE INSERT OR UPDATE ON tests FOR EACH ROW EXECUTE FUNCTION prepare_test_revision();

CREATE OR REPLACE TRIGGER record_test_revision
AFTER INSERT OR UPDATE ON tests FOR EACH ROW EXECUTE FUNCTION record_test_revision();
