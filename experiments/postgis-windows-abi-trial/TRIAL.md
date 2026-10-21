# Windows PostGIS relocatable archive trial

Created 2026-10-21 to determine whether unmodified MINGW64 PostGIS can be packaged with the selected MSVC PostgreSQL core and run after relocation on a fresh Windows runner.

This non-publication trial builds unmodified PostgreSQL 18.6 and PostGIS 3.6.4 in MSYS2 MINGW64, then stages the four tested PostGIS SQL extensions and the recursive non-system DLL closure in a separate extension archive. NetCDF-C 4.10.1 uses the validated settings in `netcdf-ros3-trial.md`: HDF5 enabled, optional S3 AWS and byte-range disabled, and tests disabled.

Run `postgis_windows_relocatable_trial` in the `postgis-pilot.yml` workflow to build the archive against the pinned selected PostgreSQL core. A separate Windows 2022 job downloads those exact archive bytes, checks their hashes and core binding, relocates both trees, starts PostgreSQL without an MSYS2 installation, and runs `scripts/postgis/probe.sql`.

The archive bundles the DLLs and GDAL, PROJ, and SFCGAL data found in the experiment's runtime closure. The run is a packaging and relocation experiment. Before selecting it for publication, identify any shipped projects missing from `LICENSES.md`, add publication metadata and static PE verification, and verify the final archive under the selected profile.

When that selected path passes, move any reusable recipe into `scripts/postgis/` and remove the trial and its manual workflow jobs. If this route cannot meet the requirements without upstream source changes, record the finding and remove the abandoned experiment.
