# Windows PostgreSQL 16.15 publication evidence

[Run 39114881034](https://github.com/BernieSumption/pg_binaries/actions/runs/39114881034) passed the current Windows x86-64 PostgreSQL 16.15 and pgvector 0.8.7 publication profiles. The importer validated the downloaded final archives, PE dependency report, PDB index, diagnostics and both archive-bound records against the profile at source revision `bbc22fa958fc544ce0e4410f1c6848d1dd2d0058`.

The PostgreSQL archive SHA-256 is `b4d7a443200ed7464895a87451cc44cfd58ca322282929f05454f4b914dbb31b`; pgvector is `6a0c530eda3de6e72035f78594c6903a7a042598d7127745bfe36e97184f95fd`. Both archives identify build `github-39114881034-1` and Windows Server 2022 image `win22/20261012.333.1`. PostgreSQL uses the exact upstream `REL_16_15` Git source pin.

The PE report leaves Windows 10 build 10240 imported-function availability unresolved. Dependency provenance and redistribution review also remain open.
