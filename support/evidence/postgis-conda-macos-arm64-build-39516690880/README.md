# macOS arm64 PostGIS conda build trial

[Run 39516690880](https://github.com/BernieSumption/pg_binaries/actions/runs/39516690880) used revision `011d555d` to try unmodified PostGIS 3.6.4 against the selected PostgreSQL 18.6 arm64 archive and conda-forge GEOS, PROJ and GDAL. It stopped before downloading or compiling PostGIS: the trial required `protoc-c`, but the installed conda environment did not contain that executable. The build job failed at its tool precheck.

The next three-SQL-name trial disables protobuf through PostGIS's configure option and removes that precheck. This result says nothing about PostGIS build, SQL behavior or archive portability.
