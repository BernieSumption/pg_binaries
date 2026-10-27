DO $$
DECLARE
    parsed record;
BEGIN
    SELECT * INTO parsed
      FROM parse_address('385 Landgrove Rd  Landgrove VT 05148');
    IF parsed.num IS DISTINCT FROM '385' OR parsed.city IS DISTINCT FROM 'Landgrove'
       OR parsed.state IS DISTINCT FROM 'VT' OR parsed.zip IS DISTINCT FROM '05148' THEN
        RAISE EXCEPTION 'unexpected parse_address result: %', row_to_json(parsed);
    END IF;
END
$$;
