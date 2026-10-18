# pgvector separate Linux build trial

GitHub Actions run [39161803777](https://github.com/BernieSumption/pg_binaries/actions/runs/39161803777) completed successfully on 2026-10-18. The `build` job ran from 20:06:39 to 20:07:18 UTC (workflow run started at 20:06:36 UTC), on commit `a030cba905409705d9e6484762b863bda1d0e71c`. Its build and archive inspection steps both passed.

The seven-day artifact contained `pgvector-0.8.7-postgresql-18.6-linux-x86_64.tar.gz` and its `.sha256` sidecar. The sidecar records SHA-256 `68f6537437c73e7c5e388d58543f805f82c4bd5a926475428143df1d12a9c0b0`, matching the independently calculated digest of the downloaded archive. The archive has 52 entries under exactly two roots: `metadata.json` and `pgvector/`.

The payload consists of `pgvector/lib/vector.so`, the extension control file and versioned SQL files under `pgvector/share/extension/`, and `pgvector/LICENSES/pgvector.txt` plus `pgvector/LICENSES/pgvector-inventory.json`. The inventory identifies pgvector 0.8.7, payload paths `lib/vector.so` and `share/extension`, and the retained PostgreSQL-style license. No unexpected archive roots or payload paths were found.

Archive metadata identifies project `pgvector`, version `0.8.7`, SQL name `vector`, PostgreSQL `18.6`, platform `linux`, architecture `x86_64`, and source revision `a030cba905409705d9e6484762b863bda1d0e71c`. Its source archive URL and SHA-256 match the pgvector 0.8.7 pin in `support.json` (`cac0b10c360f05b2d521200105ba3697e773d4cd3731f5a915a7e37ebe0bea85`). Its core archive basename is `postgresql-18.6-linux-x86_64.tar.gz`; its SHA-256 matches the expected `ca1773eeca3e083cf1c170e76d3e2191391ac3cac405b7db737a548a2a00c2df`.

This evidence establishes that the pinned Linux build completed and that the produced archive structure, checksum, source identity, core identity, platform metadata, and license inventory are consistent. It does not establish runtime loading or extension behavior in PostgreSQL; no runtime verification was performed in this trial.
