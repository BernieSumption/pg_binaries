# Human review queue

## Windows PostGIS build toolchain

PostGIS 3.6.4 is selected for Windows PostgreSQL 15–18. Our selected PostgreSQL Windows archives use MSVC, while [PostGIS's maintained Windows build paths](https://postgis.net/development/docs/environment/windows/) use MSYS2 or MinGW. [Run 39492045563](https://github.com/BernieSumption/pg_binaries/actions/runs/39492045563) built unmodified PostgreSQL 18.6 and PostGIS 3.6.4 together in MINGW64 and passed `CREATE EXTENSION postgis` with a reduced feature set. This establishes a working upstream build route, but it did not use the selected MSVC PostgreSQL archive.

Attempts to build against that selected archive have reached configuration and shared-library compilation but have not reached a module load test. The selected core's `pg_config` and PGXS makefiles pass MSVC compiler and flags into PostGIS's GCC build. The disposable import-library, `pg_config` and compiler adapters in [the trial](experiments/postgis-windows-abi-trial/README.md) are growing without proving that a resulting module can load. No upstream source has been modified.

Decision requested: May we replace the selected Windows PostgreSQL build with a MinGW build if it can meet the same PostgreSQL capabilities and publication tests, accepting that all existing Windows core and extension evidence must be refreshed? This is the recommended direction for a maintainable upstream build path. Alternatively, should we keep the MSVC core and invest further in the cross-toolchain adapter? Until the choice is resolved, keep Windows PostGIS outside release-ready evidence; continue other selected targets. The same-toolchain probe disabled raster, SFCGAL, topology and TIGER, so neither option is release-ready yet.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.
