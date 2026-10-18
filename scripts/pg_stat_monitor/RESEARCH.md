# pg_stat_monitor 2.4.0 Linux trial

`pg_stat_monitor` records PostgreSQL query statistics and exposes them through the `pg_stat_monitor` SQL extension. Percona documents PostgreSQL 14 and later compatibility, and its 2.4.0 release notes say the release adds PostgreSQL 19 beta 3 support. The selected trial target is PostgreSQL 18.6 on Linux x86-64.

The upstream project is maintained by Percona and distributed under the PostgreSQL License, as recorded in its repository metadata. Its documented source build requires Git, make, GCC and `pg_config`; PGXS supports building against the selected PostgreSQL installation. The build downloads the upstream tag archive, checks SHA-256 `21e4fe737e8eeb5a5ae96df781c61e3ceb74d481041a136e42503be636dc9fe8`, and records its resolved commit `2de2db763db9f590cd28159741c36b41f66eb985` in package metadata.

This trial does not add `pg_stat_monitor` to `support.json` or claim advertised support. The fixed Alpine verifier checks archive structure, dependencies, ordinary-user startup, query monitoring, and relocation with the supplied PostgreSQL 18.6 archive. Passing run [39138856521](https://github.com/BernieSumption/pg_binaries/actions/runs/39138856521) completed in 46 seconds. Its archive SHA-256 is `83cd9daab190109ca5f09c564f0968b20cd06df720ffe13c2cf818607276285c`. The Alpine static report inspected 185 ELF files and passed dependency closure.

## Trial iterations

The build command in each run was `bash scripts/pg_stat_monitor/linux-build.sh "$RUNNER_TEMP/core/pilot" "$RUNNER_TEMP/extension"`; the verifier command was `bash scripts/pg_stat_monitor/linux-verify.sh "$RUNNER_TEMP/extension" "$RUNNER_TEMP/core/pilot"`.

- [39138548058](https://github.com/BernieSumption/pg_binaries/actions/runs/39138548058), 31 runner seconds: source tag checkout failed at `git describe --tags --exact-match HEAD` because the shallow fetch had no tag names. Replaced the checkout with a source tarball and pinned its SHA-256 and resolved commit.
- [39138632308](https://github.com/BernieSumption/pg_binaries/actions/runs/39138632308), 37 runner seconds: source checksum passed, then extraction failed because the archive directory is `pg_stat_monitor-2.4.0`. Updated the build to enter that directory.
- [39138725039](https://github.com/BernieSumption/pg_binaries/actions/runs/39138725039), 27 runner seconds: compilation lacked `openssl/ssl.h`, included by the supplied PostgreSQL headers. Added `libssl-dev` to the disposable builder image.
- [39138788438](https://github.com/BernieSumption/pg_binaries/actions/runs/39138788438), 31 runner seconds: build passed; Alpine verification could not find `pg_stat_monitor.sha256`. Renamed the checksum sidecar to the fixed verifier's required name.
- [39138856521](https://github.com/BernieSumption/pg_binaries/actions/runs/39138856521), 46 runner seconds: build and Alpine verification passed.

An initial `gh workflow run` attempt returned HTTP 404 because GitHub did not expose this workflow from the default branch. Root added a path-filtered push trigger to the trial workflow on `spike`; no further supervision was needed.

## Sources

- [Percona pg_stat_monitor 2.4.0 release notes](https://docs.percona.com/pg-stat-monitor/release-notes/2.4.0.html)
- [Percona build instructions](https://docs.percona.com/pg-stat-monitor/install.html)
- [Upstream repository](https://github.com/percona/pg_stat_monitor)
- [Upstream 2.4.0 tag](https://github.com/percona/pg_stat_monitor/tree/2.4.0)
