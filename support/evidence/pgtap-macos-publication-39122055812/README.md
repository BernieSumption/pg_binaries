# pgTAP macOS PostgreSQL 15 and 16 publication evidence

The four archive-bound pgTAP 1.3.4 jobs passed on 2026-10-18: PostgreSQL 15.19 [arm64 run 39122055791](https://github.com/BernieSumption/pg_binaries/actions/runs/39122055791) and [Intel run 39122055786](https://github.com/BernieSumption/pg_binaries/actions/runs/39122055786), plus PostgreSQL 16.15 [arm64 run 39122055812](https://github.com/BernieSumption/pg_binaries/actions/runs/39122055812) and [Intel run 39122055728](https://github.com/BernieSumption/pg_binaries/actions/runs/39122055728). The importer checked each final pgTAP archive and exact pinned core archive against its receipt and verification record. All four jobs passed relocated SQL assertions and static analysis; PostgreSQL 15's staged SQL and documentation layout worked on both architectures.

The records establish tested candidate behavior. Core dependency redistribution review remains open, so the archives are release-ineligible.
