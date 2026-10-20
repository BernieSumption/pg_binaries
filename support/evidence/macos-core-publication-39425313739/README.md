# PostgreSQL 17.11 macOS arm64 core publication

[Run 39425313739](https://github.com/BernieSumption/pg_binaries/actions/runs/39425313739) passed the selected core build and fresh-runner verification at revision `408cb35e340df85bd8664771188b20e82ab6bc64`. The archive SHA-256 is `0db9ca0f4d0cf72fa32120aaf9a3f8e47c9dd2d97421ab2b53583af83be681b6`; the current-profile verification record and importer-retained evidence are in this directory and `support/verification`.

The selected core pin and pgAudit macOS arm64 target now point to this run so the pgAudit PostgreSQL 17.11 workflow downloads the exact verified artifact.

On 2026-10-20, the downloaded build artifact matched that archive SHA-256. Its retained [licence inventory](license-inventory.json) has SHA-256 `00052096ef4be97760dc8ab59c7dc472d285c41bf6340f00bf1ceb30cd6444b4`. It lists PostgreSQL 17.11, ICU 78.3, libxml2 2.15.4, libxslt 1.1.45, LZ4 1.10.0, OpenSSL 3.5.8 and zstd 1.5.7. Every entry records `redistribution_review.status: resolved`, a basis and `source_obligation: none`. `tools/check_macos_license_inventory.py` checked 134 native payloads and declared licence texts in the exact archive. These checks establish the recorded review status and archive structure; the release review must still assess the licence conclusions themselves.
