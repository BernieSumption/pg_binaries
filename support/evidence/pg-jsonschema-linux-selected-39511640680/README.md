# pg_jsonschema 0.3.4 Linux arm64 selected attempt

[Run 39511640680](https://github.com/BernieSumption/pg_binaries/actions/runs/39511640680) on 2026-10-20 targeted PostgreSQL 18.6 with source revision `22bbf2102656e239d129cfc48de3bc77d86ad075`. PostgreSQL and pg_jsonschema compiled, but archive packaging stopped when the isolated build container ran the component-inventory checker. The checker imported `create_pg_jsonschema_component_inventory`, while the Dockerfile had copied that module under a hyphenated filename. No extension archive checksum sidecar was produced, so the separate verifier could not run the final-archive suite.

The build and verifier Dockerfiles now retain the generator's importable Python filename, and the build script invokes that path. An isolated copy-layout import check and 23 focused Python tests pass locally. Rerun this exact selected target before expanding pg_jsonschema coverage; no publication-profile result passed in this attempt.
