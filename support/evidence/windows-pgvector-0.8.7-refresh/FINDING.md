# pgvector 0.8.7 Windows refresh

Four selected Windows publication runs passed archive-suite, symbol, diagnostic and PE dependency checks on fresh Windows Server 2022 runners. The imported [verification records](../../verification/) bind each extension archive to the exact PostgreSQL core archive used in its run:

- [PostgreSQL 15.19, run 39575480794](https://github.com/BernieSumption/pg_binaries/actions/runs/39575480794): pgvector `6b419b9ee193cd810b6a83b810c16a666a4b67335356c276f1c07cddb6fd10b1`; core `b1793090085453fdcba4a7af14084ea5e1695b50390833d3c997840f78a9a809`.
- [PostgreSQL 16.15, run 39575480299](https://github.com/BernieSumption/pg_binaries/actions/runs/39575480299): pgvector `5f2101e83c3aa58d09cdc3804a1c6429f2dbe0982231c2696ac9f7d8d2659d99`; core `d2953539433a05f551a53bd85b76e05516632e9d5b105de422db72b948c6f805`.
- [PostgreSQL 17.11, run 39575479291](https://github.com/BernieSumption/pg_binaries/actions/runs/39575479291): pgvector `d3cfe42cdec7117b8728391410992ab2e0596fb83afb0e3757bbaa2966551dce`; core `891dcdf2889dd3b08b07a61c84ffdd65f37a4ba46fc46508d6dd53be8826864e`.
- [PostgreSQL 18.6, run 39575124082](https://github.com/BernieSumption/pg_binaries/actions/runs/39575124082): pgvector `4df21e236154c0a3f5b259b62da96ec5385726039003113cc24b26774e12359d`; core `dc6b7bbc1df71183ea79cc7a36c1f410d495446aaef4f96ab1adab3b547b7b17`.

This verifies the current archive profile for these targets. Redistribution clearance and the Windows minimum-OS assessment remain separate publication checks.
