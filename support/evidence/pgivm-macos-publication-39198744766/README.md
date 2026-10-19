# pg_ivm selected macOS trial, 19 October 2026

[Run 39198744766](https://github.com/BernieSumption/pg_binaries/actions/runs/39198744766) passed at revision `d972940` for pg_ivm 1.16 and PostgreSQL 18.6 on macOS arm64. It built against a checked PostgreSQL core archive, then a fresh runner relocated the final archives, checked Mach-O dependencies and exercised IMMV schema SQL.

The publication and build artifacts were independently imported with the exact source revision. All five retained files, including the verification record, matched the CI copies byte-for-byte. The other three selected PostgreSQL/architecture targets still require CI verification. The profile will change when the legacy path is removed, so this first trial will then be historical evidence.
