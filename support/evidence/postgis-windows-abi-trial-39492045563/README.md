# Windows PostGIS same-toolchain feasibility result

On 2026-10-20, [run 39492045563](https://github.com/BernieSumption/pg_binaries/actions/runs/39492045563) completed on the standard Windows 2022 x86-64 runner. Its `windows-postgis-abi` job built unmodified PostgreSQL 18.6 and PostGIS 3.6.4 source archives in MSYS2 MINGW64, using GCC for both. PostGIS was configured without raster, TIGER geocoder, topology, SFCGAL and protobuf support.

After `make install`, the job initialized a PostgreSQL cluster, started the server, created a database and executed `CREATE EXTENSION postgis` and `SELECT postgis_full_version()`. Both SQL commands succeeded. The latter reported PostGIS 3.6.4, PostgreSQL 18.6, GEOS 3.15.0, PROJ 9.8.1, libxml2 2.15.4 and libjson-c 0.19.

This establishes a same-toolchain build and load path for the reduced PostGIS feature set. The selected Windows PostgreSQL archive uses MSVC, so this run does not establish compatibility with the core intended for publication. The job also used packages installed on its build runner and did not produce or verify a relocatable PostGIS archive.
