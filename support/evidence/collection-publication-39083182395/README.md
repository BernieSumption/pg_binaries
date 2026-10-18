# collection 1.1.1 and 2.1.3 Linux publication verification

[Run 39083182395](https://github.com/BernieSumption/pg_binaries/actions/runs/39083182395) passed on native x86-64 and arm64 GitHub runners against PostgreSQL 18.6. Each job built both unmodified, pinned collection releases, assembled their final archives with the exact PostgreSQL core, relocated them into Alpine 3.22, exercised associative-array operations and checked ELF dependency closure. The 2.1.3 test also used sparse integer keys.

The [x86-64](x86_64/attempt.json) and [arm64](arm64/attempt.json) attempts, receipts, static reports and four imported verification records bind these outcomes to the final archive hashes and current profile. Other PostgreSQL versions and platforms remain unverified. Dependency-source provenance remains a separate release-eligibility review item.
