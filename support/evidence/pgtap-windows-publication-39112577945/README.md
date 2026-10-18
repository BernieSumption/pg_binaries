# pgTAP Windows publication run 39112577945

GitHub Actions run [39112577945](https://github.com/BernieSumption/pg_binaries/actions/runs/39112577945) passed on source revision `90837a1ff8dcb62f5b7ca3306a59932fc12af092`. Its current-profile extension record binds pgTAP archive SHA-256 `da913efb244a0ce6aab290d640e03c2ca86cbdc7dec84e78f4f4d65fe1b816e0` and both passing cases, archive-suite and static-analysis, to PostgreSQL 18.6 archive SHA-256 `acba200dc61234fce48f75b0dd57b6e4392ca0c56ffe59448b8d1fe8b5d21b27`.

The exact archive bytes and pgTAP test profile remain current. The separate PostgreSQL 18.6 core verification profile is stale because the PG15-only helper change altered the shared Windows core source set. This record therefore establishes the pgTAP test result against those exact core bytes; overall publication remains blocked until a current-profile core record is available. The retained files contain the attempt, receipt, structural analysis and relocated SQL probe output.
