# Windows PostgreSQL 15.19 publication evidence

[Run 39117226735](https://github.com/BernieSumption/pg_binaries/actions/runs/39117226735) passed the current Windows x86-64 PostgreSQL 15.19 and pgvector 0.8.7 publication profiles. The importer validated the downloaded final archives, PE dependency report, PDB index, diagnostics and archive-bound records against profile revision `7906fed6aff79dca12f14da6fe948b29925f04b0cd95d90a5e26f08fb3142d19` at source revision `abcbf20c3c3fa01e35f5512845cfac4d269e62a4`.

The PostgreSQL archive SHA-256 is `7ffadf8bfb0b122a37759dec7eff1dd7e5307997d74791a6d84fa3f4a47bb02b`; pgvector is `99ffabc67d2c2b40dd2420b9c214ecad4a3e76cd1e47724d0d6493e9a4506f36`. Both records use Windows Server 2022 image `win22/20261012.333.1`. See the current-profile records in `support/verification/`.

The PE report does not establish imported-function availability on Windows 10 build 10240. Dependency provenance and redistribution review remain open.
