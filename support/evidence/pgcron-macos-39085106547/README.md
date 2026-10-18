# pg_cron Apple Silicon macOS dependency-closure attempt

[Run 39085106547](https://github.com/BernieSumption/pg_binaries/actions/runs/39085106547) again built and packaged unmodified pg_cron 1.6.8 against the checksum-pinned PostgreSQL 18.6 Apple Silicon core. The isolated core [static report](static-analysis.json) passed with no findings; the extension-specific check then found that `pg_cron.dylib` imports `@rpath/libpq.5.dylib` while neither the module nor `bin/postgres` declares an `LC_RPATH` that resolves it. The module archive [checksum sidecar](pg_cron-1.6.8-postgresql-18.6-macos-arm64.tar.gz.sha256) is retained. The check stopped before `CREATE EXTENSION` or the scheduled-job probe.

The next candidate uses PGXS `PG_LDFLAGS` at link time to add `@loader_path` to the module's run paths. It does not change upstream source or rewrite the linked binary; CI must verify the emitted load command and runtime behavior.
