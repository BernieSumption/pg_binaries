CREATE EXTENSION dblink;
DO $$
DECLARE
    result integer;
BEGIN
    IF dblink_connect('pilot_dblink', 'host=/tmp/pgsocket port=55431 dbname=postgres') <> 'OK' THEN
        RAISE EXCEPTION 'dblink could not connect to the packaged server';
    END IF;
    SELECT value INTO result FROM dblink('pilot_dblink', 'SELECT 42') AS remote(value integer);
    IF result IS DISTINCT FROM 42 THEN
        RAISE EXCEPTION 'dblink did not return the remote query result';
    END IF;
    PERFORM dblink_disconnect('pilot_dblink');
END
$$;

CREATE EXTENSION postgres_fdw;
CREATE TABLE builtin_fdw_source (value integer);
INSERT INTO builtin_fdw_source VALUES (73);
CREATE SERVER builtin_fdw_server FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host '/tmp/pgsocket', port '55431', dbname 'postgres');
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
