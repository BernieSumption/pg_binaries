# pg_jsonschema Mac Intel source feasibility

[Run 39054402192](https://github.com/BernieSumption/pg_binaries/actions/runs/39054402192) compiled unmodified PostgreSQL 18.6 and pg_jsonschema 0.3.4 on the standard macOS 15 Intel runner, selecting the upstream `pg18` feature with cargo-pgrx 0.16.1. The retained `probe-output.txt`, with trailing whitespace removed, shows `CREATE EXTENSION`, representative JSON schema constraint DDL, an accepted row and the catalogue definitions.

The run failed after the SQL probe because its inspection step searched a hard-coded library directory rather than PostgreSQL's `pg_config --pkglibdir`. No Mach-O floor evidence or final archive was produced. A corrected probe is pending.
