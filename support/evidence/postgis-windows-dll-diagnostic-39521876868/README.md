# Windows PostGIS raster loader diagnostic

Run [39521876868](https://github.com/BernieSumption/pg_binaries/actions/runs/39521876868) built PostgreSQL 18.6 and PostGIS 3.6.4 with the same MSYS2 MINGW64 toolchain. `CREATE EXTENSION postgis_raster` failed with Windows error 127, “The specified procedure could not be found.” The server log records the failure at `cluster/server.log` in artifact `postgis-windows-abi-trial-39521876868`.

The artifact contains `dll-diagnostic/postgis_raster-3.dll.txt` and reports for `libgdal-39.dll`, `libgeos_c.dll`, `libproj-25.dll`, and `postgres.exe`. I compared every raster import to the available dependency export names. All 81 imports from `libgeos_c.dll`, six from `libproj-25.dll`, and 91 from `postgres.exe` appear in the corresponding reports' export-name tables.

The raster module imports 108 names from `libgdal-39.dll`. Its report reaches the 1 MiB per-file cap before the export-name table, so it cannot establish whether any of those names are absent. GDAL also imports many further DLLs, whose exports are not included in this artifact. The exact missing procedure and owning DLL therefore remain unknown; the current reports do not support attributing the failure to GDAL or one of its transitive dependencies.

The downloaded artifact is retained locally at `/private/tmp/postgis-windows-abi-trial-39521876868`. SHA-256 digests of its five diagnostic reports:

- `postgis_raster-3.dll.txt`: `7150e8b102af580b957e32bb7e177fd0e0747abfd6a6ed0f0f0564ed562d63cc`
- `libgdal-39.dll.txt`: `6772091717530ccedcfd21e46541101fb23b44d562623938658779653bc28609`
- `libgeos_c.dll.txt`: `3f757321683aeffd18a3615658deb41f8159a5b2772505662eabef6c0cd08a4f`
- `libproj-25.dll.txt`: `44705edc0cc1e93abced29d92996b0edde9b32725913fb16a8f90f21aadd3515`
- `postgres.exe.txt`: `4d3602128c340f6a6b10e4bca9750deb2e06265505803a190ce288865c0430ca`

The smallest useful follow-up is a focused comparison on the Windows runner: extract the raster module's 108 GDAL imports, compare them with the complete `libgdal-39.dll` export-name table, and report only missing names. If all 108 are exported, repeat that check for GDAL's direct imports and the corresponding runtime DLL exports to identify any transitive missing procedure.
