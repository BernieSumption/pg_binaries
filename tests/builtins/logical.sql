CREATE EXTENSION pg_logicalinspect;
CREATE TABLE builtin_logical_probe (value integer PRIMARY KEY);
CREATE PUBLICATION builtin_logical_pub FOR TABLE builtin_logical_probe;
SELECT * FROM pg_create_logical_replication_slot('builtin_logical_slot', 'pgoutput');
INSERT INTO builtin_logical_probe VALUES (1);
CHECKPOINT;
INSERT INTO builtin_logical_probe VALUES (2);
SELECT count(*) FROM pg_logical_slot_get_binary_changes(
    'builtin_logical_slot', NULL, NULL,
    'proto_version', '1', 'publication_names', 'builtin_logical_pub'
);
DO $$
DECLARE
    snapshot_version integer;
    snapshot_state text;
BEGIN
    SELECT meta.version, info.state
    INTO snapshot_version, snapshot_state
    FROM pg_ls_logicalsnapdir() AS snapshot
    CROSS JOIN LATERAL pg_get_logical_snapshot_meta(snapshot.name) AS meta
    CROSS JOIN LATERAL pg_get_logical_snapshot_info(snapshot.name) AS info
    LIMIT 1;
    IF snapshot_version IS NULL OR snapshot_version <= 0
       OR snapshot_state IS DISTINCT FROM 'consistent' THEN
        RAISE EXCEPTION 'pg_logicalinspect did not decode a serialized logical snapshot';
    END IF;
END
$$;
SELECT pg_drop_replication_slot('builtin_logical_slot');
