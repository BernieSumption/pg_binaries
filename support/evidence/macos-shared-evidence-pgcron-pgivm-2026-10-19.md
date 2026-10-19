# macOS shared evidence helper: pg_cron and pg_ivm

The pg_cron and pg_ivm macOS emitters and importers now use the shared checksum, bounded JSON and retention helpers. Their six affected publication profiles include the helper source. Each run below passed its archive suite and static checks at commit `04cda9dcc0ef7a59bf75a24cbeacd982832cb42a`:

- pg_cron 1.6.8, PostgreSQL 18.6: [arm64 run 39178722070](https://github.com/BernieSumption/pg_binaries/actions/runs/39178722070) and [x86-64 run 39178721872](https://github.com/BernieSumption/pg_binaries/actions/runs/39178721872).
- pg_ivm 1.16, PostgreSQL 17.11: [arm64 run 39178722005](https://github.com/BernieSumption/pg_binaries/actions/runs/39178722005) and [x86-64 run 39178722078](https://github.com/BernieSumption/pg_binaries/actions/runs/39178722078).
- pg_ivm 1.16, PostgreSQL 18.6: [arm64 run 39178721954](https://github.com/BernieSumption/pg_binaries/actions/runs/39178721954) and [x86-64 run 39178722052](https://github.com/BernieSumption/pg_binaries/actions/runs/39178722052).

For each run, the exact PostgreSQL artifact named by its workflow and the final extension artifact were downloaded. The importer validated the archive-bound receipts and retained the record, static report and probe output. All six retained records match the corresponding downloaded CI record byte for byte. These results cover the current profiles for these six targets; other projects and targets require their own runs.
