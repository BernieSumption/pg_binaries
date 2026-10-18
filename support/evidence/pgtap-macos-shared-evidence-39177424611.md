# Shared macOS evidence helper trial

The [selected pgTAP macOS arm64 run 39177424611](https://github.com/BernieSumption/pg_binaries/actions/runs/39177424611) passed its build and fresh-runner verification jobs at source revision `44d6d0e3a0a58290e77112796d9811f29c4a9a8e`. The run used the shared checksum, bounded-JSON and collision-safe evidence helpers in the pgTAP emitter and importer. Its PostgreSQL 17.11 and pgTAP 1.3.4 final archives passed the relocated SQL suite and static analysis on macOS 15.7.9 arm64.

The downloaded build and publication artifacts were independently imported with `tools/import_pgtap_macos_publication.py`. The imported verification record matches the record inside the CI artifact byte for byte. It binds PostgreSQL archive SHA-256 `e2fe14b3967cd06f4e9695dac2d8649bc46a3e211a9fa63b0a686d3a53018d4b` and pgTAP archive SHA-256 `6a9c597bda328da08b45c621f2a08c7ddc4dbcc87cd99c5a3203bd18d2bde460` to the passed cases and current profile revision `c01b97c5401c05bcb2c222584bd49705212e480788b02346df9dc190532a553f`.

This proves the helper for one selected macOS project. Other active macOS emitters and importers still need migration and their own current-profile checks.
