CREATE EXTENSION adminpack;
DO $$
BEGIN
    IF pg_catalog.pg_file_write('builtin_adminpack_probe', 'probe', false) <> 5 THEN
        RAISE EXCEPTION 'adminpack file write failed';
    END IF;
    IF pg_catalog.pg_read_file('builtin_adminpack_probe') IS DISTINCT FROM 'probe' THEN
        RAISE EXCEPTION 'adminpack file read failed';
    END IF;
    IF pg_catalog.pg_file_rename('builtin_adminpack_probe', 'builtin_adminpack_renamed') IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'adminpack file rename failed';
    END IF;
    IF pg_catalog.pg_file_unlink('builtin_adminpack_renamed') IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'adminpack file unlink failed';
    END IF;
END
$$;

CREATE EXTENSION old_snapshot;
DO $$
BEGIN
    IF current_setting('old_snapshot_threshold')::integer <> -1
       OR EXISTS (SELECT 1 FROM pg_old_snapshot_time_mapping()) THEN
        RAISE EXCEPTION 'old_snapshot reported timestamp mapping with tracking disabled';
    END IF;
END
$$;
