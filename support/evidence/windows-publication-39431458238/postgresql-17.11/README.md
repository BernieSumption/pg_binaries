# PostgreSQL 17.11 Windows core verification

[Run 39431458238](https://github.com/BernieSumption/pg_binaries/actions/runs/39431458238) passed the current Windows x86-64 core profile on Windows Server 2022 image `win22/20261012.333.1`. The record binds archive SHA-256 `8238a3ce5c85242091e486396a2db4d63b8581f22943b4c72efb75ed232e4d31` to passing archive-suite, diagnostics, symbols, and PE dependency checks.

This exact archive is selected by the PostgreSQL 17.11 Windows core identity and artifact pins for extension builds. The earlier pin from run 39425253610 remains historical. Redistribution review remains pending for the bundled vcpkg runtime dependencies.
