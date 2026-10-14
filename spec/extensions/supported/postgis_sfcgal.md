# postgis_sfcgal

`postgis_sfcgal` wraps the **SFCGAL** geometry library. Its SQL extension version
follows [PostGIS](postgis.md); record the SFCGAL library version separately.
PostGIS's source, licence and expected PostgreSQL ranges apply, including the
3.6.1–3.6.4 candidates. Bundled SFCGAL, CGAL and numeric/runtime libraries need
their own licence inventory.

## Dependencies and resources

Require `postgis`, SFCGAL and its C++ and numeric runtime dependencies. No preload,
external service or bulk dataset is expected. User meshes and map corpora are
excluded. Resolve library requirements from the selected source release; the
[moving installation guide](https://postgis.net/docs/postgis_installation.html)
may describe a different revision.

## Schema transitions

SFCGAL functions acquired `CG_` names in PostGIS 3.5 while old `ST_` aliases
were deprecated. Check exact signatures and aliases against the
[release notes](https://github.com/postgis/postgis/blob/3.6.4/NEWS).
New SQL functions can also require newer SFCGAL libraries, making successful
extension creation insufficient evidence of feature coverage.

## Evidence and remaining tests

The Linux pilot passed creation and a 3D intersection using SFCGAL 1.4.1.
The tagged PostGIS 3.6 notes require SFCGAL 2.2+ for full coverage, exceeding
the moving manual's 2.1+ statement cited in the pilot. See
[pilot evidence and common gaps](../README.md#pilot-evidence).

Resolve requirements against the exact source, build suitable dependencies and
exercise gated APIs as well as version-specific aliases and signatures.
