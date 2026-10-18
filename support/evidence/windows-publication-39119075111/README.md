# Windows PostgreSQL 16.15 publication evidence

[Run 39119075111](https://github.com/BernieSumption/pg_binaries/actions/runs/39119075111) passed the current Windows x86-64 PostgreSQL 16.15 and pgvector 0.8.7 publication profiles. The importer validated the downloaded final archives, PE dependency report, PDB index, diagnostics and archive-bound records against profile revision `7906fed6aff79dca12f14da6fe948b29925f04b0cd95d90a5e26f08fb3142d19` at source revision `eecefcbb0362a602afb136b5ee8769113c6a47f2`.

The PostgreSQL archive SHA-256 is `a4a368282a2f89a6e85bc81cfbf0a73e5c1a1a9ef4c813c681698a9af0d50bb0`; pgvector is `b521a2298b55cb6c08a583b8abe59966084c6c4bb10b7d7b91afe889dc12bda1`. Both records use Windows Server 2022 image `win22/20261012.333.1`. See the current-profile records in `support/verification/`.

The PE report does not establish imported-function availability on Windows 10 build 10240. Dependency provenance and redistribution review remain open.
