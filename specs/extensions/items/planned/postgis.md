# postgis

`postgis` supplies spatial types and functions. Its source distribution also
contains separately selectable SQL extensions. Discover releases through the
[official source links](https://postgis.net/development/source_code/), checking
each tag's `NEWS` and build files. PostGIS uses
[GPL-2.0-or-later](https://github.com/postgis/postgis/blob/3.6.4/postgis/lwgeom_functions_basic.c);
retain [COPYING](https://github.com/postgis/postgis/blob/3.6.4/COPYING) and
component/dependency notices.

## Versions and compatibility

The researched 3.6 candidates are 3.6.1–3.6.4; 3.6.0 predates the cutoff and
3.7 prereleases do not qualify. PostGIS 3.6's expected project range is PostgreSQL
15–18. Qualifying patches to older branches remain in scope and need their own
range research. Apply the [shared build and verification rules](../../extensions-policy.md).

Branch transitions can affect dependent views: 3.5 changes
`ST_AsGeoJSON(record, ...)` signatures and 3.6 changes TIN/polyhedral access
semantics. Use the [tagged release notes](https://github.com/postgis/postgis/blob/3.6.4/NEWS)
to identify fixtures for exact versions.

## Dependencies and resources

Core `postgis` requires no companion SQL extension or preload. Its native
libraries include GEOS, PROJ, libxml2 and JSON-C; feature-dependent libraries
such as protobuf-c must be recorded so optional builds do not silently lose
SQL functions. See the [installation requirements](https://postgis.net/docs/postgis_installation.html).

Bundle `spatial_ref_sys` installation content, PROJ's database and resources
required by advertised operations. User map corpora are excluded. Document and
test the transformation limits of any excluded optional grid collection.

## Evidence and remaining tests

The Linux pilot passed extension creation, a GEOS operation and a numerical
EPSG transformation after relocation. Its GEOS 3.10.2 does not cover all 3.6
features: the tagged notes require GEOS 3.14+ for full coverage. See
[pilot evidence and common gaps](../../extensions-notes.md#pilot-evidence).

Build the required dependency versions and test their gated SQL functions,
spatial column/index DDL and transformations after moving resource paths.

## Completion

Meet the [extension packaging and verification criteria](../../extensions-policy.md#e06--item-content-and-completion) for this item's inventory scope, including the tests above. Keep exact release/platform results in coverage records.
