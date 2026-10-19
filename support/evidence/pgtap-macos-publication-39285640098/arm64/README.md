# pgTAP macOS arm64 publication evidence, run 39285640098

GitHub Actions run [39285640098](https://github.com/BernieSumption/pg_binaries/actions/runs/39285640098) succeeded for PostgreSQL 18.6 and pgTAP 1.3.4 at source revision `4f01212aaacd77200931b3a7a2b6b9745c3f1be4`. Its fresh macOS runner passed the archive suite and static analysis on macOS 15.7.9 (`macos15/20260907.0337.1`). The retained verification record matches the publication artifact byte for byte.

The produced pgTAP archive SHA-256 is `86281ea66f0bce2d6d1c6dda48d8c4e9bf67bea71d9c62ba770abd7eb17dafb0`. Its 36 tar members have no absolute paths or `..` path components. The archive sidecar has the same digest.

The run reused PostgreSQL core archive `postgresql-18.6-macos-arm64.tar.gz`, SHA-256 `33807e7b17519acf8643ed73429ba7c983cf9572be12048bdb7b6a872f682608`. The candidate manifest identifies the selected core artifact as `postgresql-macos-selected-18.6-arm64-build-39264498472`, from workflow run 39264498472. This is distinct from the original builder run recorded in the pgTAP target config, 39260057987.

The exact-source importer accepted the evidence against source snapshot `4f01212aaacd77200931b3a7a2b6b9745c3f1be4`. The profile was current at that producer snapshot. It is stale against the present checkout, so this record is retained as historical evidence.

The verification artifact was `pgtap-macos-arm64-18.6-publication-39285640098` (ID `12202877931`, ZIP SHA-256 `d78d78981a7c0592384381bf164068ef5c90f8219771687287a097771957bb87`); its downloaded ZIP matched the GitHub digest. The build artifact was ID `12203690192`, ZIP SHA-256 `7e91a68a417849bf0b2d2ffedb9bbecfa14459342efd07dd53e4202df40087bb`.
