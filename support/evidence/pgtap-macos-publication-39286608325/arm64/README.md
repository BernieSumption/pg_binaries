# pgTAP macOS arm64 publication evidence, run 39286608325

GitHub Actions run [39286608325](https://github.com/BernieSumption/pg_binaries/actions/runs/39286608325) succeeded for PostgreSQL 18.6 and pgTAP 1.3.4 at source revision `225559542cc833bf68317bec5450eff1f4ea2502`. Its fresh macOS runner passed the archive suite and static analysis. The exact-producer importer accepted the evidence, and the five retained evidence files plus verification record match the downloaded publication artifact byte for byte. The profile remains current in the producer snapshot and present checkout.

The published pgTAP archive SHA-256 is `0b57b8febb4c30dfc5ff313477d99702a7287fafcb21849b1de7ecb8e3a0bf52`; its sidecar agrees. Its 36 tar members contain no absolute paths or `..` components.

The pgTAP build reused core archive `postgresql-18.6-macos-arm64.tar.gz`, SHA-256 `33807e7b17519acf8643ed73429ba7c983cf9572be12048bdb7b6a872f682608`. The candidate manifest identifies selected core artifact `postgresql-macos-selected-18.6-arm64-build-39264498472` (artifact ID `12192063860`, ZIP SHA-256 `abdca7f7beec38b41de5b3143707fdac7e09f9f5d95c0760f3988e708798e464`) from selected-core workflow run 39264498472. The target config separately records original core builder run 39260057987. The resolver supplied this archive to the pgTAP build, which skipped PostgreSQL core compilation.

The build artifact is ID `12204155692`, with GitHub ZIP digest `7e08d401ca837535c71df7f45a6e5a6d6e85b00b8d5f0d7dbcc433adbb214fc5`. The publication artifact is ID `12203846348`; its downloaded ZIP matched GitHub's SHA-256 digest `3b5b671a21d14abfdaed54a5ff857c7b6116f49237d5e29c953180d7aaf41c57`. All six retained support files also match that ZIP byte for byte. The pgTAP archive SHA-256 and sidecar were verified locally.
