\set ON_ERROR_STOP on
SELECT current_setting('server_version') AS postgres_version;
SELECT name, default_version FROM pg_available_extensions
WHERE name IN ('postgis','postgis_raster','postgis_topology','postgis_sfcgal',
               'postgis_tiger_geocoder','address_standardizer','address_standardizer_data_us')
ORDER BY name;
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_raster;
CREATE EXTENSION postgis_topology;
CREATE EXTENSION postgis_sfcgal;
CREATE EXTENSION address_standardizer;
CREATE EXTENSION address_standardizer_data_us;
CREATE EXTENSION fuzzystrmatch;
CREATE EXTENSION postgis_tiger_geocoder;
SELECT postgis_full_version();
SELECT ST_AsText(ST_Transform(ST_SetSRID(ST_MakePoint(-0.1278,51.5074),4326),3857));
DO $$ BEGIN
  IF NOT (ST_X(ST_Transform(ST_SetSRID(ST_Point(1,0),4326),3857)) BETWEEN 111319 AND 111320)
     OR abs(ST_Y(ST_Transform(ST_SetSRID(ST_Point(1,0),4326),3857))) > 0.000001 THEN
    RAISE EXCEPTION 'EPSG:4326 to EPSG:3857 transform returned wrong coordinates';
  END IF;
END $$;
SELECT ST_Area(ST_Intersection(ST_Buffer(ST_Point(0,0),2), ST_Buffer(ST_Point(1,0),2))) > 0 AS geos_works;
SELECT ST_Value(ST_AsRaster(ST_SetSRID(ST_Point(0,0),4326), 4, 4, '8BUI', 7),1,1,1);
SELECT topology.CreateTopology('pilot_topology',4326);
SELECT ST_AsText(CG_3DIntersection('LINESTRING Z (0 0 0, 2 2 2)'::geometry,
                                  'LINESTRING Z (0 2 2, 2 0 0)'::geometry));
SELECT (stdaddr).city FROM (SELECT standardize_address('us_lex','us_gaz','us_rules',
                                                     '1600 Pennsylvania Ave NW',
                                                     'Washington, DC 20500') AS stdaddr) AS s;
SELECT na.address, na.streetname FROM normalize_address('1 Devonshire Place, Boston, MA 02109') AS na;
-- The extension installs geocoder code but no Census TIGER address corpus.
SELECT count(*) FROM tiger.state;
