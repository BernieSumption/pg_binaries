DO $$
DECLARE
    standardized record;
BEGIN
    SELECT * INTO standardized
      FROM standardize_address(
        'us_lex', 'us_gaz', 'us_rules',
        'One Devonshire Place, PH 301, Boston, MA 02109');
    IF standardized.name IS DISTINCT FROM 'DEVONSHIRE'
       OR standardized.suftype IS DISTINCT FROM 'PLACE'
       OR standardized.city IS DISTINCT FROM 'BOSTON' THEN
        RAISE EXCEPTION 'unexpected standardize_address result: %', row_to_json(standardized);
    END IF;
END
$$;
