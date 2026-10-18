# pgTAP macOS PostgreSQL 17 and 18 refresh evidence

The four archive-bound pgTAP 1.3.4 refresh jobs passed on 2026-10-18: PostgreSQL 17.11 [arm64 run 39122055680](https://github.com/BernieSumption/pg_binaries/actions/runs/39122055680) and [Intel run 39122055613](https://github.com/BernieSumption/pg_binaries/actions/runs/39122055613), plus PostgreSQL 18.6 [arm64 run 39122055625](https://github.com/BernieSumption/pg_binaries/actions/runs/39122055625) and [Intel run 39122055708](https://github.com/BernieSumption/pg_binaries/actions/runs/39122055708). The importer checked each final pgTAP archive and exact pinned core archive against its receipt and verification record. All four jobs passed relocated SQL assertions and static analysis.

The records establish tested candidate behavior. Core dependency redistribution review remains open, so the archives are release-ineligible.
