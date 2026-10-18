# pg_partman Linux feasibility

This trial targets pg_partman 5.5.0 with PostgreSQL 18.6 on Linux x86-64. The shared version policy selects the latest compatible release, and v5.5.0 is the current stable release as of 2026-10-18. Upstream requires PostgreSQL 14 or later. Major 5 first appeared on 2023-09-28, so it does not trigger the additional-major rule's two-year window; the latest-release rule still selects 5.5.0.

pg_partman manages PostgreSQL declarative range and list partitions, including automated creation and retention of child tables. The SQL extension is `pg_partman`; its optional background worker can run maintenance without an external scheduler. The upstream README lists AWS, Google, Azure and Supabase among services offering it, and the repository's provider catalogue also records Neon and other major hosts.

The inclusion case is strong: upstream is active, PostgreSQL 18 is within its documented compatibility range, and the extension addresses routine partition lifecycle work. It is licensed under PostgreSQL's permissive licence. Building the background worker requires no separate runtime library; pg_jobmon is optional and is not required for the core extension. The worker requires `shared_preload_libraries` and careful role configuration, so this trial verifies SQL installation and partition creation without claiming worker configuration coverage.

The build script expects the PostgreSQL 18.6 x86-64 archive and checksum in its input directory. It builds the unmodified v5.5.0 tag with PGXS, packages the shared library, control and SQL files with the upstream licence, and records the PGXN source archive digest. The verifier checks package contents and collisions, creates a database, installs pg_partman, creates a range partition set, moves PostgreSQL to a new prefix, and repeats the SQL checks. The extension adds no executable of its own.

This is a feasibility implementation. It does not establish release eligibility, redistribution review, all-platform compatibility, or coverage for PostgreSQL 15–17. The source archive digest is recorded after retrieval rather than checked against a shared source pin; support metadata must add a reviewed source checksum before normal support is declared.

Sources:

- [pg_partman 5.5.0 release and notes](https://github.com/pgpartman/pg_partman/releases/tag/v5.5.0)
- [pg_partman 5.0.0 first major-5 release](https://github.com/pgpartman/pg_partman/releases/tag/v5.0.0)
- [Upstream README, requirements, optional integrations and setup](https://github.com/pgpartman/pg_partman/blob/v5.5.0/README.md)
- [Upstream v5.5.0 PGXS Makefile and PostgreSQL minimum](https://github.com/pgpartman/pg_partman/blob/v5.5.0/Makefile)
- [Upstream PostgreSQL licence](https://github.com/pgpartman/pg_partman/blob/v5.5.0/LICENSE.txt)
- [PGXN v5.5.0 package](https://pgxn.org/dist/pg_partman/5.5.0/)
- [Amazon RDS extension versions](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html)
- [Azure PostgreSQL extensions](https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-versions)
- [Supabase extension catalogue](https://supabase.com/docs/guides/database/extensions)
- [Neon extension catalogue](https://neon.com/docs/extensions/pg-extensions)
