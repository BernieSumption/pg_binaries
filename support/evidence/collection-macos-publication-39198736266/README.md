# Collection selected macOS trial, 19 October 2026

[Run 39198736266](https://github.com/BernieSumption/pg_binaries/actions/runs/39198736266) passed at revision `d972940` for PostgreSQL 18.6 on macOS arm64. The selected target built both collection 1.1.1 and 2.1.3 from unmodified upstream source against one checked PostgreSQL core archive. A fresh runner relocated each final archive, checked Mach-O dependencies, exercised schema SQL, and retained archive-bound publication records.

The publication artifact was independently imported with the exact source revision. Its eleven retained files, including both verification records, matched the CI copies byte-for-byte. The selected workflow's other seven PostgreSQL/architecture targets still require CI verification. The profile will change when the legacy path is removed, so this first trial will then be historical evidence.
