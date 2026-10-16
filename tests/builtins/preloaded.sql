CREATE EXTENSION pg_stat_statements;
CREATE TABLE builtin_stat_probe (value integer);
INSERT INTO builtin_stat_probe VALUES (4321);
SELECT value FROM builtin_stat_probe;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_stat_statements
        WHERE query LIKE '%FROM builtin_stat_probe%'
          AND calls >= 1
    ) THEN
        RAISE EXCEPTION 'pg_stat_statements did not record a packaged-server query';
    END IF;
END
$$;
