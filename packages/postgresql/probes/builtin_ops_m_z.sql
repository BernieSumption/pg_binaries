\set ON_ERROR_STOP on

-- The verifier creates these extensions before running this probe.

CREATE TABLE builtin_ops_moddatetime (id integer PRIMARY KEY, updated_at timestamp NOT NULL);
CREATE TRIGGER builtin_ops_moddatetime_trigger
    BEFORE UPDATE ON builtin_ops_moddatetime
    FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
INSERT INTO builtin_ops_moddatetime VALUES (1, CURRENT_TIMESTAMP);
UPDATE builtin_ops_moddatetime SET updated_at = NULL WHERE id = 1;
DO $$
BEGIN
    IF (SELECT updated_at IS NULL FROM builtin_ops_moddatetime WHERE id = 1) THEN
        RAISE EXCEPTION 'moddatetime did not set the updated timestamp';
    END IF;
END
$$;

CREATE TABLE builtin_ops_pageinspect (value integer);
INSERT INTO builtin_ops_pageinspect VALUES (1);
CREATE INDEX builtin_ops_pageinspect_idx ON builtin_ops_pageinspect USING btree (value);
DO $$
BEGIN
    IF (SELECT root FROM bt_metap('builtin_ops_pageinspect_idx')) < 1 THEN
        RAISE EXCEPTION 'pageinspect returned invalid B-tree metadata';
    END IF;
END
$$;

CREATE TABLE builtin_ops_buffercache (value integer);
INSERT INTO builtin_ops_buffercache VALUES (19);
DO $$
BEGIN
    IF (SELECT count(*) FROM pg_buffercache)
       <> pg_size_bytes(current_setting('shared_buffers'))
          / current_setting('block_size')::bigint THEN
        RAISE EXCEPTION 'pg_buffercache returned an unexpected descriptor count';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_buffercache
        WHERE relfilenode = pg_relation_filenode('builtin_ops_buffercache'::regclass)
          AND reldatabase = (SELECT oid FROM pg_database WHERE datname = current_database())
    ) THEN
        RAISE EXCEPTION 'pg_buffercache did not show the probe table';
    END IF;
END
$$;

CREATE TABLE builtin_ops_freespacemap (value integer);
INSERT INTO builtin_ops_freespacemap VALUES (1);
DO $$
DECLARE
    free_bytes integer;
BEGIN
    free_bytes := pg_freespace('builtin_ops_freespacemap'::regclass, 0);
    IF free_bytes IS NULL OR free_bytes < 0
       OR free_bytes > current_setting('block_size')::integer THEN
        RAISE EXCEPTION 'pg_freespacemap returned an invalid free-space value';
    END IF;
END
$$;

DO $$
BEGIN
    IF pg_prewarm('pg_catalog.pg_class'::regclass) < 1 THEN
        RAISE EXCEPTION 'pg_prewarm did not load pg_class';
    END IF;
END
$$;

CREATE TABLE builtin_ops_stat_statements (value integer);
INSERT INTO builtin_ops_stat_statements VALUES (4321);
SELECT value FROM builtin_ops_stat_statements;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_stat_statements
        WHERE query LIKE '%FROM builtin_ops_stat_statements%'
          AND calls >= 1
    ) THEN
        RAISE EXCEPTION 'pg_stat_statements did not record the probe query';
    END IF;
END
$$;

CREATE TABLE builtin_ops_surgery (value integer);
INSERT INTO builtin_ops_surgery VALUES (42);
SELECT ctid::text AS surgery_tid FROM builtin_ops_surgery \gset
SELECT heap_force_kill('builtin_ops_surgery'::regclass, ARRAY[:'surgery_tid'::tid]);
DO $$
BEGIN
    IF EXISTS (SELECT FROM builtin_ops_surgery) THEN
        RAISE EXCEPTION 'pg_surgery did not hide the killed probe tuple';
    END IF;
