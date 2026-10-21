# PostGIS conda SFCGAL macOS arm64 diagnostic closure

[Run 39522418114](https://github.com/BernieSumption/pg_binaries/actions/runs/39522418114) successfully built SFCGAL 2.3.0 and PostGIS for the selected PostgreSQL 18.6 macOS arm64 core, then probed the four extension names. The run established build and SQL probe feasibility; it did not produce a relocatable extension archive.

The bundled dependency report identifies 66 dylibs. The ownership report maps 65 dylibs to 50 distinct conda packages and identifies the locally built SFCGAL dylib as the one unresolved owner. The two staged runtime data trees map to `libgdal-core` (93 files under `share/gdal`) and `proj` (16 files under `share/proj`). The exact package/build identities, source URLs, archive hashes, and conda license metadata are retained in `conda-package-owners.json`; the report is diagnostic and does not establish final-archive notice completeness.

The unresolved file is `lib/libSFCGAL.2.3.0.dylib`. Its build source is pinned in `sfcgal-source.json` to commit `137203dae01faab4a1287934f9457e925e3b4383` with source archive SHA-256 `426abf9ac0de764a6098abe89c9dc84aa59273d0c5ff90819ed49a9c21f1c21f`. The SFCGAL source notice inventory and final bundled archive inventory remain to be collected and validated before packaging can be considered release-ready.

`core-target.json` binds this experiment to PostgreSQL 18.6 arm64 core archive from run 39260057987, SHA-256 `33807e7b17519acf8643ed73429ba7c983cf9572be12048bdb7b6a872f682608`.
