DO $$
DECLARE
  schema json := '{
    "type": "object",
    "required": ["name"],
    "properties": {"name": {"type": "string"}}
  }';
BEGIN
  IF jsonb_matches_schema(schema, '{"name":"Ada"}'::jsonb) IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'pg_jsonschema rejected a valid JSON Schema instance';
  END IF;

  IF jsonb_matches_schema(schema, '{"name":42}'::jsonb) IS DISTINCT FROM false THEN
    RAISE EXCEPTION 'pg_jsonschema accepted an invalid JSON Schema instance';
  END IF;
END
$$;
