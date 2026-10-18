\set ON_ERROR_STOP on
SELECT current_setting('server_version') AS postgres_version;
CREATE EXTENSION address_standardizer;
CREATE EXTENSION address_standardizer_data_us;

DO $$
DECLARE
    parsed record;
    standardized record;
BEGIN
    SELECT * INTO parsed
      FROM parse_address('385 Landgrove Rd  Landgrove VT 05148');
    IF parsed.num <> '385' OR parsed.city <> 'Landgrove'
       OR parsed.state <> 'VT' OR parsed.zip <> '05148' THEN
        RAISE EXCEPTION 'unexpected parse_address result: %', row_to_json(parsed);
    END IF;

    SELECT * INTO standardized
      FROM standardize_address(
        'us_lex', 'us_gaz', 'us_rules',
        'One Devonshire Place, PH 301, Boston, MA 02109');
    IF standardized.name <> 'DEVONSHIRE'
       OR standardized.suftype <> 'PLACE'
       OR standardized.city <> 'BOSTON' THEN
        RAISE EXCEPTION 'unexpected standardize_address result: %', row_to_json(standardized);
    END IF;
END
$$;

SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('address_standardizer', 'address_standardizer_data_us')
ORDER BY extname;
