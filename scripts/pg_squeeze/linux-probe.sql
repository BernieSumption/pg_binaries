\set ON_ERROR_STOP on
CREATE EXTENSION pg_squeeze;
CREATE TABLE squeeze_probe (id integer PRIMARY KEY, value text);
INSERT INTO squeeze_probe SELECT n, repeat('x', 200) FROM generate_series(1, 4000) AS n;
DELETE FROM squeeze_probe WHERE id % 2 = 0;
SELECT squeeze.squeeze_table('public', 'squeeze_probe');
