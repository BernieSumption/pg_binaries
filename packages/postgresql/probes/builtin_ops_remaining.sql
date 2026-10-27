\set ON_ERROR_STOP on

-- Run after the source-selected built-in extensions have been created.
-- The caller should check psql output for the tcn notification payload.
CREATE TABLE builtin_logicalinspect_probe (value integer PRIMARY KEY);
CREATE PUBLICATION builtin_logicalinspect_pub FOR TABLE builtin_logicalinspect_probe;
SELECT * FROM pg_create_logical_replication_slot('builtin_logicalinspect_slot', 'pgoutput');
INSERT INTO builtin_logicalinspect_probe VALUES (1);
CHECKPOINT;
INSERT INTO builtin_logicalinspect_probe VALUES (2);
SELECT count(*) FROM pg_logical_slot_get_binary_changes(
    'builtin_logicalinspect_slot', NULL, NULL,
    'proto_version', '1', 'publication_names', 'builtin_logicalinspect_pub'
);
DO $checks$
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
$checks$;
SELECT pg_drop_replication_slot('builtin_logicalinspect_slot');
DROP PUBLICATION builtin_logicalinspect_pub;
DROP TABLE builtin_logicalinspect_probe;

CREATE TABLE builtin_tcn_remaining (id integer PRIMARY KEY);
CREATE TRIGGER builtin_tcn_remaining_change
    AFTER INSERT ON builtin_tcn_remaining
    FOR EACH ROW EXECUTE FUNCTION triggered_change_notification();
LISTEN tcn;
INSERT INTO builtin_tcn_remaining VALUES (91);
SELECT 'TCN_PROBE_INSERTED; expect notification payload "builtin_tcn_remaining",I,"id"=''91''' AS tcn_probe_marker;
