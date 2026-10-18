# Windows PostgreSQL 18.6 publication evidence

[Run 39089826690](https://github.com/BernieSumption/pg_binaries/actions/runs/39089826690) passed the current Windows x86-64 PostgreSQL 18.6 and pgvector 0.8.7 publication profiles. The importer validated the downloaded final archives, PE dependency report, PDB index, diagnostics and both archive-bound records against the current profile.

The PostgreSQL archive SHA-256 is `ee0b6781299cc462ba4305ff4a318519fc61741d7b0f05988cf29030eafeedd2`; pgvector is `d871febec42ff838551d531f0dc5b58f4c717b726782beed2b0fba9263f45f96`. Both records identify build `github-39089826690-1`, source/build/test revision `01fe5d267c30f73bb6e44d2b37c18f008223bc75`, and Windows Server 2022 image `win22/20261012.333.1`. The PE report inspected 144 files and recorded the imported DLLs and functions; the symbol index binds 125 modules to PDBs.

The PE report leaves availability of imported functions on Windows 10 build 10240 unresolved. The archives remain temporary CI artifacts; dependency provenance and redistribution review also remain open.
