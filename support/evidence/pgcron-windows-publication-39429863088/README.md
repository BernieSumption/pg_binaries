# pg_cron 1.6.8 Windows publication verification on PostgreSQL 17.11

[Run 39429863088](https://github.com/BernieSumption/pg_binaries/actions/runs/39429863088) passed the selected Windows build and separate final-archive verification. The verifier checked PDBs against the downloaded archives, ran relocated PostgreSQL and pg_cron, and observed a scheduled background-worker job complete.

The imported current-profile record binds pg_cron SHA-256 `75164faf766ad7c419d2ee55c404d6ac500c931d313e6ed966261c7f3ff17779` to the exact PostgreSQL 17.11 core from selected run 39425253610, SHA-256 `95863d1ef79c2d1e55f3a204570b1b1610285a3068ac74edd743d48a94c89a8d`. The importer validated the downloaded archive sidecars, receipt, probe output, PE report, PDB index, attempt and current-profile record before retaining the evidence.
