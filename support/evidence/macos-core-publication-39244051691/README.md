# macOS PostgreSQL core-only trial 39244051691

[Run 39244051691](https://github.com/BernieSumption/pg_binaries/actions/runs/39244051691) built PostgreSQL 18.6 for macOS arm64 and checked the final archive on a separate runner. The core-only archive suite failed when the shared verifier tried to create `vector`, which is absent from a PostgreSQL-only archive. The dSYM and diagnostic checks passed. The final publication gate failed as required.

The [raw attempt](postgresql-18.6/arm64/publication-attempt.json), [step outcomes](postgresql-18.6/arm64/publication-steps.json) and [diagnostic report](postgresql-18.6/arm64/diagnostics.json) were imported from the run artifact. The diagnostic report's PostgreSQL archive SHA-256, `fdbab37202e64ec3aadb8e8693a9209ea4c2ba0c23c0198d271682f1fb8c9e8d`, matches the downloaded archive. The retained diagnostic bytes match the CI artifact.
