# Selected Linux archive-layout trial

[GitHub Actions run 39172271421](https://github.com/BernieSumption/pg_binaries/actions/runs/39172271421) passed at source revision `cd5acba36b59570b008eafd611a8ac4aad88d9c4`. It selected PostgreSQL 17.11 and pgvector 0.8.7 for Linux x86-64, built a new core, and passed the relocated Alpine archive suite, no-host-user-space check and diagnostic probes. The uploaded artifact retained one core archive and adjacent checksum sidecar at `_temp/bundle/pilot/`, allowing the candidate-discovery code to identify a unique pair.

The [independently imported core record](../verification/postgresql-17.11-linux-x86_64-current-39172271421.json) binds SHA-256 `5b91fe8c572192adb52539f592e6c721550406859b55ebddcf9ae8c35234367f`; the [pgvector record](../verification/pgvector-0.8.7-postgresql-17.11-linux-x86_64-current-39172271421.json) binds extension SHA-256 `02a73316cfa321dc76495f5e026cb93201d43353d4e3f314cd173d7dd087d6e1` and the same core. Both passed the current profile revision `46898f825bff62cfa774a85fe6808652dc7d580cac3a5eb04eb99b10feff6d68`. [Retained evidence](linux-publication-39172271421/postgresql-17.11/x86_64/current-steps.json) includes the receipt, static analysis, symbols and diagnostics.

This run establishes a discoverable candidate. A subsequent selected run must still demonstrate checksum- and input-checked reuse.
