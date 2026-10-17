\set ON_ERROR_STOP on
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_raster;
CREATE EXTENSION postgis_topology;
CREATE EXTENSION postgis_sfcgal;

CREATE TABLE parcel_34 (
  parcel_id integer PRIMARY KEY,
  outline geometry(Polygon, 4326) NOT NULL
);
CREATE INDEX parcel_34_outline_idx ON parcel_34 USING gist (outline);
CREATE TABLE elevation_34 (tile_id integer PRIMARY KEY, pixels raster NOT NULL);
CREATE VIEW parcel_34_area AS
  SELECT parcel_id, ST_Area(outline::geography) AS square_metres FROM parcel_34;
CREATE FUNCTION crossing_34(a geometry, b geometry) RETURNS geometry
  LANGUAGE sql IMMUTABLE AS 'SELECT ST_3DIntersection(a, b)';
SELECT topology.CreateTopology('parcel_topology_34', 4326);

INSERT INTO parcel_34 VALUES
  (1, ST_GeomFromText('POLYGON((0 0,1 0,1 1,0 1,0 0))', 4326));
INSERT INTO elevation_34 VALUES
  (1, ST_AsRaster(ST_SetSRID(ST_Point(0,0),4326), 4, 4, '8BUI', 7));
DO $$ BEGIN
  IF (SELECT count(*) FROM pg_indexes WHERE indexname = 'parcel_34_outline_idx') <> 1
     OR (SELECT count(*) FROM parcel_34_area WHERE square_metres > 0) <> 1
     OR (SELECT ST_Value(pixels, 1, 1, 1) FROM elevation_34) <> 7
     OR (SELECT ST_AsText(crossing_34('LINESTRING Z (0 0 0,2 2 2)'::geometry,
                                      'LINESTRING Z (0 2 2,2 0 0)'::geometry)))
        <> 'POINT Z (1 1 1)'
     OR NOT EXISTS (SELECT 1 FROM topology.topology WHERE name = 'parcel_topology_34') THEN
    RAISE EXCEPTION 'PostGIS 3.4 DDL behaviour failed';
  END IF;
END $$;
SELECT 1 / (postgis_lib_version() = :'installed_version')::integer;
SELECT 1 / (count(*) = 4 AND bool_and(extversion = :'installed_version'))::integer
  FROM pg_extension
  WHERE extname IN ('postgis', 'postgis_raster', 'postgis_topology', 'postgis_sfcgal');
