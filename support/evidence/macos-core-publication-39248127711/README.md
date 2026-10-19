# PostgreSQL 18.6 macOS arm64 core publication run 39248127711

[Run 39248127711](https://github.com/BernieSumption/pg_binaries/actions/runs/39248127711) passed selection, build, fresh-runner verification and the final publication gate. Its source revision was `4cb2de8db2d636429d7ffa5e45b9c40d87d1fc5f`; the exact-revision importer retained the archive-bound record and evidence. The PostgreSQL 18.6 macOS arm64 archive SHA-256 is `93f853292f3527279781a968ceba4660175d3e1bb1435ac048b8ceb4423b5019`. The record uses profile revision `ce66a7725abf62297282fded4e81e5b7da6c2286a43863ac62c87252de49ce70`.

The `archive-suite`, `diagnostics` and `symbols` cases passed on a clean macOS 15.7.9 arm64 verifier. The final gate required all three cases, the current-profile record, Mach-O dependency checks, dSYM checks and diagnostics to succeed; it passed. All six retained evidence files and the verification record match their copies in the CI verification artifact byte-for-byte.

GitHub identified the build artifact as `postgresql-macos-selected-18.6-arm64-build-39248127711` (artifact ID `12185239726`, ZIP SHA-256 `0a3b54245568b756357bf3bb193d44b591ae1e6e6cd13e0e1d16f1a5b2b3882c`) and the verification artifact as `postgresql-macos-selected-18.6-arm64-verification-39248127711` (artifact ID `12185554872`, ZIP SHA-256 `b99493208927eb7f7b519858d638a6984f8f6882958b2715dd5c9c4ca63625dd`). The archive checksum sidecar and all retained evidence bytes were checked against the corresponding downloaded CI artifact contents.

The run predates the macOS core profile-source change at `27c8934`, so this result is historical under the current profile. The current-profile fallback trial is [run 39253162889](https://github.com/BernieSumption/pg_binaries/actions/runs/39253162889).
