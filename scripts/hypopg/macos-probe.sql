\set ON_ERROR_STOP on
SELECT current_setting('server_version_num')::integer >= 180000 AS postgres_18;
DO $$ BEGIN
  IF current_setting('server_version_num')::integer < 180000 THEN
    RAISE EXCEPTION 'PostgreSQL 18 or newer is required';
  END IF;
END $$;
CREATE EXTENSION hypopg;
CREATE TABLE hypo_probe AS SELECT id, repeat('x', 80) AS payload FROM generate_series(1, 100000) AS id;
ANALYZE hypo_probe;
SET enable_seqscan = off;
SELECT indexrelid > 0 AS hypothetical_index_created
FROM hypopg_create_index('CREATE INDEX ON hypo_probe (id)');
DO $$
BEGIN
  IF (SELECT count(*) FROM hypopg_list_indexes
      WHERE schema_name = 'public' AND table_name = 'hypo_probe' AND am_name = 'btree') <> 1 THEN
    RAISE EXCEPTION 'expected one hypothetical btree index on hypo_probe';
  END IF;
END
$$;
SELECT indexrelid, indexname FROM hypopg_list_indexes
WHERE schema_name = 'public' AND table_name = 'hypo_probe';
EXPLAIN SELECT payload FROM hypo_probe WHERE id = 4242;
SELECT hypopg_reset();
SELECT count(*) AS remaining_hypothetical_indexes FROM hypopg_list_indexes;
