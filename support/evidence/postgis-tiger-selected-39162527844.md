# PostGIS and TIGER selected Linux trial attempt

[Run 39162527844](https://github.com/BernieSumption/pg_binaries/actions/runs/39162527844) on 2026-10-18 downloaded and checked the pinned PostgreSQL 18.6, pgvector 0.8.7, PostGIS 3.6.4 and TIGER 2025.2 Linux x86-64 archives from run 39075939610. The verifier step stopped immediately with `Permission denied` because the trial invoked the non-executable `scripts/linux/verify-combined.sh` directly. No Alpine verification phase ran and no archive-bound test claim follows. The scoped retry invokes that script through Bash.
