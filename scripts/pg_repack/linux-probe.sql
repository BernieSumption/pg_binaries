\set ON_ERROR_STOP on
CREATE EXTENSION pg_repack;
CREATE TABLE repack_probe (id integer PRIMARY KEY, value text);
INSERT INTO repack_probe SELECT n, repeat('x', 200) FROM generate_series(1, 2000) AS n;
DELETE FROM repack_probe WHERE id % 2 = 0;
VACUUM repack_probe;
SELECT extname, extversion FROM pg_extension WHERE extname = 'pg_repack';
