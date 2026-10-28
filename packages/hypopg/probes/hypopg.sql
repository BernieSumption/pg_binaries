CREATE TABLE hypo_probe AS
SELECT id, repeat('x', 80) AS payload
FROM generate_series(1, 100000) AS id;
ANALYSE hypo_probe;

SET enable_seqscan = off;
DO $$
DECLARE
  created_index oid;
  plan json;
BEGIN
  SELECT indexrelid INTO created_index
  FROM hypopg_create_index('CREATE INDEX ON hypo_probe (id)');

  IF created_index IS NULL OR created_index = 0 THEN
    RAISE EXCEPTION 'HypoPG did not create a hypothetical index';
  END IF;

  IF (SELECT count(*) FROM hypopg_list_indexes
      WHERE indexrelid = created_index AND table_name = 'hypo_probe' AND am_name = 'btree') <> 1 THEN
    RAISE EXCEPTION 'expected one hypothetical btree index on hypo_probe';
  END IF;

  EXECUTE 'EXPLAIN (FORMAT JSON) SELECT payload FROM hypo_probe WHERE id = 4242' INTO plan;
  IF plan::text NOT LIKE '%Index Scan%' THEN
    RAISE EXCEPTION 'planner did not use the hypothetical index: %', plan;
  END IF;
END
$$;

DO $$
BEGIN
  PERFORM hypopg_reset();
  IF (SELECT count(*) FROM hypopg_list_indexes) <> 0 THEN
    RAISE EXCEPTION 'hypopg_reset left hypothetical indexes registered';
  END IF;
END
$$;

RESET enable_seqscan;
DROP TABLE hypo_probe;
