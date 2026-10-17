# macOS arm64 pilot evidence, run 39068360727

GitHub Actions run [39068360727](https://github.com/BernieSumption/pg_binaries/actions/runs/39068360727) built PostgreSQL 18.6 and pgvector 0.8.7 for macOS arm64 at source/build/test revision `3a600990f3deed8e32c57b249c31653d319b50b2`. Its verification records report `passed` for the `macos-pilot-arm64` `pilot-smoke` profile on clean macOS 15.7.9, image `macos15/20260907.0337.1`.

The archive sidecars matched locally recomputed SHA-256 values:

- `postgresql-18.6-macos-arm64.tar.gz`: `5110a35989ed89ef47b990820d29dcbb956a3a578aa977c6ac38096fae19eb89`
- `pgvector-0.8.7-postgresql-18.6-macos-arm64.tar.gz`: `8a3b82e5d69cd6aaf4f9d0155c187ddb7702b5761848363d37ae279f7c5e6ee4`

Both archives contain source identity metadata with source URLs, source archive hashes and source revision. Their license inventories contain payload mappings and resolved redistribution reviews. The PostgreSQL archive maps seven components (PostgreSQL, ICU, libxml2, libxslt, LZ4, OpenSSL and zstd); the pgvector archive maps pgvector 0.8.7. All recorded reviews state that the applicable license text is included and no source delivery is required.

`static-analysis.json` is the CI Mach-O report: it passed with no findings across 133 arm64 files, all declaring macOS 11.0 as their minimum OS. `index.json` records 124 arm64 module-to-dSYM associations for the two archive hashes (37 executables and 87 libraries/modules). The index and CI verification record are retained; the dSYM payloads are not copied into this compact evidence directory.

These records document pilot smoke verification. They do not establish publication approval or authorize a public release. Binary execution and the smoke tests described above ran in the GitHub Actions macOS runner; this local review inspected archive metadata and hashes only and did not execute compiled binaries.
