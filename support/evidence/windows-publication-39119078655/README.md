# Windows PostgreSQL 18.6 publication evidence

[Run 39119078655](https://github.com/BernieSumption/pg_binaries/actions/runs/39119078655) passed the current Windows x86-64 PostgreSQL 18.6 and pgvector 0.8.7 publication profiles. The importer validated the downloaded final archives, PE dependency report, PDB index, diagnostics and archive-bound records against profile revision `7906fed6aff79dca12f14da6fe948b29925f04b0cd95d90a5e26f08fb3142d19` at source revision `eecefcbb0362a602afb136b5ee8769113c6a47f2`.

The PostgreSQL archive SHA-256 is `8679af38bfb384cf5f287575b8be4d7946490df14e0680674645d50d3646758d`; pgvector is `3c89b096b64e64a90b3b71c7891b399222d96652e989bba58360c2b2a44d8a21`. Both records use Windows Server 2022 image `win22/20261012.333.1`. See the current-profile records in `support/verification/`.

The PE report does not establish imported-function availability on Windows 10 build 10240. Dependency provenance and redistribution review remain open.
