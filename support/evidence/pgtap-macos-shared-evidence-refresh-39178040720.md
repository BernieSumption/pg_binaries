# pgTAP shared evidence helper profile refresh

The [selected pgTAP macOS arm64 run 39178040720](https://github.com/BernieSumption/pg_binaries/actions/runs/39178040720) passed its PostgreSQL 17.11 build and fresh-runner archive-suite and static-analysis checks at revision `ef18a587530d1a51a89375c1592296cc1182fa1a`. The profile now includes `tools/macos_publication_evidence.py` among its source inputs, so future helper changes invalidate this record.

The downloaded build and publication artifacts were independently imported. The imported record matches the CI artifact byte for byte and binds core SHA-256 `e2fe14b3967cd06f4e9695dac2d8649bc46a3e211a9fa63b0a686d3a53018d4b` to pgTAP SHA-256 `c6c94eee4a84d12497c1c50e4a239a5b8557a1e4a6ae36c68db72eee230c7d6c` under current profile revision `ac219dd04f8140948f7305e99841cb8f8d5826c9fb4b2cedd8d40e34527887e1`.
