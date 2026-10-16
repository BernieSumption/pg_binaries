CREATE EXTENSION dblink;
SELECT dblink_connect('pilot_dblink', :'loopback_conninfo');
DO $$
DECLARE
    result integer;
BEGIN
    SELECT value INTO result FROM dblink('pilot_dblink', 'SELECT 42') AS remote(value integer);
    IF result IS DISTINCT FROM 42 THEN
        RAISE EXCEPTION 'dblink did not return the remote query result';
    END IF;
    PERFORM dblink_disconnect('pilot_dblink');
END
$$;

CREATE EXTENSION pgrowlocks;
CREATE TABLE builtin_rowlocks (value integer);
INSERT INTO builtin_rowlocks VALUES (31);
SELECT dblink_connect('pilot_lock', :'loopback_conninfo');
DO $$
DECLARE
    locked_value integer;
BEGIN
    PERFORM dblink_exec('pilot_lock', 'BEGIN');
    SELECT value INTO locked_value
    FROM dblink('pilot_lock', 'SELECT value FROM builtin_rowlocks FOR UPDATE')
         AS remote(value integer);
    IF locked_value IS DISTINCT FROM 31
       OR NOT EXISTS (
           SELECT 1 FROM pgrowlocks('builtin_rowlocks')
           WHERE locked_row = '(0,1)'::tid
       ) THEN
        RAISE EXCEPTION 'pgrowlocks did not report a concurrent row lock';
    END IF;
    PERFORM dblink_exec('pilot_lock', 'COMMIT');
    PERFORM dblink_disconnect('pilot_lock');
END
$$;

CREATE EXTENSION postgres_fdw;
CREATE TABLE builtin_fdw_source (value integer);
INSERT INTO builtin_fdw_source VALUES (73);
CREATE SERVER builtin_fdw_server FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host :'loopback_host', port :'loopback_port', dbname 'postgres', sslmode 'disable');
CREATE USER MAPPING FOR CURRENT_USER SERVER builtin_fdw_server;
CREATE FOREIGN TABLE builtin_fdw_remote (value integer) SERVER builtin_fdw_server
    OPTIONS (table_name 'builtin_fdw_source');
DO $$
BEGIN
    IF (SELECT value FROM builtin_fdw_remote) IS DISTINCT FROM 73 THEN
        RAISE EXCEPTION 'postgres_fdw did not read the packaged server';
    END IF;
END
$$;
