# pgAudit Linux feasibility attempt

[Run 39073599766](https://github.com/BernieSumption/pg_binaries/actions/runs/39073599766) attempted pgAudit 18.0 against PostgreSQL 18.6 on x86-64 and arm64 at revision `d088739f808018f914b1ff9f9de3cd4aa2449e0d`. The retained `step-outcomes.json` files are copied from each run artifact and identify the run, revision, versions, architecture and step results: core build succeeded, pgAudit build failed, and verification and archive identity were skipped on both targets.

The build log shows compilation stopped because PostgreSQL's server header `libpq-be.h` includes `openssl/ssl.h`, which was absent from the build container. The pgAudit Dockerfile did not install `libssl-dev`. No pgAudit archive was produced, no archive-bound verification succeeded, and this attempt provides no Linux feasibility pass. See the [failed build logs](https://github.com/BernieSumption/pg_binaries/actions/runs/39073599766).
