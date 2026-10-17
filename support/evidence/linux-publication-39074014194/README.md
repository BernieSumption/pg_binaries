# Linux PostgreSQL 18.6 publication evidence

[Linux publication run 39074014194](https://github.com/BernieSumption/pg_binaries/actions/runs/39074014194) passed the current publication profiles on x86-64 and arm64 at source, build and test revision `486c0b07ef4cad4b7dafcaaee352fefa5e12a5e8`.

The retained evidence covers PostgreSQL 18.6, pgvector 0.8.7, PostGIS 3.6.4 and its four SQL names, TIGER Geocoder 2025.2, HypoPG 1.4.3, and pgTAP 1.3.4. It contains 18 passed verification records, ten profile receipts, and ten static-analysis reports. The importers checked archive SHA-256 sidecars and receipt/record archive identities, prerequisite and assembled-core digests, Alpine 3.22 runtime evidence, and compatibility with the current revisions of all ten architecture-specific publication profiles.

Per-project receipts and static reports are under the matching `support/evidence/*-publication-39074014194/<architecture>/` directories. Archive-bound records are under `support/verification/` with run ID `39074014194`.
