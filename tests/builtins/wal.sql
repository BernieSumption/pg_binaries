CREATE EXTENSION pg_walinspect;
CREATE TEMP TABLE builtin_wal_start AS
    SELECT pg_current_wal_insert_lsn() AS lsn;
CREATE TABLE builtin_wal_probe (value integer);
INSERT INTO builtin_wal_probe VALUES (57);
DO $$
DECLARE
    inspected record;
BEGIN
    SELECT * INTO inspected
    FROM pg_get_wal_record_info((SELECT lsn FROM builtin_wal_start));
    IF inspected.start_lsn IS NULL
       OR inspected.start_lsn < (SELECT lsn FROM builtin_wal_start)
       OR inspected.record_length <= 0
       OR inspected.resource_manager IS NULL THEN
        RAISE EXCEPTION 'pg_walinspect did not decode a generated WAL record';
    END IF;
END
$$;
