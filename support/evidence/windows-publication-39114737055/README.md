# Windows PostgreSQL 18.6 publication evidence

[Run 39114737055](https://github.com/BernieSumption/pg_binaries/actions/runs/39114737055) passed the current Windows x86-64 PostgreSQL 18.6 and pgvector 0.8.7 publication profiles. The importer validated the downloaded final archives, PE dependency report, PDB index, diagnostics and both archive-bound records against the profile at source revision `a4dac8dde221b7f289235c4e1d1934e243fdfbc8`.

The PostgreSQL archive SHA-256 is `fc8e06cc1fbf420f178a7819ab570f6782376fc5971431b74a333b1ce13c6336`; pgvector is `8721365fd4613d3774daf7e4f6f3591e833d9bb2c83d78c7c19459a1336ea8d1`. Both archives identify build `github-39114737055-1` and Windows Server 2022 image `win22/20261012.333.1`. The build uses PostgreSQL's pinned 18.6 source archive and vcpkg revision `9e593bb18ea69cc5095e012465dcd675a822ed0d`.

The PE report leaves Windows 10 build 10240 imported-function availability unresolved. Dependency provenance and redistribution review also remain open.
