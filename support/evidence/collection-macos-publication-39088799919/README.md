# collection macOS Apple Silicon publication run 39088799919

[Run 39088799919](https://github.com/BernieSumption/pg_binaries/actions/runs/39088799919) passed the current macOS arm64 collection profile for upstream 1.1.1 and 2.1.3 against the exact PostgreSQL 18.6 core archive. Both final extension archives passed relocated SQL probes and Mach-O dependency checks. Their SHA-256 values are `67c0525495d1a251e7c1f653eb4cbb28c302805a2979eec0df005becde7eeaad` and `da1f469daf1ad59e0352afcab2a48858133a30be1feec0250883c05f1ef3d6a4` respectively.

The local importer checked the downloaded final archives against the [CI attempt](arm64/attempt.json), both receipts, static reports and profile revisions, then retained two [current-profile verification records](../../verification/). Their release eligibility remains blocked on the PostgreSQL core dependency redistribution review.
