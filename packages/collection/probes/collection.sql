DO $$
DECLARE
  text_values collection;
  integer_values icollection('text');
  table_rows integer;
BEGIN
  text_values['beta'] := 'two';
  text_values['alpha'] := 'one';
  IF count(text_values) IS DISTINCT FROM 2 OR exist(text_values, 'alpha') IS DISTINCT FROM true
     OR exist(text_values, 'missing') IS DISTINCT FROM false
     OR find(text_values, 'beta') IS DISTINCT FROM 'two' THEN
    RAISE EXCEPTION 'text-key collection lookup/count failed';
  END IF;

  SELECT count(*) INTO table_rows FROM to_table(text_values) AS item(key, value);
  IF table_rows <> 2 THEN
    RAISE EXCEPTION 'text-key collection to_table failed';
  END IF;

  integer_values[1] := 'first';
  integer_values[1000000] := 'millionth';
  IF count(integer_values) IS DISTINCT FROM 2 OR exist(integer_values, 1) IS DISTINCT FROM true
     OR exist(integer_values, 500) IS DISTINCT FROM false
     OR find(integer_values, 1000000) IS DISTINCT FROM 'millionth' THEN
    RAISE EXCEPTION 'integer-key collection sparse lookup/count failed';
  END IF;

  SELECT count(*) INTO table_rows FROM to_table(integer_values) AS item(key, value);
  IF table_rows <> 2 OR value_type(integer_values) IS DISTINCT FROM 'text'::regtype THEN
    RAISE EXCEPTION 'integer-key collection table/type metadata failed';
  END IF;
END;
$$;
