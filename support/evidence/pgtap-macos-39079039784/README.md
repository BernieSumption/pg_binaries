# pgTAP Apple Silicon feasibility result

[Run 39079039784](https://github.com/BernieSumption/pg_binaries/actions/runs/39079039784) passed the macOS arm64 pgTAP 1.3.4 feasibility probe at revision `5af9539`. It checked the PostgreSQL 18.6 core archive from run 39075939632 (SHA-256 `853e0eafb3570378225d2ea16247c9de31770f85df5230509885df2ca5e89d67`), fetched checksum-pinned unmodified pgTAP source, and used upstream PGXS rules to generate and install its SQL and documentation. The emitted extension archive has SHA-256 `a04002790ec210363597af7eec0723f52b9af7ac6451792da527f7894ac7c86b` and includes its upstream licence notice and inventory. The [full CI log](build-log.txt) records source checks, packaging and runtime verification.

After assembling the checked archives and moving the installation, the probe passed `CREATE EXTENSION pgtap` and four [schema and query assertions](probe-output.txt). The [Mach-O report](static-analysis.json) found no loader-closure or minimum-OS violation and binds both archive hashes. The archive itself is retained as a temporary CI artifact, not in Git.

This establishes one exact core/extension combination's feasibility. It does not provide final-byte publication records across the selected macOS targets.
