# Unmodified GEOS source at the macOS 11 target

[Run 39057655819](https://github.com/BernieSumption/pg_binaries/actions/runs/39057655819) built GEOS 3.15.0 from the upstream source archive on standard macOS 15 Apple Silicon and Intel runners. Both jobs verified SHA-256 `d5e5192a686d065eaed082de14dd26244c5c8e02bff16b2c6cce3265f648e00e`, matching the digest published in the signed Debian FTP Masters source-acceptance notice. The retained reports show both dylibs targeting macOS 11.0 with the expected architecture.

Both dylibs use `@rpath` install IDs. `libgeos_c` resolves `libgeos` through `@rpath` and declares `@loader_path`; neither architecture's load commands contain temporary build or host paths. The probe establishes source-build feasibility and clean load paths for GEOS alone. Integration, dependency closure and final PostgreSQL archive verification remain open.
