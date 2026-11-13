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
