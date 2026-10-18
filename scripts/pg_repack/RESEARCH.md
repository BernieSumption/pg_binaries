# pg_repack Linux feasibility

This trial targets pg_repack 1.5.3 with PostgreSQL 18.6 on Linux x86-64. The repository's version rule selects the latest compatible release. PGXN lists 1.5.3 as the latest package, and the 1.5.3 documentation lists PostgreSQL 18 as supported. No release after 1.5.3 was identified as of 2026-10-18. The 1.5 line is a minor line within major 1; the shared rule does not select another major.

pg_repack removes table and index bloat through online repacking. Its SQL extension is `pg_repack`; it also installs a client executable that must match the server extension version. This makes the package useful for database maintenance but requires shipping and testing both components.

The inclusion case is strong: AWS RDS, Azure Database for PostgreSQL and Supabase document pg_repack support. Upstream remains active, documents PostgreSQL 18 compatibility, and declares a BSD-3-Clause licence. Its PGXS build uses the selected PostgreSQL installation and has no separate runtime data or service dependency. The current research found no specific exclusion factor.

Upstream documents PostgreSQL 9.5 through 19 for the current development documentation. The released 1.5.3 documentation explicitly includes PostgreSQL 18; this trial makes no claim beyond that released evidence. Upstream describes UNIX/Linux builds through PGXS and also keeps MSVC project files, but those facts do not establish this repository's other OS and architecture targets.

The build script expects the PostgreSQL 18.6 x86-64 archive and checksum in its input directory. It builds the PGXS extension and CLI against that archive, packages only the project payload and licence, and records the PGXN archive digest. The verifier assembles the extension into the PostgreSQL archive, checks payload structure and collisions, creates a database, verifies `CREATE EXTENSION`, runs the CLI on a table with a primary key, checks the surviving row count, moves the installation, and repeats representative operations. The client is packaged behind the project's Linux launcher so the bundled glibc loader and relative library lookup remain available after relocation.

This is a feasibility implementation. It does not establish release eligibility, redistribution review, all-platform compatibility, or coverage for PostgreSQL 15–17. The source archive digest is currently recorded after retrieval rather than checked against a shared source pin; intended support metadata must add a reviewed source checksum before normal support is declared.

Sources:

- [pg_repack 1.5.3 documentation and release notes](https://reorg.github.io/pg_repack/)
- [PGXN 1.5.3 stable package record](https://pgxn.org/dist/pg_repack/1.5.3/)
- [PGXN package index](https://api.pgxn.org/src/pg_repack/)
- [pg_repack source and BSD-3-Clause licence](https://github.com/reorg/pg_repack)
- [AWS RDS extension versions](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html)
- [Azure pg_repack usage](https://learn.microsoft.com/en-us/azure/postgresql/troubleshoot/how-to-perform-fullvacuum-pg-repack)
- [Supabase pg_repack guide](https://supabase.com/docs/guides/database/extensions/pg_repack)
