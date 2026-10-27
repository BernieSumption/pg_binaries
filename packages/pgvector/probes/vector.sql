DO $$
DECLARE
    distance double precision;
BEGIN
    distance := '[1,2,3]'::vector <-> '[1,1,1]'::vector;
    IF distance IS NULL OR abs(distance - sqrt(5.0)) >= 1e-12 THEN
        RAISE EXCEPTION 'vector distance was not sqrt(5)';
    END IF;
END
$$;
