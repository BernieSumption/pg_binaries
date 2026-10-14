# Resource and dataset sizes in the PostGIS family

Research checked on 14 October 2026. Packaging recommendations below remain for review.

## Finding

TIGER is the clearest example of a large, external, application-populated
dataset, but it is not the only substantial geospatial data collection. PROJ
distributes optional coordinate-transformation grids separately from its
required runtime database. The PROJ CDN reports 806 MB of content. This describes the full
collection, not the download size of a required baseline. [PROJ CDN](https://cdn.proj.org/)

Those grids are not all equivalent to TIGER data. PROJ grids can be required
to perform a requested coordinate transformation accurately. PostGIS says
`ST_Transform` may error when a referenced grid is absent. PROJ can retrieve
needed grids from its CDN when networking is enabled, but network access is
disabled by default; relying on it conflicts with this project's offline
artifact tests. Thus retain `proj.db` and the ordinary PROJ configuration as
runtime resources, and treat optional grids as operation-specific resources:
bundle and verify those needed for advertised transformations, or state the
tested limits. A blanket “no grids” rule is unsafe. [PROJ resource files](https://proj.org/en/stable/resource_files.html),
[PROJ network capabilities](https://proj.org/en/stable/usage/network.html),
[PostGIS `ST_Transform`](https://postgis.net/docs/manual-dev/en/ST_Transform.html)

This matters even when the SQL only defines a schema object. For example, a
`CHECK (ST_X(ST_Transform(geom, 26910)) > 0)`, an expression index on
`ST_Transform(geom, 26910)`, or a materialized view selecting that expression
can execute the transform while applying or populating DDL. A schema parser
cannot infer that every transform will use a grid, but it also cannot safely
assume all DDL is independent of grids. This is an inference from PostGIS's
documented runtime behavior and PostgreSQL's expression-bearing schema
objects.

Other bundled geospatial defaults are small by comparison. GDAL's official
support-data RFC describes its then-current data directory as roughly 1.8 MB
uncompressed, mostly coordinate-system dictionaries, plus S-57 dictionaries,
seed files and logos. This is an older published figure, so it establishes
order of magnitude rather than a current exact package size. GDAL's ordinary
support files belong with the runtime; user raster/vector files, imagery,
basemaps and other project corpora are input data and should stay external.
GEOS does not have a comparable required geography corpus. [GDAL RFC 27](https://gdal.org/en/stable/development/rfc/rfc27_supportdata.html)

TIGER is distinctly different: its Census geography is downloaded/imported
into database tables for geocoding, and the PostGIS loader generates scripts
for selecting and loading geographic areas. It is not needed to create the
geocoder extension or use its basic normalization functions. The US address
standardizer's default lexicon, gazetteer and rules are instead part of that
extension's purpose and should be retained. No published current byte count
was found for those defaults, so do not describe them as large without
measuring the release being packaged. [PostGIS Extras](https://postgis.net/docs/Extras.html),
[TIGER loader](https://postgis.net/docs/Loader_Generate_Nation_Script.html)

## Packaging implication

Keep schema/install SQL and extension defaults, PROJ's required database and
GDAL's ordinary support files. Exclude TIGER Census imports and user imagery,
vector or raster corpora. Do not exclude every grid as “application data”:
record which transformations are tested offline and keep their required grid
resources available after relocation. Size claims should be measured per
selected release and archive; published figures above describe upstream
collections, not proposed bundle totals.
