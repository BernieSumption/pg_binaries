# HypoPG macOS PostgreSQL 17 and 18 publication evidence

The archive-bound HypoPG 1.4.3 jobs passed on 2026-10-18: PostgreSQL 17.11 [arm64 run 39123193536](https://github.com/BernieSumption/pg_binaries/actions/runs/39123193536), PostgreSQL 18.6 [arm64 run 39123193593](https://github.com/BernieSumption/pg_binaries/actions/runs/39123193593), and PostgreSQL 18.6 [Intel run 39123193520](https://github.com/BernieSumption/pg_binaries/actions/runs/39123193520). The importers checked the final HypoPG archives and exact pinned core archives against their receipts and verification records. Each job passed relocated hypothetical-index SQL and Mach-O inspection.

An earlier PostgreSQL 18.6 arm64 run 39123025094 also passed and was imported, but its profile revision predates the selected-major SQL probe. Its record is historical. Core dependency redistribution review remains open, so these archives are release-ineligible.
