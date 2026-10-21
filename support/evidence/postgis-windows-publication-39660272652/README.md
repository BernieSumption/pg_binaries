# Selected Windows PostGIS publication verification

[Run 39660272652](https://github.com/BernieSumption/pg_binaries/actions/runs/39660272652) built PostGIS 3.6.4 against the checked PostgreSQL 18.6 Windows x86-64 core. A separate Windows runner relocated the exact archives, exercised all four PostGIS SQL extension names, and passed PE dependency analysis. The [receipt](x86_64/18.6/current-receipt.json) binds the archive SHA-256 values, passed cases, and report hashes. The importer checked those bytes and retained four current-profile [component records](../../verification/).

The [runtime owner report](x86_64/18.6/runtime-package-owners.txt) identifies the copied MSYS2 DLLs. Its set of 99 package owners matches the earlier reviewed build. The final archives remain unpublished CI artifacts; this evidence does not authorize a release.
