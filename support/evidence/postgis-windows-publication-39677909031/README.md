# Windows PostGIS 18.6 verification

[Run 39677909031](https://github.com/BernieSumption/pg_binaries/actions/runs/39677909031) built PostGIS 3.6.4 with the selected PostgreSQL 18.6 core for Windows x86-64. A separate runner relocated the final archives, passed SQL probes for all four PostGIS extension names, and checked PE dependencies. The [receipt](x86_64/18.6/current-receipt.json) binds the archive hashes, passing cases and retained reports. The importer checked the downloaded archive and report hashes and retained four component records. Its historical profile revision was reviewed as equivalent to the narrowed current verification inputs: the case list and retained source bytes are unchanged.

The [runtime owner report](x86_64/18.6/runtime-package-owners.txt) names the packages supplying the 154 copied DLLs. Its set of 99 package owners matches the [PostgreSQL 16.15 selected archive](../postgis-windows-publication-39673718536/x86_64/16.15/runtime-package-owners.txt).
