\set ON_ERROR_STOP on

-- Run after the source-selected built-in extensions have been created.
-- Each assertion raises an error so psql exits non-zero on a bad result.
DO $checks$
BEGIN
  PERFORM bt_index_check('pg_catalog.pg_class_oid_index'::regclass, true);
END
$checks$;
CREATE TEMP TABLE builtin_bloom_a_l (id integer, value text);
INSERT INTO builtin_bloom_a_l VALUES (1, 'alpha'), (2, 'beta');
CREATE INDEX builtin_bloom_a_l_idx ON builtin_bloom_a_l USING bloom (id, value);
DO $checks$
BEGIN
  IF (SELECT count(*) FROM builtin_bloom_a_l WHERE id = 2 AND value = 'beta') <> 1 THEN
    RAISE EXCEPTION 'bloom index probe returned the wrong row count';
  END IF;
END
$checks$;

CREATE INDEX builtin_btree_gin_a_l_idx ON builtin_bloom_a_l USING gin (id);
CREATE INDEX builtin_btree_gist_a_l_idx ON builtin_bloom_a_l USING gist (id);
DO $checks$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_index WHERE indexrelid = 'builtin_btree_gin_a_l_idx'::regclass)
     OR NOT EXISTS (SELECT FROM pg_index WHERE indexrelid = 'builtin_btree_gist_a_l_idx'::regclass) THEN
    RAISE EXCEPTION 'btree_gin or btree_gist index was not registered';
  END IF;
END
$checks$;

DO $checks$
BEGIN
  IF 'Hello'::citext = 'hello'::citext IS NOT TRUE THEN
    RAISE EXCEPTION 'citext comparison is case-sensitive';
  END IF;
  IF cube_distance(cube(ARRAY[0.0, 0.0]), cube(ARRAY[3.0, 4.0])) <> 5 THEN
    RAISE EXCEPTION 'cube distance did not return 5';
  END IF;
END
$checks$;

DO $checks$
BEGIN
  IF 'a=>b'::hstore -> 'a' <> 'b' THEN
    RAISE EXCEPTION 'hstore lookup returned the wrong value';
  END IF;
  IF 'Top.Child'::ltree ~ 'Top.*'::lquery IS NOT TRUE THEN
    RAISE EXCEPTION 'ltree pattern match failed';
  END IF;
END
$checks$;

DO $checks$
BEGIN
  IF levenshtein('kitten', 'sitting') <> 3 THEN
    RAISE EXCEPTION 'levenshtein returned the wrong distance';
  END IF;
  IF (SELECT value FROM dblink('dbname=postgres', 'SELECT 42') AS remote(value integer))
     IS DISTINCT FROM 42 THEN
    RAISE EXCEPTION 'dblink did not return the loopback query result';
  END IF;
END
$checks$;

CREATE SEQUENCE builtin_ops_autoinc_seq START WITH 100;
CREATE TEMP TABLE builtin_ops_autoinc (id integer);
CREATE TRIGGER builtin_ops_autoinc_trigger BEFORE INSERT ON builtin_ops_autoinc
  FOR EACH ROW EXECUTE FUNCTION autoinc(id, builtin_ops_autoinc_seq);
INSERT INTO builtin_ops_autoinc VALUES (NULL), (NULL);

CREATE TEMP TABLE builtin_ops_username (changed_by text);
CREATE TRIGGER builtin_ops_username_trigger BEFORE INSERT ON builtin_ops_username
  FOR EACH ROW EXECUTE FUNCTION insert_username(changed_by);
INSERT INTO builtin_ops_username VALUES (NULL);

CREATE TEMP TABLE builtin_ops_intarray (values integer[]);
INSERT INTO builtin_ops_intarray VALUES (ARRAY[1, 2, 3]);
CREATE TEMP TABLE builtin_ops_isn (value isbn);
INSERT INTO builtin_ops_isn VALUES ('0-393-04002-X');

CREATE TEMP TABLE builtin_ops_lo (object_id lo);
INSERT INTO builtin_ops_lo VALUES (lo_from_bytea(0, decode('50475351', 'hex')));

CREATE TEXT SEARCH DICTIONARY builtin_ops_xsyn (
  TEMPLATE = xsyn_template, RULES = 'xsyn_sample');
CREATE SERVER builtin_ops_file_server FOREIGN DATA WRAPPER file_fdw;
CREATE FOREIGN TABLE builtin_ops_file_probe (id integer, value text)
  SERVER builtin_ops_file_server OPTIONS (filename :'fixture_path', format 'csv');

DO $checks$
BEGIN
  IF (SELECT array_agg(id ORDER BY id) FROM builtin_ops_autoinc) IS DISTINCT FROM ARRAY[100, 101] THEN
    RAISE EXCEPTION 'autoinc did not assign sequence values';
  END IF;
  IF (SELECT changed_by FROM builtin_ops_username) IS DISTINCT FROM current_user THEN
    RAISE EXCEPTION 'insert_username did not record the current user';
  END IF;
  IF ts_lexize('intdict', '123') IS DISTINCT FROM ARRAY['123']::text[] THEN
    RAISE EXCEPTION 'dict_int did not lexise an integer';
  END IF;
  IF ts_lexize('builtin_ops_xsyn', 'supernova')
     IS DISTINCT FROM ARRAY['supernova', 'sn', 'sne', '1987a']::text[] THEN
    RAISE EXCEPTION 'dict_xsyn did not read its packaged rule file';
  END IF;
  IF (SELECT id FROM builtin_ops_file_probe) IS DISTINCT FROM 42
     OR (SELECT value FROM builtin_ops_file_probe) IS DISTINCT FROM 'hello' THEN
    RAISE EXCEPTION 'file_fdw did not read the CSV fixture';
  END IF;
  IF earth_distance(ll_to_earth(0, 0), ll_to_earth(0, 0)) IS DISTINCT FROM 0 THEN
    RAISE EXCEPTION 'earthdistance returned a nonzero distance for equal points';
  END IF;
  IF (SELECT int_array_aggregate(value ORDER BY value)
      FROM (VALUES (3), (1), (2)) AS input(value)) IS DISTINCT FROM ARRAY[1, 2, 3] THEN
    RAISE EXCEPTION 'intagg returned the wrong array';
  END IF;
  IF (SELECT values @> ARRAY[2, 3] FROM builtin_ops_intarray) IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'intarray containment failed';
  END IF;
  IF (SELECT value::text FROM builtin_ops_isn) IS DISTINCT FROM '0-393-04002-X' THEN
    RAISE EXCEPTION 'isn did not preserve the ISBN';
  END IF;
  IF lo_get((SELECT object_id FROM builtin_ops_lo)) IS DISTINCT FROM decode('50475351', 'hex') THEN
    RAISE EXCEPTION 'lo did not read the stored bytes';
  END IF;
END
$checks$;

