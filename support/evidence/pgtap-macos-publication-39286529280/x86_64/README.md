# pgTAP macOS x86-64 publication evidence, run 39286529280

GitHub Actions run [39286529280](https://github.com/BernieSumption/pg_binaries/actions/runs/39286529280) succeeded for PostgreSQL 18.6 and pgTAP 1.3.4 at source revision `225559542cc833bf68317bec5450eff1f4ea2502`. The fresh macOS runner passed the archive suite and static analysis. The exact-source importer accepted the downloaded publication artifact, and all five retained evidence files plus the verification record match the artifact copy byte for byte. The profile remains current in the present checkout.

The published pgTAP archive SHA-256 is `64826f0db88d26e16bbd26046c21b12dfd05ca1dc7ae27a57943038dacc789e7`; its sidecar agrees. Its 36 tar members contain no absolute paths or `..` components.

The pgTAP run reused core archive `postgresql-18.6-macos-x86_64.tar.gz`, SHA-256 `e3df58edda00221a874c6b23796be6487d7a24152b523f82c7db8deff9204eb9`. Its candidate manifest identifies selected core artifact `postgresql-macos-selected-18.6-x86_64-build-39274163013`, workflow run 39274163013, which is also the original core builder run recorded in the target. The pgTAP run therefore skipped PostgreSQL core compilation and built pgTAP against the resolved core archive.

GitHub CLI downloaded the exact build and publication artifacts by run ID. The GitHub API artifact-list endpoint repeatedly failed to connect, so artifact ZIP IDs and GitHub ZIP digests could not be checked; the published archive SHA-256 and sidecar were verified locally.
