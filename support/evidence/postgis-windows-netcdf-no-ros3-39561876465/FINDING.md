# PostGIS Windows NetCDF import-resolution trial

GitHub Actions [run 39561876465](https://github.com/BernieSumption/pg_binaries/actions/runs/39561876465) passed on the standard Windows 2022 x86-64 runner at revision `0ed44d987a4b75d60a16b01d6149ad99d569f54`. The `postgis_windows_abi_probe` built upstream NetCDF-C 4.10.1 and unmodified PostgreSQL 18.6/PostGIS 3.6.4 with MSYS2 MINGW64. It then created `postgis`, `postgis_raster`, `postgis_topology`, and `postgis_sfcgal` and passed the spatial transform probe.

The NetCDF archive URL was `https://github.com/Unidata/netcdf-c/archive/v4.10.1/netcdf-4.10.1.tar.gz`; its pinned SHA-256 was `33c27231c478c3b35da7c7758fbdd02da1fe407abcb16ddfe195f69d164f930d`. The validated CMake cache settings are in `netcdf-cmake-options.txt`: HDF5 enabled, S3 AWS disabled, byte-range disabled, tests disabled. The upstream source was unmodified. The blank `HAS_HDF5_ROS3` cache entry shows that the build did not enable the ROS3 path.

The recursive import resolver found no missing symbols, unresolved DLLs, or `objdump` errors for the NetCDF dependency closure (27 modules) or the final raster dependency closure (159 modules). Reports are retained in `netcdf-import-resolution.json` and `import-resolution.json`. The runner log and SQL output remain in the run artifact `postgis-windows-abi-trial-39561876465`; this evidence folder retains the small configuration and import-resolution reports.

This validates the loader fix and SQL probe in the same-toolchain experiment. It does not establish a relocatable selected archive or a clean-runner result.
