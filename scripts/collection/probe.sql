\set ON_ERROR_STOP on
CREATE EXTENSION collection;

DO $$
DECLARE
    c collection;
    i icollection('text');
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

    i[1] := 'first';
    i[1000000] := 'millionth';
    IF count(i) <> 2 OR NOT exist(i, 1) OR exist(i, 500) OR find(i, 1000000) <> 'millionth' THEN
        RAISE EXCEPTION 'integer-key collection sparse lookup/count failed';
    END IF;
    SELECT count(*) INTO result_count FROM to_table(i) AS item(key, value);
    IF result_count <> 2 THEN
        RAISE EXCEPTION 'integer-key collection to_table failed';
    END IF;

    CREATE TABLE public.collection_persist_probe (value collection NOT NULL, integer_value icollection('text') NOT NULL);
    INSERT INTO collection_persist_probe VALUES (c, i);

    IF value_type(i) <> 'text'::regtype THEN
        RAISE EXCEPTION 'icollection value type metadata failed';
    END IF;
END;
$$;

SELECT 'collection probe passed' AS outcome;
