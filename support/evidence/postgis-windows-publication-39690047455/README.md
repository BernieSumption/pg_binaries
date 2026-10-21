# Windows PostGIS 15.19 verification

[Run 39690047455](https://github.com/BernieSumption/pg_binaries/actions/runs/39690047455) built PostGIS 3.6.4 with the selected PostgreSQL 15.19 core for Windows x86-64. Fresh-runner verification passed the relocated archive suite, SQL probes for all four PostGIS extension names, static analysis and PE dependency checks. The importer validated all four component records against the current `postgis-publication-windows-x86_64-15.19` profile and retained the receipt and reports under `x86_64/15.19`.

The [runtime owner report](x86_64/15.19/runtime-package-owners.txt) lists 154 copied DLLs from 99 MSYS2 packages. Its library and package sets exactly match the retained PostgreSQL 16.15, 17.11 and 18.6 reports; it identifies no new runtime project. The final extension archive's central `postgis/LICENSES/postgis/LICENCE` pointer passed verification.
