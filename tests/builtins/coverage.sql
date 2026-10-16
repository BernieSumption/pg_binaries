CREATE EXTENSION pg_surgery;
DO $$
DECLARE
    missing text;
BEGIN
    SELECT string_agg(name, ', ' ORDER BY name) INTO missing
    FROM (
        SELECT name FROM pg_available_extensions
        EXCEPT
        SELECT extname AS name FROM pg_extension
    ) AS uncovered;
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'bundled SQL extensions without a pilot case: %', missing;
    END IF;
END
$$;
