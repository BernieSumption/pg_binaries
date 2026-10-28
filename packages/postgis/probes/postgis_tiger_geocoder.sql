DO $$
DECLARE
  parsed record;
BEGIN
  SELECT * INTO parsed FROM tiger.normalize_address('1 Devonshire Place, Boston, MA 02109');
  IF parsed.streetname <> 'Devonshire' THEN
    RAISE EXCEPTION 'TIGER address normalisation failed: %', parsed.streetname;
  END IF;
END $$;
