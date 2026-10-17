# macOS x86-64 pilot evidence, run 39068360742

[GitHub Actions run 39068360742](https://github.com/BernieSumption/pg_binaries/actions/runs/39068360742) built PostgreSQL 18.6 and pgvector 0.8.7 for macOS x86-64 at source, build and test revision `3a600990f3deed8e32c57b249c31653d319b50b2`. Fresh-runner verification passed the `macos-pilot-x86_64` pilot profile on macOS 15.7.9, image `macos15/20260824.0482.1`. The retained records under `support/verification/` identify that revision and both final archive checksums.

The downloaded archives matched their checksum sidecars:

- `postgresql-18.6-macos-x86_64.tar.gz`: `36a2f9297d05b88125c697a6e2f73ee61ae2b3ae9edbd95d20ed3d42ffa6e91f`
- `pgvector-0.8.7-postgresql-18.6-macos-x86_64.tar.gz`: `6b48a2c26171641879b989f348e77a1644774fd9089c78e70404dbe86188f5a5`

The core archive's licence inventory maps seven components to resolved redistribution reviews: PostgreSQL, ICU, libxml2, libxslt, LZ4, OpenSSL and Zstandard. The pgvector inventory maps pgvector to a resolved review. `static-analysis.json` passed with no findings across 133 Mach-O files, each declaring macOS 11.0 as its minimum target. `index.json` lists 124 module-to-dSYM associations; every archive checksum in the index matches the downloaded bytes. The dSYM payloads and archives remain in the short-lived CI artifact rather than this compact evidence directory.

This is pilot evidence for the earlier archive layout. The pgvector archive contains `LICENSES/inventory.json`; a subsequent build change packages `LICENSES/pgvector-inventory.json` so installation can copy it unchanged beside the core inventory. The new layout and publication profile require fresh archive-bound verification. No compiled artifact was executed locally while retaining these records.
