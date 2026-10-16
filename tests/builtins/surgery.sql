CREATE EXTENSION pg_surgery;
CREATE TABLE surgery_probe (value integer);
INSERT INTO surgery_probe VALUES (42);
SELECT ctid::text AS target_tid FROM surgery_probe \gset
SELECT heap_force_kill('surgery_probe'::regclass, ARRAY[:'target_tid'::tid]);
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM surgery_probe) THEN
        RAISE EXCEPTION 'pg_surgery did not hide the killed tuple';
    END IF;
END
$$;
