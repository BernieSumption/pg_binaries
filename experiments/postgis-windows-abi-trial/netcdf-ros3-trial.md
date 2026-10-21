# Windows NetCDF ROS3 dependency trial

The same-toolchain Windows probe previously failed to load `postgis_raster-3.dll` because `libnetcdf.dll` imported `H5Pset_fapl_ros3`, which was absent from the runtime `libhdf5-320.dll`. This trial builds upstream NetCDF-C 4.10.1 against the installed HDF5 with NetCDF-4/HDF5 support enabled and optional AWS S3, byte-range, and HDF5 ROS3 support disabled.

The source archive is the upstream [netCDF-C 4.10.1 tag](https://github.com/Unidata/netcdf-c/tree/v4.10.1), downloaded from `https://github.com/Unidata/netcdf-c/archive/v4.10.1/netcdf-4.10.1.tar.gz`. Its SHA-256 is pinned to `33c27231c478c3b35da7c7758fbdd02da1fe407abcb16ddfe195f69d164f930d`, matching the URL and digest in the [MSYS2 package recipe](https://github.com/msys2/MINGW-packages/blob/master/mingw-w64-netcdf/PKGBUILD). The experiment installs this DLL under the run output directory, places it first on `PATH`, and resolves its recursive DLL imports before compiling PostgreSQL or PostGIS. It then uses the same PostGIS four-name SQL probe.

The compact evidence is in `dll-diagnostic/netcdf-import-resolution.json` and `dll-diagnostic/import-resolution.json`; the build log records CMake configuration and the final SQL probe. This trial tests the dependency fix only and does not define the Windows publication dependency set.
