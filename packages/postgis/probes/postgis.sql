DO $$
BEGIN
  IF abs(ST_X(ST_Transform(ST_SetSRID(ST_Point(1, 0), 4326), 3857)) - 111319.49) > 1 THEN
    RAISE EXCEPTION 'PostGIS coordinate transform failed';
  END IF;
  IF NOT ST_Intersects(ST_Buffer(ST_Point(0, 0), 2), ST_Buffer(ST_Point(1, 0), 2)) THEN
    RAISE EXCEPTION 'PostGIS GEOS operation failed';
  END IF;
END $$;
