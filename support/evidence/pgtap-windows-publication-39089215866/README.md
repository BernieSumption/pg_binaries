# pgTAP 1.3.4 Windows publication verification

[Run 39089215866](https://github.com/BernieSumption/pg_binaries/actions/runs/39089215866) passed both publication cases on a standard Windows 2022 x86-64 runner. The archive suite exercised pgTAP against the exact PostgreSQL 18.6 core archive from run 39077749917 after relocation. Static analysis checked the final archives, and the imported receipt and verification record bind both results to their archive hashes.

The core input is a temporary CI artifact, so this candidate remains ineligible for release. Its bundled vcpkg components still need source-provenance and redistribution review.
