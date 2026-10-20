# PostGIS Windows core ABI trial

Created 2026-10-20 to determine whether unmodified PostGIS 3.6.4 built through the upstream MSYS2 clang64 path can load into this repository's checked MSVC PostgreSQL 18.6 Windows x86-64 core.

The manual `postgis-pilot.yml` workflow downloads the pinned core artifact, builds the pinned PostGIS 3.6.4 source archive, installs only the `postgis` extension into an extracted core, then initializes a cluster and runs `CREATE EXTENSION postgis` plus `postgis_full_version()`.

The trial is answered when that SQL probe passes or when the first build/load blocker shows that this route needs substantial compiler or source changes. It does not establish runtime dependency closure or support for raster, SFCGAL, or topology.