END
$$;

DO $$
BEGIN
    IF similarity('word', 'word') IS DISTINCT FROM 1.0::real THEN
        RAISE EXCEPTION 'pg_trgm returned an unexpected similarity';
    END IF;
END
$$;

CREATE TABLE builtin_ops_visibility (value integer);
INSERT INTO builtin_ops_visibility SELECT generate_series(1, 100);
VACUUM builtin_ops_visibility;
DO $$
BEGIN
    IF (SELECT all_visible FROM pg_visibility_map('builtin_ops_visibility'::regclass, 0))
       IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'pg_visibility did not report the vacuumed page as all-visible';
    END IF;
END
$$;

CREATE TEMP TABLE builtin_ops_wal_start AS
    SELECT pg_current_wal_insert_lsn() AS lsn;
CREATE TABLE builtin_ops_wal (value integer);
INSERT INTO builtin_ops_wal VALUES (57);
DO $$
DECLARE
    inspected record;
BEGIN
    SELECT * INTO inspected
    FROM pg_get_wal_record_info((SELECT lsn FROM builtin_ops_wal_start));
    IF inspected.start_lsn IS NULL
       OR inspected.start_lsn < (SELECT lsn FROM builtin_ops_wal_start)
       OR inspected.record_length <= 0
       OR inspected.resource_manager IS NULL THEN
        RAISE EXCEPTION 'pg_walinspect did not decode a generated WAL record';
    END IF;
END
$$;

DO $$
BEGIN
    IF encode(digest('abc', 'sha256'), 'hex')
       IS DISTINCT FROM 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad' THEN
        RAISE EXCEPTION 'pgcrypto returned an unexpected SHA-256 digest';
    END IF;
END
$$;

CREATE TABLE builtin_ops_rowlocks (value integer);
INSERT INTO builtin_ops_rowlocks VALUES (31);
DO $$
BEGIN
    IF (SELECT count(*) FROM pgrowlocks('builtin_ops_rowlocks')) <> 0 THEN
        RAISE EXCEPTION 'pgrowlocks reported a lock when no row is locked';
    END IF;
END
$$;

CREATE TABLE builtin_ops_pgstattuple (value integer);
INSERT INTO builtin_ops_pgstattuple VALUES (1), (2), (3);
DO $$
BEGIN
    IF (SELECT tuple_count FROM pgstattuple('builtin_ops_pgstattuple')) <> 3 THEN
        RAISE EXCEPTION 'pgstattuple returned an unexpected live tuple count';
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION builtin_ops_plpgsql_probe() RETURNS integer
LANGUAGE plpgsql
AS $$ BEGIN RETURN 42; END $$;
DO $$
BEGIN
    IF builtin_ops_plpgsql_probe() <> 42 THEN
        RAISE EXCEPTION 'PL/pgSQL function returned an unexpected value';
    END IF;
END
$$;

CREATE SERVER builtin_ops_fdw_server FOREIGN DATA WRAPPER postgres_fdw
  OPTIONS (dbname 'postgres');
CREATE USER MAPPING FOR CURRENT_USER SERVER builtin_ops_fdw_server;
CREATE FOREIGN TABLE builtin_ops_fdw_catalog (oid oid, relname name)
  SERVER builtin_ops_fdw_server
  OPTIONS (schema_name 'pg_catalog', table_name 'pg_class');
DO $$
BEGIN
    IF (SELECT count(*) FROM builtin_ops_fdw_catalog) < 1 THEN
        RAISE EXCEPTION 'postgres_fdw returned no rows from the loopback catalogue';
    END IF;
END
$$;

CREATE TABLE builtin_ops_refint_parent (id integer NOT NULL UNIQUE);
CREATE TABLE builtin_ops_refint_child (parent_id integer);
CREATE TRIGGER builtin_ops_refint_child_check
    AFTER INSERT OR UPDATE ON builtin_ops_refint_child
    FOR EACH ROW EXECUTE FUNCTION check_primary_key(
        'parent_id', 'builtin_ops_refint_parent', 'id');
