\set ON_ERROR_STOP on
SELECT current_setting('server_version') AS postgres_version;
CREATE EXTENSION pg_jsonschema;

CREATE TABLE schema_checked (
    payload jsonb NOT NULL,
    CONSTRAINT payload_matches_schema CHECK (
        jsonb_matches_schema(
            '{"type":"object","properties":{"name":{"type":"string","maxLength":8}},"required":["name"]}',
            payload
        )
    )
);

INSERT INTO schema_checked VALUES ('{"name":"Codex"}');
DO $$
BEGIN
    IF NOT jsonb_matches_schema('{"type":"integer","minimum":2}', '3'::jsonb) THEN
        RAISE EXCEPTION 'expected valid JSON value to match schema';
    END IF;
    IF jsonb_matches_schema('{"type":"integer","minimum":2}', '1'::jsonb) THEN
        RAISE EXCEPTION 'expected invalid JSON value to fail schema';
    END IF;
    BEGIN
        INSERT INTO schema_checked VALUES ('{"name":"too long a name"}');
        RAISE EXCEPTION 'expected table constraint to reject invalid JSON';
    EXCEPTION WHEN check_violation THEN
        NULL;
    END;
END
$$;

SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_jsonschema';
SELECT conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint WHERE conrelid = 'schema_checked'::regclass;
