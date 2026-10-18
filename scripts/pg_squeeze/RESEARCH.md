# pg_squeeze Linux trial

This trial targets pg_squeeze 1.9.4 with PostgreSQL 18.6 on Linux x86-64. Upstream's GitHub release page identifies 1.9.4 as its latest release, and the 1.9.0 release notes say that release added PostgreSQL 18 support. The shared version rule therefore selects 1.9.4 as the latest compatible release for this target.

The current major is 1. Its first announcement, for 1.0 beta1, is dated 2016-10-31. The later 1.9.0 release is a minor release within major 1 and does not make major 1 newly released under the two-year rule. No other major line was found in the upstream release list. pg_squeeze provides online table bloat cleanup through SQL extension `pg_squeeze`; it also supports background workers. Its upstream README documents a PGXS build and requires `shared_preload_libraries=pg_squeeze` and `wal_level=logical` on PostgreSQL 18. Its source repository includes a PostgreSQL licence file. The project remains actively maintained, with upstream activity in 2026.

The trial scripts build unmodified upstream commit `400c5f6ae9bc911073a6824e9a19f4d475fb7331`, verify the tag resolves to that commit, install only the shared library, SQL/control files and licence, then test the final archive with PostgreSQL 18.6. The Alpine verifier assembles the archives, configures the required settings, creates an extension and runs `squeeze.squeeze_table` on a table with a primary key. It checks the operation log and surviving row count before and after moving the PostgreSQL installation.

Docker was unavailable in the execution environment: the Docker API returned permission denied for the configured socket. No compilation or compiled-artifact execution was attempted. The build and archive verification paths are therefore implemented but unverified; shell syntax checks are the only local validation. The archive checksum, build output, relocation behaviour and actual pg_squeeze operation remain unknown. This is a draft trial, not a verified candidate or advertised support decision. It does not establish support on other PostgreSQL releases, operating systems or architectures, or complete redistribution review.

Sources reviewed 2026-10-18:

- [Upstream releases](https://github.com/cybertec-postgresql/pg_squeeze/releases) — latest 1.9.4, its verified tag and commit; 1.9.0 adds PostgreSQL 18 support.
- [Upstream 1.9.4 source commit](https://github.com/cybertec-postgresql/pg_squeeze/commit/400c5f6ae9bc911073a6824e9a19f4d475fb7331) — immutable source revision used by the trial.
- [Upstream README](https://github.com/cybertec-postgresql/pg_squeeze/blob/REL1_9_4/README.md) — PGXS build, PostgreSQL configuration and usage.
- [Upstream licence](https://github.com/cybertec-postgresql/pg_squeeze/blob/REL1_9_4/LICENSE) — licence included in the package.
- [PostgreSQL mailing-list announcement](https://www.postgresql.org/message-id/f7288807-acf0-0ef6-0864-94cad76f9a26%40cybertec.at) — announces pg_squeeze 1.0 beta1 on 2016-10-31.
- [CYBERTEC project page](https://www.cybertec-postgresql.com/en/products/pg_squeeze/) — describes the extension's table-bloat cleanup use case.
