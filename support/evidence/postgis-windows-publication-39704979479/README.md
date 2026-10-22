# Windows PostGIS 16.15 verification attempt

[Run 39704979479](https://github.com/BernieSumption/pg_binaries/actions/runs/39704979479) built PostGIS 3.6.4 against PostgreSQL 16.15 on 2026-10-22. The separate Windows runner passed final-archive and PE inspection, then failed before emitting a receipt or SQL-extension records. The emitter looked for `postgis/metadata.json`; the builder placed `metadata.json` at the archive root. The [verification job log](verify-job.log) records the error, and [verification output](verification/) retains the available SQL probe, PE and static reports. This attempt provides no passing publication record.

Commit `c907df4e` changes the emitter to read the archive-root member and tests that layout. Run 39707138322 is the first corrected attempt; its result must be imported separately if it passes.
