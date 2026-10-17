# pgAudit Linux verification failure

[Run 39074014070](https://github.com/BernieSumption/pg_binaries/actions/runs/39074014070) built pgAudit 18.0 and PostgreSQL 18.6 on x86-64 and arm64, then failed during the Alpine 3.22 verification step on both architectures. The failed logs show `Broken pipe` and exit code 141 from the `psql | grep` audit-log check: `grep` exits after finding a matching line, and `psql` receives SIGPIPE while continuing to write under `set -o pipefail`.

The retained raw attempt manifests identify run `39074014070`, revision `486c0b07ef4cad4b7dafcaaee352fefa5e12a5e8`, and both architecture outcomes. Core and pgAudit builds succeeded, verification failed, and archive identity was skipped. This run has no passing verification or archive-bound publication result. See the [failed run logs](https://github.com/BernieSumption/pg_binaries/actions/runs/39074014070).
