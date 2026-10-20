# PostGIS Windows same-toolchain feasibility trial

Created 2026-10-20 to test whether PostgreSQL 18.6 and unmodified PostGIS 3.6.4 can build and run together in the upstream MSYS2 MINGW64 environment on a Windows x86-64 runner.

The manual `postgis-pilot.yml` workflow builds the PostgreSQL 18.6 and PostGIS 3.6.4 upstream source archives with the same MINGW64 toolchain. It installs the `postgis` extension, initializes a cluster, then runs `CREATE EXTENSION postgis` and `postgis_full_version()`.

Run 39492045563 passed the same-toolchain SQL probe. That establishes an upstream build path, but the selected Windows PostgreSQL core was built with MSVC. The next trial downloads that exact core archive and attempts a GCC PostGIS build and extension load against it. It ends when the selected-core SQL probe passes or a specific compiler, linker or loader incompatibility is established.

Both trials disable optional raster, SFCGAL, tiger geocoder and topology components. They do not establish runtime dependency closure or support for those components. Remove this experiment after its findings have been incorporated into the selected Windows publication route or a human review decision.
