# HypoPG fresh-runner macOS verification

[Run 39135932527](https://github.com/BernieSumption/pg_binaries/actions/runs/39135932527) built HypoPG 1.4.3 for PostgreSQL 17.11 on a macOS arm64 runner, then downloaded the final archives into a separate macOS arm64 runner job. The verifier assembled the archives, moved the installation, inspected 131 native files and exercised HypoPG's index-plan and reset behavior. Both publication cases passed.

The [attempt](arm64/attempt.json) and [receipt](arm64/current-receipt.json) bind the checks to PostgreSQL archive SHA-256 `d9ac809946cd87bbb585135d0ff329d33d5563047b9caaa312aea9116a8d9eaa` and HypoPG archive SHA-256 `7f9224bce2a6f4c637233ec448a3d55cfda33efe8512a6da4f872f781aa1bd2e`. The [static report](arm64/static-analysis.json), [SQL output](arm64/probe-output.txt) and [publication record](../../verification/hypopg-1.4.3-postgresql-17.11-macos-arm64-current-39135932527.json) were imported from the verification job's retained artifact. Its runner image was `macos15/20260907.0337.1` with macOS 15.7.9. The source revision and test revision were `809d79f3a8c8df11d9a4921e6db0cc76852265a8`.

This verifies the fresh-runner structure for one target. Other macOS and Windows extension workflows require their own split before their records meet the same environment rule. The archives remain unpublished.
