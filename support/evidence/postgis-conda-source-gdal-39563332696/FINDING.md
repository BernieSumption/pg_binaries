# macOS arm64 source-GDAL PostGIS closure finding

[Run 39563332696](https://github.com/BernieSumption/pg_binaries/actions/runs/39563332696) built PostGIS 3.6.4 and source-built SFCGAL 2.3.0 against the selected PostgreSQL 18.6 arm64 core on a standard macOS 15 runner. All four SQL extensions were created and the geometry, raster, topology and SFCGAL probes passed.

The diagnostic closure contains 38 dylibs, including source-built GDAL 3.13.3 and SFCGAL 2.3.0, plus 25 uniquely owned conda packages. Ownership is unresolved only for the SFCGAL dylib built into the conda prefix; its exact source commit and archive checksum are recorded in `sfcgal-source.json`. This is build and closure evidence only. It does not establish a final archive, relocation, license inventory or redistribution eligibility. The selected route remains the existing Homebrew path while the separate 25-package conda evidence path is deferred.
