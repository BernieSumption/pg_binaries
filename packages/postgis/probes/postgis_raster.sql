DO $$
DECLARE
  image raster;
BEGIN
  image := ST_AsRaster(ST_SetSRID(ST_Point(0, 0), 4326), 4, 4, '8BUI', 7);
  IF ST_Value(image, 1, 1, 1) <> 7 THEN
    RAISE EXCEPTION 'PostGIS raster value failed';
  END IF;
  PERFORM set_config('postgis.gdal_enabled_drivers', 'GTiff', true);
  IF ST_Width(ST_FromGDALRaster(ST_AsGDALRaster(image, 'GTiff'))) <> 4 THEN
    RAISE EXCEPTION 'PostGIS GDAL raster round trip failed';
  END IF;
END $$;
