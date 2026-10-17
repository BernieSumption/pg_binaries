# Linux test installer review

The Linux archive verifier must reproduce [the documented installation process](../../policies/install-process.md) using only the PostgreSQL and extension archives. This review compares `scripts/linux/verify-in-container.sh` at the ordinary-user relocation change with that procedure.

- The verifier checks archive checksums, extracts the PostgreSQL archive into a user-writable staging directory and extracts pgvector separately, all before running a PostgreSQL command.
- It reads the sibling `metadata.json` without copying it into the installation prefix. It rejects collisions other than directory merges, then copies only the contents of the project-named `pgvector/` payload into `postgresql/`, preserving relative paths and permissions.
- Extraction, payload merge and the prefix move run as `postgres`. The test starts PostgreSQL and exercises pgvector before the move, moves the prefix while the first server is stopped, and repeats schema and extension operations from the new path. It invokes packaged commands directly from `bin/`; the policy also allows adding that directory to `PATH`.
- The container creates the test account and writable directories. Those steps prepare the verifier environment; the extracted package requires no privileged registration, installer script or configuration generated from the build machine.

The review found that an earlier verifier moved the prefix as root even though extraction and merging used `postgres`. The move now uses `runuser -u postgres`. A local Docker run using the PostgreSQL 18.6 and pgvector 0.8.7 x86-64 archives from [CI run 38992702677](https://github.com/BernieSumption/pg_binaries/actions/runs/38992702677) passed the full archive verifier on Ubuntu 24.04 after the change. CI must rerun the changed test source on both architectures and OS endpoints before its retained records are current.
