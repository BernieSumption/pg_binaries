# collection 1.1.1 and 2.1.3 Linux PostgreSQL 18.6 publication verification

[Run 39085258918](https://github.com/BernieSumption/pg_binaries/actions/runs/39085258918) passed the selected-minor collection profile on native x86-64 and arm64 Linux runners against PostgreSQL 18.6. Each job built the two pinned upstream releases against its exact core archive, assembled final extension archives, relocated the pair into Alpine 3.22, tested associative arrays including sparse integer keys for 2.1.3, and checked ELF dependency closure.

The [x86-64](x86_64/attempt.json) and [arm64](arm64/attempt.json) attempts, receipts, static reports and four imported current-profile records bind these results to final archive hashes. PostgreSQL 15.19, 16.15 and 17.11 still need imported results; macOS and Windows coverage remain separate work.
