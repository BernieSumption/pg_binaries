# pg_jsonschema macOS current-profile refresh, 19 October 2026

[Run 39196299612](https://github.com/BernieSumption/pg_binaries/actions/runs/39196299612) passed at source revision `898aeaaf5ea75d3f02cf1766791633194e8758a6`. The selected path built pg_jsonschema 0.3.4 for PostgreSQL 15.19, 16.15, 17.11 and 18.6 on both macOS arm64 and x86-64. Every target passed final-archive SQL and static analysis on a fresh runner.

The shared macOS core-target helper had changed since the previous matrix, invalidating its profile revisions. All eight publication artifacts from this run were downloaded and independently imported with the exact source revision. The 80 retained files, ten per target, matched the CI copies byte-for-byte. Each record's profile revision matches the current profile.
