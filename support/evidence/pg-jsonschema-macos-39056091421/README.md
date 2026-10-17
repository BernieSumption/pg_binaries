# pg_jsonschema source feasibility on Intel macOS

[Run 39056091421](https://github.com/BernieSumption/pg_binaries/actions/runs/39056091421) built unmodified PostgreSQL 18.6 and pg_jsonschema 0.3.4 with pgrx's `pg18` feature on a macOS 15.7.9 x86-64 runner. It passed `CREATE EXTENSION` and a table constraint using `jsonb_matches_schema`. The built module declares macOS 11.0 as its minimum. The retained SQL output and Mach-O inspection came from the CI artifact.

The module's install name contains its temporary source-build directory. This is source compatibility evidence, not a relocated archive, dependency-closure or publication check. Apple Silicon, Windows and the other selected PostgreSQL majors remain untested here.
