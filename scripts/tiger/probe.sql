\set ON_ERROR_STOP on
CREATE EXTENSION postgis;
CREATE EXTENSION fuzzystrmatch;
CREATE EXTENSION postgis_tiger_geocoder;
SET search_path = "$user", public, tiger;
DO $$
DECLARE
  result norm_addy;
BEGIN
  SELECT * INTO result FROM normalize_address('1 Devonshire Place, Boston, MA 02109');
  IF result.address::text <> '1' OR result.streetname <> 'Devonshire'
     OR result.streettypeabbrev <> 'Pl' OR result.zip <> '02109' THEN
    RAISE EXCEPTION 'Unexpected TIGER address normalization: %', result;
  END IF;
  IF (SELECT count(*) FROM pg_extension WHERE extname IN (
      'postgis', 'fuzzystrmatch', 'postgis_tiger_geocoder')) <> 3 THEN
    RAISE EXCEPTION 'Missing TIGER extension dependencies';
  END IF;
END $$;
