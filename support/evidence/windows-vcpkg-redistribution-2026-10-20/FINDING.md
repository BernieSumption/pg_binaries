# Selected Windows core archive checks

These findings record notice inventory checks against exact successful PostgreSQL core archives. A complete notice bundle does not resolve the aggregate redistribution review while source obligations remain unknown.

## PostgreSQL 18.6, run 39562140440

The archive `postgresql-18.6-windows-x86_64.tar.gz` has SHA-256 `dc6b7bbc1df71183ea79cc7a36c1f410d495446aaef4f96ab1adab3b547b7b17`. Its `LICENSES/vcpkg-dll-map.json` maps 16 DLLs to eight ports: ICU 78.3, libiconv 1.19, libxml2 2.15.3, libxslt 1.1.45, LZ4 1.10.0, OpenSSL 3.6.3, zlib 1.3.2 and zstd 1.5.7. The map's DLL set matches the runtime payload paths in `LICENSES/inventory.json` exactly.

All 16 additional notice files declared by the inventory exist in the archive, and each file's bytes occur in `LICENSES/dependencies/NOTICE-BUNDLE.txt`. This includes the xxHash, libxml2 dict/list and zstd divsufsort notices. The aggregate `bundled-runtime-dependencies` review remains `pending` with `source_obligation: unknown`; libiconv source delivery remains unresolved.

The archive is retained in the successful build artifact for [run 39562140440](https://github.com/BernieSumption/pg_binaries/actions/runs/39562140440). Its verification record is [postgresql-18.6-windows-x86_64-current-39562140440.json](../../verification/postgresql-18.6-windows-x86_64-current-39562140440.json); the repository importer retained the associated publication evidence under `support/evidence/windows-publication-39562140440/postgresql-18.6/`.

## PostgreSQL 16.15, run 39570352068

The archive `postgresql-16.15-windows-x86_64.tar.gz` has SHA-256 `d2953539433a05f551a53bd85b76e05516632e9d5b105de422db72b948c6f805`. Its DLL map covers the same 16-DLL, eight-port set as the 18.6 archive, and matches the runtime payload paths exactly. Each additional notice file declared in `LICENSES/inventory.json` exists and its bytes occur in `LICENSES/dependencies/NOTICE-BUNDLE.txt`. The aggregate dependency review remains `pending` with `source_obligation: unknown`.

The exact archive and successful verification record are retained from [run 39570352068](https://github.com/BernieSumption/pg_binaries/actions/runs/39570352068). The record is [postgresql-16.15-windows-x86_64-current-39570352068.json](../../verification/postgresql-16.15-windows-x86_64-current-39570352068.json); the importer retained publication evidence under `support/evidence/windows-publication-39570352068/postgresql-16.15/`.

## PostgreSQL 15.19, run 39570352294

The archive `postgresql-15.19-windows-x86_64.tar.gz` has SHA-256 `b1793090085453fdcba4a7af14084ea5e1695b50390833d3c997840f78a9a809`. Its 16-entry DLL map matches the runtime payload paths exactly. All 16 additional notice files declared by the inventory exist in the archive, and each file's bytes occur in the notice bundle. The aggregate dependency review remains `pending` with `source_obligation: unknown`.

The exact archive and successful verification record are retained from [run 39570352294](https://github.com/BernieSumption/pg_binaries/actions/runs/39570352294). The record is [postgresql-15.19-windows-x86_64-current-39570352294.json](../../verification/postgresql-15.19-windows-x86_64-current-39570352294.json); the importer retained publication evidence under `support/evidence/windows-publication-39570352294/postgresql-15.19/`.

## PostgreSQL 17.11, run 39570353538

The archive `postgresql-17.11-windows-x86_64.tar.gz` has SHA-256 `891dcdf2889dd3b08b07a61c84ffdd65f37a4ba46fc46508d6dd53be8826864e`. Its 16-entry DLL map matches the runtime payload paths exactly. All 16 additional notice files declared by the inventory exist in the archive, and each file's bytes occur in the notice bundle. The aggregate dependency review remains `pending` with `source_obligation: unknown`.

The exact archive and successful verification record are retained from [run 39570353538](https://github.com/BernieSumption/pg_binaries/actions/runs/39570353538). The record is [postgresql-17.11-windows-x86_64-current-39570353538.json](../../verification/postgresql-17.11-windows-x86_64-current-39570353538.json); the importer retained publication evidence under `support/evidence/windows-publication-39570353538/postgresql-17.11/`.
