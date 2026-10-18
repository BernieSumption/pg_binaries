# Selected Windows HypoPG trial

[GitHub Actions run 39170659413](https://github.com/BernieSumption/pg_binaries/actions/runs/39170659413) passed at source revision `db1601af676834a79b53b4882d244c45e2a794c5`. The selected target was PostgreSQL 17.11, HypoPG 1.4.3 and Windows x86-64. The selector, build and fresh-runner verification jobs passed. The build job took about 25 minutes, including roughly 20 minutes of dependency setup; verification took 41 seconds.

The [independently imported record](../verification/hypopg-1.4.3-postgresql-17.11-windows-x86_64-current-39170659413.json) binds the HypoPG archive SHA-256 `c9f8fee6cb81649b9c3ddda197eb64dd1fdc7985b6456eb0c91408258da89442` to core SHA-256 `f7ea0ce998ffe8c24828b2c1bab7d99c25e8daa19631a1058eaffd7c60f9e953`. It reports passed archive and PE dependency checks on a Windows Server 2022 runner. The importer checked the downloaded archive checksums, receipt, static-analysis report and diagnostic evidence. [Retained outputs](hypopg-windows-publication-39170659413/x86_64/17.11/verification-record.json) identify the same run and bytes.

This trial built a fresh core. Checked reuse of an existing Windows core remains to be demonstrated on the selected path.
