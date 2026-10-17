\set ON_ERROR_STOP on
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_raster;
CREATE EXTENSION postgis_topology;
CREATE EXTENSION postgis_sfcgal;

CREATE TABLE route_35 (
  route_id integer PRIMARY KEY,
  shape geometry(LineString, 4326) NOT NULL,
  location geography(Point, 4326) NOT NULL
);
CREATE INDEX route_35_shape_idx ON route_35 USING gist (shape);
CREATE INDEX route_35_location_idx ON route_35 USING gist (location);
CREATE TABLE raster_35 (cell_id integer PRIMARY KEY, tile raster NOT NULL);
CREATE VIEW route_35_length AS
  SELECT route_id, ST_Length(shape::geography) AS metres FROM route_35;
CREATE FUNCTION overlap_35(a geometry, b geometry) RETURNS geometry
  LANGUAGE sql IMMUTABLE AS 'SELECT CG_3DIntersection(a, b)';
SELECT topology.CreateTopology('route_topology_35', 4326);

INSERT INTO route_35 VALUES
  (1, ST_GeomFromText('LINESTRING(0 0,1 0)', 4326), ST_Point(0, 0, 4326)::geography);
INSERT INTO raster_35 VALUES
  (1, ST_AsRaster(ST_SetSRID(ST_Point(0,0),4326), 4, 4, '8BUI', 9));
DO $$ BEGIN
  IF (SELECT count(*) FROM pg_indexes WHERE indexname IN ('route_35_shape_idx','route_35_location_idx')) <> 2
     OR (SELECT count(*) FROM route_35_length WHERE metres > 0) <> 1
     OR (SELECT ST_Value(tile, 1, 1, 1) FROM raster_35) <> 9
     OR (SELECT ST_AsText(overlap_35('LINESTRING Z (0 0 0,2 2 2)'::geometry,
                                     'LINESTRING Z (0 2 2,2 0 0)'::geometry)))
        <> 'POINT Z (1 1 1)'
     OR NOT EXISTS (SELECT 1 FROM topology.topology WHERE name = 'route_topology_35') THEN
    RAISE EXCEPTION 'PostGIS 3.5 DDL behaviour failed';
  END IF;
END $$;
SELECT 1 / (postgis_lib_version() = :'installed_version')::integer;
SELECT 1 / (count(*) = 4 AND bool_and(extversion = :'installed_version'))::integer
  FROM pg_extension
  WHERE extname IN ('postgis', 'postgis_raster', 'postgis_topology', 'postgis_sfcgal');
