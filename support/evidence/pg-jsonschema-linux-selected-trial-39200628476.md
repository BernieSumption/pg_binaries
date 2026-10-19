# pg_jsonschema selected Linux trial, 19 October 2026

[Run 39200628476](https://github.com/BernieSumption/pg_binaries/actions/runs/39200628476) passed at source revision `a092c56` for pg_jsonschema 0.3.4, PostgreSQL 17.11 and Linux x86-64. The selected workflow built the extension in Docker against the pinned PostgreSQL core archive. A separate GitHub-hosted runner downloaded the final extension bytes, relocated them with that exact core archive in Alpine, ran the SQL probe and inspected ELF dependencies. The extension archive in the build and verification artifacts matched byte-for-byte.

The downloaded artifacts were independently imported using the exact source revision and the pinned core artifact from run 39082111630. All ten retained files matched the CI copies byte-for-byte. The passing current-profile record reports archive-suite and elf-closure passed. The plan, selection, build and verification jobs used about 6.1 elapsed runner-minutes in total, of which the Docker build used about 5.5 minutes.

This trial establishes target selection and fresh-runner verification for one Linux target. The emitter and importer still fix the core run ID and SHA-256 in source, and the other pg_jsonschema Linux targets still use the older publication workflows. Dynamic checked core selection and full target migration remain open.
