# Windows PostgreSQL 17.11 publication evidence

[Run 39114882446](https://github.com/BernieSumption/pg_binaries/actions/runs/39114882446) passed the current Windows x86-64 PostgreSQL 17.11 and pgvector 0.8.7 publication profiles. The importer validated the downloaded final archives, PE dependency report, PDB index, diagnostics and both archive-bound records against the profile at source revision `bbc22fa958fc544ce0e4410f1c6848d1dd2d0058`.

The PostgreSQL archive SHA-256 is `dc81e09b896ab60a9c3381908bb8cec7e36f4d4b2d8f3d1174d29031c8ee62af`; pgvector is `384404292db665dac12014edca10206c704d15e8b5a7a94e69fc5da6b93aec48`. Both archives identify build `github-39114882446-1` and Windows Server 2022 image `win22/20261012.333.1`.

The PE report leaves Windows 10 build 10240 imported-function availability unresolved. Dependency provenance and redistribution review also remain open.
