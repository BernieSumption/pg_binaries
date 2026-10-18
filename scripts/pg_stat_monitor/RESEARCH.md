# pg_stat_monitor 2.4.0 Linux trial

`pg_stat_monitor` records PostgreSQL query statistics and exposes them through the `pg_stat_monitor` SQL extension. Percona documents PostgreSQL 14 and later compatibility, and its 2.4.0 release notes say the release adds PostgreSQL 19 beta 3 support. The selected trial target is PostgreSQL 18.6 on Linux x86-64.

The upstream project is maintained by Percona and distributed under the PostgreSQL License, as recorded in its repository metadata. Its documented source build requires Git, make, GCC and `pg_config`; PGXS supports building against the selected PostgreSQL installation. The build uses upstream tag `2.4.0` without source modifications and records the resolved commit and Git archive digest in package metadata.

This trial does not add `pg_stat_monitor` to `support.json` or claim advertised support. The fixed Alpine verifier checks archive structure, dependencies, ordinary-user startup, query monitoring, and relocation with the supplied PostgreSQL 18.6 archive.

## Sources

- [Percona pg_stat_monitor 2.4.0 release notes](https://docs.percona.com/pg-stat-monitor/release-notes/2.4.0.html)
- [Percona build instructions](https://docs.percona.com/pg-stat-monitor/install.html)
- [Upstream repository](https://github.com/percona/pg_stat_monitor)
- [Upstream 2.4.0 tag](https://github.com/percona/pg_stat_monitor/tree/2.4.0)
