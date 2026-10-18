# collection 1.1.1 and 2.1.3 Linux arm64 feasibility

[Run 39082901624](https://github.com/BernieSumption/pg_binaries/actions/runs/39082901624) passed on a standard arm64 Linux runner at source revision `01e7bd54477999063d6bbdde6c60a2965f57c536`. It built both selected collection releases from checksum-pinned, unmodified upstream source against PostgreSQL 18.6, then relocated each final archive with its exact core into Alpine 3.22. Both versions passed ELF dependency inspection, extension creation, associative-array operations and persistence across connections; version 2.1.3 also passed sparse integer-key checks.

The [attempt manifest](attempt.json) binds both extension archive hashes and the core hash to the source revision and outcomes. The [1.1.1](collection-1.1.1-static-analysis.json) and [2.1.3](collection-2.1.3-static-analysis.json) reports retain the dependency inspection. This is feasibility evidence; publication profiles and other selected targets remain open.
