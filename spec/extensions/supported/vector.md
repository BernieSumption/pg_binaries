# vector

`CREATE EXTENSION vector` installs [pgvector](https://github.com/pgvector/pgvector),
which supplies vector types and indexes under the
[PostgreSQL licence](https://github.com/pgvector/pgvector/blob/v0.8.7/LICENSE).

## Versions and compatibility

The [changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md)
identifies candidates 0.8.2 (2026-02-25) through 0.8.7 (2026-10-01); 0.8.1
predates the cutoff. The 0.8 line supports PostgreSQL 13+ and gained PostgreSQL
18 support before the cutoff, giving an expected project range of 15–18.
Apply the [shared build and verification rules](../README.md).

No breaking schema transition within 0.8.2–0.8.7 has been established. Inspect
tagged type, operator, index and update definitions during release intake;
the changelog includes index correctness fixes that make exact versions relevant.

## Dependencies and resources

No companion SQL extension, preload setting, external service or runtime dataset
is required. Embeddings and indexes are application data.

Unix builds must clear `OPTFLAGS`: the
[tagged Makefile](https://github.com/pgvector/pgvector/blob/v0.8.7/Makefile)
otherwise uses `-march=native`, which can require the build machine's CPU features.

## Evidence and remaining tests

Vector 0.8.7 built against PostgreSQL 18.6 passed relocation, extension creation
and an HNSW query on x86-64 Linux, Intel macOS and x86-64 Windows. Windows used
a runner with the Visual C++ runtime installed, so it does not establish
operation on a stock Windows installation. See [pilot evidence](../../evidence.md).

The recorded artifact sizes combine PostgreSQL and vector; vector's separate
size remains unmeasured. Add type/operator and IVFFlat DDL fixtures alongside
HNSW, and test applicable update SQL using the final relocated archives.
