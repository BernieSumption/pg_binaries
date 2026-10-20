# pgAudit 18.0 macOS arm64 attempt 39445559081

[The selected run](https://github.com/BernieSumption/pg_binaries/actions/runs/39445559081) failed before the extension build. The core resolver rejected the PostgreSQL 18.6 artifact pin because the archive's embedded builder ID named original run 39260057987, while the pin named a later run that had reverified and reuploaded identical bytes. No extension archive or archive-bound record was produced.

The original producer artifact was still available, and its SHA-256 matched the reverified archive. Commit `b6103237` corrected the pin to the original producer; the follow-up selected run is 39446348112.
