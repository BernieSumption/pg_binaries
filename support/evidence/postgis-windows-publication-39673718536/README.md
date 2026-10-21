# Windows PostGIS 16.15 verification

[Run 39673718536](https://github.com/BernieSumption/pg_binaries/actions/runs/39673718536) built PostGIS 3.6.4 with the selected PostgreSQL 16.15 core for Windows x86-64. A separate runner relocated the final archives, passed SQL probes for all four PostGIS extension names, and checked PE dependencies. The [receipt](x86_64/16.15/current-receipt.json) binds the archive hashes, passing cases, and retained reports. The importer checked the downloaded archive and report hashes and retained four current-profile component records.

The [runtime owner report](x86_64/16.15/runtime-package-owners.txt) names the packages supplying the 154 copied DLLs. Its set of 99 package owners matches the previously reviewed Windows PostGIS closure in [run 39646973668](../postgis-windows-publication-39646973668/runtime-package-owners.txt).
