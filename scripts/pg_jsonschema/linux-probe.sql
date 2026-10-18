\set ON_ERROR_STOP on
CREATE EXTENSION pg_jsonschema;
DO $$
BEGIN
    IF NOT jsonb_matches_schema('{"type":"object","required":["name"],"properties":{"name":{"type":"string"}}}', '{"name":"Ada"}'::jsonb) THEN
        RAISE EXCEPTION 'valid JSON did not match schema';
    END IF;
    IF jsonb_matches_schema('{"type":"object","required":["name"],"properties":{"name":{"type":"string"}}}', '{"name":7}'::jsonb) THEN
        RAISE EXCEPTION 'invalid JSON matched schema';
    END IF;
END
$$;
SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_jsonschema';
