\set ON_ERROR_STOP on
CREATE SCHEMA partman;
CREATE EXTENSION pg_partman SCHEMA partman;
CREATE TABLE public.partman_probe (id integer NOT NULL, value text) PARTITION BY RANGE (id);
SELECT partman.create_partition('public.partman_probe', 'id', '10', p_type := 'range', p_start_partition := '1', p_jobmon := false);
DO $$
BEGIN
    IF (SELECT extversion FROM pg_extension WHERE extname = 'pg_partman') <> '5.5.0' THEN
        RAISE EXCEPTION 'unexpected pg_partman extension version';
    END IF;
    IF (SELECT count(*) FROM pg_inherits WHERE inhparent = 'public.partman_probe'::regclass) < 1 THEN
        RAISE EXCEPTION 'pg_partman did not create child partitions';
    END IF;
END
$$;
SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_partman';
