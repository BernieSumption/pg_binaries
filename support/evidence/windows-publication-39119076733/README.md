# Windows PostgreSQL 17.11 publication evidence

[Run 39119076733](https://github.com/BernieSumption/pg_binaries/actions/runs/39119076733) passed the current Windows x86-64 PostgreSQL 17.11 and pgvector 0.8.7 publication profiles. The importer validated the downloaded final archives, PE dependency report, PDB index, diagnostics and archive-bound records against profile revision `7906fed6aff79dca12f14da6fe948b29925f04b0cd95d90a5e26f08fb3142d19` at source revision `eecefcbb0362a602afb136b5ee8769113c6a47f2`.

The PostgreSQL archive SHA-256 is `c94d4cef57880ec80a4177570ab7c1f2e955f1e799a2d41fb38412e07c435285`; pgvector is `e5fecab0d7cb0444750c9995a5b524471b4ced0cfef574a4c3f5cfd646d8b8ee`. Both records use Windows Server 2022 image `win22/20261012.333.1`. See the current-profile records in `support/verification/`.

The PE report does not establish imported-function availability on Windows 10 build 10240. Dependency provenance and redistribution review remain open.
