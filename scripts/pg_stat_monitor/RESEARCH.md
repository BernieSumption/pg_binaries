# pg_stat_monitor 2.4.0 Linux trial

`pg_stat_monitor` records PostgreSQL query statistics and exposes them through the `pg_stat_monitor` SQL extension. Percona documents PostgreSQL 14 and later compatibility, and its 2.4.0 release notes say the release adds PostgreSQL 19 beta 3 support. The selected trial target is PostgreSQL 18.6 on Linux x86-64.

The upstream project is maintained by Percona and distributed under the PostgreSQL License, as recorded in its repository metadata. Its documented source build requires Git, make, GCC and `pg_config`; PGXS supports building against the selected PostgreSQL installation. The build downloads the upstream tag archive, checks SHA-256 `21e4fe737e8eeb5a5ae96df781c61e3ceb74d481041a136e42503be636dc9fe8`, and records its resolved commit `2de2db763db9f590cd28159741c36b41f66eb985` in package metadata.

This trial does not add `pg_stat_monitor` to `support.json` or claim advertised support. The fixed Alpine verifier checks archive structure, dependencies, ordinary-user startup, query monitoring, and relocation with the supplied PostgreSQL 18.6 archive. Run [39138548058](https://github.com/BernieSumption/pg_binaries/actions/runs/39138548058) is the initial trial. The workflow dispatch attempt returned HTTP 404 because the workflow was absent from the default branch; root enabled a path-filtered push trigger on `spike`.

## Sources

- [Percona pg_stat_monitor 2.4.0 release notes](https://docs.percona.com/pg-stat-monitor/release-notes/2.4.0.html)
- [Percona build instructions](https://docs.percona.com/pg-stat-monitor/install.html)
- [Upstream repository](https://github.com/percona/pg_stat_monitor)
- [Upstream 2.4.0 tag](https://github.com/percona/pg_stat_monitor/tree/2.4.0)
