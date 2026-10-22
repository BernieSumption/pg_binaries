# Exact-core verification attempts

The first-release candidate assembled selected PostgreSQL archives whose checksums differ from those in 42 otherwise passing extension records. These 2026-10-22 dispatches request fresh final-archive verification against the selected cores. They are attempts, not passing evidence. Import each result only after its archive, selected core, profile and prerequisite checks pass.

Linux requests:

- PostgreSQL 16.15 x86-64: Address Standardizer [39706107519](https://github.com/BernieSumption/pg_binaries/actions/runs/39706107519).
- PostgreSQL 17.11 x86-64: Address Standardizer [39706108137](https://github.com/BernieSumption/pg_binaries/actions/runs/39706108137), collection 1.1.1 [39706107950](https://github.com/BernieSumption/pg_binaries/actions/runs/39706107950), collection 2.1.3 [39706108340](https://github.com/BernieSumption/pg_binaries/actions/runs/39706108340).
- PostgreSQL 18.6 arm64: Address Standardizer [39706107056](https://github.com/BernieSumption/pg_binaries/actions/runs/39706107056), collection 1.1.1 [39706107698](https://github.com/BernieSumption/pg_binaries/actions/runs/39706107698), collection 2.1.3 [39706107438](https://github.com/BernieSumption/pg_binaries/actions/runs/39706107438).
- PostgreSQL 18.6 x86-64: Address Standardizer [39706123860](https://github.com/BernieSumption/pg_binaries/actions/runs/39706123860), HypoPG [39706123215](https://github.com/BernieSumption/pg_binaries/actions/runs/39706123215), PostGIS [39706123604](https://github.com/BernieSumption/pg_binaries/actions/runs/39706123604), collection 1.1.1 [39706123864](https://github.com/BernieSumption/pg_binaries/actions/runs/39706123864), collection 2.1.3 [39706124360](https://github.com/BernieSumption/pg_binaries/actions/runs/39706124360), pg_cron [39706124102](https://github.com/BernieSumption/pg_binaries/actions/runs/39706124102), pg_ivm [39706124413](https://github.com/BernieSumption/pg_binaries/actions/runs/39706124413), pg_jsonschema [39706123345](https://github.com/BernieSumption/pg_binaries/actions/runs/39706123345), pgAudit [39706124001](https://github.com/BernieSumption/pg_binaries/actions/runs/39706124001), pgTAP [39706124094](https://github.com/BernieSumption/pg_binaries/actions/runs/39706124094). TIGER Geocoder follows a passing PostGIS archive for this core.

macOS requests:

- PostgreSQL 15.19 arm64: PostGIS [39706147862](https://github.com/BernieSumption/pg_binaries/actions/runs/39706147862).
- PostgreSQL 16.15 and 17.11 arm64: TIGER Geocoder [39706148486](https://github.com/BernieSumption/pg_binaries/actions/runs/39706148486) and [39706148084](https://github.com/BernieSumption/pg_binaries/actions/runs/39706148084). These workflows also produce and verify their PostGIS prerequisites; import those records only when their exact hashes match the selected core.
- PostgreSQL 18.6 x86-64: Address Standardizer [39706147996](https://github.com/BernieSumption/pg_binaries/actions/runs/39706147996) and pgAudit [39706150529](https://github.com/BernieSumption/pg_binaries/actions/runs/39706150529).
