\set ON_ERROR_STOP on
CREATE EXTENSION collection;

DO $$
DECLARE
    c collection;
    result_count integer;
BEGIN
    c['beta'] := 'two';
    c['alpha'] := 'one';
    IF count(c) <> 2 OR NOT exist(c, 'alpha') OR find(c, 'beta') <> 'two' THEN
        RAISE EXCEPTION 'text-key collection lookup/count failed';
    END IF;
    SELECT count(*) INTO result_count FROM to_table(c) AS item(key, value);
    IF result_count <> 2 THEN
        RAISE EXCEPTION 'text-key collection to_table failed';
    END IF;

    CREATE TABLE public.collection_persist_probe (value collection NOT NULL);
    INSERT INTO collection_persist_probe VALUES (c);
END;
$$;

SELECT 'collection probe passed' AS outcome;
