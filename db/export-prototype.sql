-- Run with psql -X -qAt -v ON_ERROR_STOP=1 -v team=local -f ... -o ...
-- Read-only single-statement snapshot of the prototype schema, NOT Fuse's schema.
-- Secret/session, job, scan, agent, cache and member records are not exported.
SELECT jsonb_build_object(
    'format_version', 1,
    'records', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'team_id', team_id, 'kind', kind, 'id', id, 'data', data
        ) ORDER BY kind, id)
        FROM records
        WHERE team_id = :'team' AND kind IN ('test', 'run', 'approval')
    ), '[]'::jsonb),
    'revisions', COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
            'team_id', team_id, 'test_id', test_id, 'revision', revision, 'data', data
        ) ORDER BY test_id, revision)
        FROM test_revisions
        WHERE team_id = :'team'
    ), '[]'::jsonb)
);
