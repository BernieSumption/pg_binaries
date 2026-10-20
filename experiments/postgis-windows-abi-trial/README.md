# PostGIS Windows same-toolchain feasibility trial

Created 2026-10-20 to test whether PostgreSQL 18.6 and unmodified PostGIS 3.6.4 can build and run together in the upstream MSYS2 clang64 environment on a Windows x86-64 runner.

The manual `postgis-pilot.yml` workflow builds the PostgreSQL 18.6 and PostGIS 3.6.4 upstream source archives with the same clang64 toolchain. It installs the `postgis` extension, initializes a cluster, then runs `CREATE EXTENSION postgis` and `postgis_full_version()`.

The trial is answered when that SQL probe passes or when the first build/load blocker shows that this route needs substantial compiler or source changes. The trial disables optional raster, SFCGAL, tiger geocoder and topology components. It does not establish runtime dependency closure or support for those components.
