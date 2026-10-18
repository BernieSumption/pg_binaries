# PostgreSQL 15.19 macOS arm64 attempt, run 39091354837

[GitHub Actions run 39091354837](https://github.com/BernieSumption/pg_binaries/actions/runs/39091354837) built PostgreSQL 15.19 and installed pgvector 0.8.7 from pinned upstream sources, then failed before archive assembly. PGXS installed `vector.so`; `scripts/macos/build.sh` attempted to copy `vector.dylib` and exited with `cp: .../lib/vector.dylib: No such file or directory`. No final archive or archive-bound verification record came from this run.

The candidate correction copies the sole installed pgvector module under its actual filename and includes `.so` extension modules in the macOS symbol index. It needs fresh final-archive verification before this target can count as covered.
