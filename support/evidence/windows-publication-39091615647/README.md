# Windows PostgreSQL 17.11 publication evidence

[Run 39091615647](https://github.com/BernieSumption/pg_binaries/actions/runs/39091615647) passed the current Windows x86-64 PostgreSQL 17.11 and pgvector 0.8.7 publication profiles. The importer validated the exact final archives, PE dependency report, PDB index and diagnostics, then retained both archive-bound verification records.

The PostgreSQL archive SHA-256 is `94bff6a5b34da9a515d49361355137f96d59e0d6d81a0f3e203561f37e4b653d`; pgvector is `60822f47a59357f175f7e6778f7e4ed234f8cfa6e2e3680d6a86af97bfcc2eb9`. The run used source revision `2ea355e60e1bb3cd7304b9c8ce7be3246442b320` and Windows Server 2022 image `win22/20261012.333.1`. The PE report covers 142 files, and the symbol index binds 123 modules to PDBs.

This is current-profile pilot evidence. The archives remain temporary CI artifacts, and dependency provenance and redistribution clearance remain open.
