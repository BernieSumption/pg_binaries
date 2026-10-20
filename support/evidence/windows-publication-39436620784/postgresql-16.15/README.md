# PostgreSQL 16.15 Windows core verification

[Run 39436620784](https://github.com/BernieSumption/pg_binaries/actions/runs/39436620784) passed the current Windows x86-64 core profile on Windows Server 2022 image `win22/20261012.333.1`. The archive SHA-256 is `efd9ff15882a355ac9f431eb0c085abbf571bed8a3821a542370f02c83c0715c`; the identity and artifact pins refer to this run and archive.

Archive-suite, diagnostics, symbols, and PE dependency checks passed. This current-runner evidence does not establish execution on the Windows 10 support floor. Redistribution review for the bundled vcpkg runtime dependencies remains pending, so the archive is not eligible for release publication.
