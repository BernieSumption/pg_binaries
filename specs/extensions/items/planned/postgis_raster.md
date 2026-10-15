# postgis_raster

`postgis_raster` supplies raster types and functions. It follows the
[PostGIS source versions, licence and expected PostgreSQL ranges](postgis.md),
including the 3.6.1–3.6.4 candidates. It has been a separate SQL extension since
PostGIS 3.0.

## Dependencies and resources

The extension requires `postgis`, GDAL and GDAL's libraries, driver resources
and runtime data. No preload is expected. The
[installation guide](https://postgis.net/docs/postgis_installation.html) identifies
GDAL requirements; the [raster reference](https://postgis.net/docs/RT_reference.html)
covers construction, format import/export and driver discovery.

Bundle the GDAL/PROJ resources required for advertised DDL and raster operations.
User imagery, terrain collections and import datasets are excluded. Record
available drivers and configuration in metadata: an in-memory pixel test cannot
establish file-format support.

## Schema transitions

PostGIS 3.5 replaces `ST_Clip` variants and 3.6 removes an unusable
`ST_ApproxQuantile` signature. Dependent views can rely on exact signatures;
use the [release notes](https://github.com/postgis/postgis/blob/3.6.4/NEWS)
to select migration fixtures.

## Evidence and remaining tests

The Linux pilot created the extension, read a raster pixel and started loader
executables after relocation. It did not establish GDAL driver coverage or
all features requiring newer GEOS. See [pilot evidence and common gaps](../../extensions-notes.md#pilot-evidence).

Add raster column/index DDL and file import/export tests for the advertised
drivers, confirm relocated data paths and measure GDAL's download contribution.

## Completion

Meet the [extension packaging and verification criteria](../../extensions-policy.md#e06--item-content-and-completion) for this item's inventory scope, including the tests above. Keep exact release/platform results in coverage records.
