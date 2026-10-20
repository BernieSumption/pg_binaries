# PostGIS Windows cross-install trial

Created 2026-10-20 to test unmodified PostGIS 3.6.4 on the selected Windows PostgreSQL 18.6 archive. The manual `postgis-pilot.yml` workflow first builds PostgreSQL and PostGIS with the same MSYS2 MINGW64 toolchain. Run 39492045563 passed `CREATE EXTENSION postgis` and `postgis_full_version()` on that pair.

The selected Windows PostgreSQL core was built with MSVC. Runs 39495196354 through 39499432408 tried to build PostGIS directly against its PGXS files with GCC. The last run reached shared-library compilation, but the required MSVC-to-GCC build adapters became disproportionate. The previous adapter script remains in Git history.

The current `cross-install-probe.sh` follows the [upstream Winnie route](../../support/evidence/postgis-windows-upstream-build-review-2026-10-20.md): build against a matching MinGW PostgreSQL installation, then copy PostGIS DLLs and extension files into the selected MSVC PostgreSQL 18.6 archive. It tests extension creation and basic spatial DDL against that exact archive. A pass establishes the cross-toolchain module boundary, not publication readiness.

Both build paths disable optional raster, SFCGAL, tiger geocoder and topology components. They do not establish runtime dependency closure or support for those components. Remove this experiment after its findings have been incorporated into the selected Windows publication route or a human review decision.