CREATE TRIGGER builtin_ops_refint_parent_cascade
    AFTER DELETE OR UPDATE ON builtin_ops_refint_parent
    FOR EACH ROW EXECUTE FUNCTION check_foreign_key(
        1, 'cascade', 'id', 'builtin_ops_refint_child', 'parent_id');
INSERT INTO builtin_ops_refint_parent VALUES (1);
INSERT INTO builtin_ops_refint_child VALUES (1);
DELETE FROM builtin_ops_refint_parent WHERE id = 1;
DO $$
BEGIN
    IF EXISTS (SELECT FROM builtin_ops_refint_child) THEN
        RAISE EXCEPTION 'refint cascade left a referencing row';
    END IF;
END
$$;

CREATE TABLE builtin_ops_seg (value seg);
INSERT INTO builtin_ops_seg VALUES ('1..3'), ('5..7');
DO $$
BEGIN
    IF (SELECT count(*) FROM builtin_ops_seg WHERE value @> '2'::seg) <> 1
       OR (SELECT count(*) FROM builtin_ops_seg WHERE value && '3..5'::seg) <> 2 THEN
        RAISE EXCEPTION 'seg containment or overlap returned unexpected results';
    END IF;
END
$$;

DO $check$
BEGIN
    IF (SELECT a FROM crosstab(
            $$SELECT 'row1'::text, 'a'::text, 10 UNION ALL
              SELECT 'row1', 'b', 20 ORDER BY 1, 2$$,
            $$SELECT unnest(ARRAY['a', 'b'])$$
        ) AS result(row_name text, a integer, b integer)) <> 10
       OR (SELECT b FROM crosstab(
            $$SELECT 'row1'::text, 'a'::text, 10 UNION ALL
              SELECT 'row1', 'b', 20 ORDER BY 1, 2$$,
            $$SELECT unnest(ARRAY['a', 'b'])$$
        ) AS result(row_name text, a integer, b integer)) <> 20 THEN
        RAISE EXCEPTION 'tablefunc crosstab returned unexpected values';
    END IF;
END
$check$;

CREATE TABLE builtin_ops_system_rows (value integer);
INSERT INTO builtin_ops_system_rows SELECT generate_series(1, 20);
DO $$
BEGIN
    IF (SELECT count(*) FROM builtin_ops_system_rows TABLESAMPLE SYSTEM_ROWS (4)) <> 4 THEN
        RAISE EXCEPTION 'tsm_system_rows did not return the requested row count';
    END IF;
END
$$;

CREATE TABLE builtin_ops_system_time (value integer);
INSERT INTO builtin_ops_system_time SELECT generate_series(1, 20);
DO $$
BEGIN
    IF (SELECT count(*) FROM builtin_ops_system_time TABLESAMPLE SYSTEM_TIME (0)) <> 0 THEN
        RAISE EXCEPTION 'tsm_system_time returned rows for a zero-millisecond sample';
    END IF;
END
$$;

DO $$
BEGIN
    IF unaccent('Hôtel') IS DISTINCT FROM 'Hotel' THEN
        RAISE EXCEPTION 'unaccent returned an unexpected normalised value';
    END IF;
END
$$;

DO $$
DECLARE
    generated uuid;
BEGIN
    generated := uuid_generate_v4();
    IF generated IS NULL OR substring(generated::text FROM 15 FOR 1) <> '4' THEN
        RAISE EXCEPTION 'uuid-ossp did not generate a version 4 UUID';
    END IF;
END
$$;

DO $$
BEGIN
    IF xpath_string('<root><value>expected</value></root>', '/root/value')
       IS DISTINCT FROM 'expected' THEN
        RAISE EXCEPTION 'xml2 xpath_string returned an unexpected value';
    END IF;
END
$$;
