# PostgreSQL 15.19 macOS arm64 core publication

[Run 39424367764](https://github.com/BernieSumption/pg_binaries/actions/runs/39424367764) passed the selected core build and fresh-runner verification at revision `817362a98376ab8b0a5af6239ae5dbc92962fedf`. The archive SHA-256 is `bd866dec8967e6320f88eb8ffe3a2f57fad36920b3d05556dae026c53226cf85`; its current-profile verification record and importer-retained evidence are in this directory and `support/verification`.

The selected core pin now points to this run so the pgAudit PostgreSQL 15.19 macOS arm64 feasibility workflow can be dispatched. That extension run remains the next step.

On 2026-10-20, the selected build archive was rechecked against the pin and its embedded `postgresql/LICENSES/inventory.json` was retained as [license-inventory.json](license-inventory.json) (SHA-256 `f79e1cb37959e9d34c583d6b98df7c404f609f6a179903b86282738451e7073a`). PostgreSQL 15.19, ICU 78.3, libxml2 2.15.4, libxslt 1.1.45, LZ4 1.10.0, OpenSSL 3.5.8 and zstd 1.5.7 all record `resolved` with source obligation `none`. The archive inventory checker passed for 137 native payloads across seven components; this checks inventory structure and archive coverage, not the accuracy of the recorded licence interpretations.
