# PostGIS source-built GDAL conda arm64 trial

[Run 39558166272](https://github.com/BernieSumption/pg_binaries/actions/runs/39558166272) completed successfully against the selected PostgreSQL 18.6 arm64 core. The probe found and created all four extension names: `postgis`, `postgis_raster`, `postgis_sfcgal`, and `postgis_topology`.

The trial built GDAL 3.13.3 from the pinned source archive (SHA-256 `5e0c388d83da2d686cc00a40272882432cdb54edff43d4af173e532844a0a0ea`); its configure log reports the source build prefix and PostGIS `configure.log` records the source-built `gdal-config`. The bundled dependency report nevertheless resolves `libgdal.39.3.13.3.dylib` to the conda prefix. It records the same 66 dylibs and 50 conda package owners as run 39522418114, so this run did not demonstrate a smaller conda runtime closure.

The report counts 26 source-built GDAL data files and 16 conda-owned PROJ data files. The unresolved library remains the locally built SFCGAL dylib. The likely measurement fix is to let the existing bundler search the GDAL prefix before the conda prefix, while preserving its current single-prefix behavior for other builds.
