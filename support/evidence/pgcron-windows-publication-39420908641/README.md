# pg_cron 1.6.8 Windows publication verification

[Run 39420908641](https://github.com/BernieSumption/pg_binaries/actions/runs/39420908641) passed a build of unmodified upstream pg_cron against the checked PostgreSQL 18.6 Windows core. A separate runner matched PDBs to final archive bytes, checked PE dependencies, relocated both archives, created the extension and observed a scheduled background-worker job complete. The imported passing record binds the extension SHA-256 `f966cd2513a0656f7aa45d5ecfb750598190f9736e673345c0d46ebc993fd574` to core SHA-256 `6c98dc1177ff11006009ee5a4f732c9d48db24f6da40551f63cdee0dfe9951d2` under the current selected profile.

The retained receipt, PE report, symbol index and probe output are in this directory. This verifies one selected target; other PostgreSQL versions and release-wide redistribution checks remain separate work.
