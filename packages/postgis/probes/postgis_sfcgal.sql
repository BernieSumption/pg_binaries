DO $$
BEGIN
  IF postgis_sfcgal_version() IS NULL THEN
    RAISE EXCEPTION 'PostGIS SFCGAL library did not load';
  END IF;
  IF ST_IsEmpty(CG_3DIntersection('LINESTRING Z (0 0 0, 2 2 2)'::geometry,
                                  'LINESTRING Z (0 2 2, 2 0 0)'::geometry)) THEN
    RAISE EXCEPTION 'PostGIS SFCGAL intersection failed';
  END IF;
END $$;
