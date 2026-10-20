# PostgreSQL 16.15 macOS arm64 core publication

[Run 39424382435](https://github.com/BernieSumption/pg_binaries/actions/runs/39424382435) passed the selected core build and fresh-runner verification at revision `817362a98376ab8b0a5af6239ae5dbc92962fedf`. The archive SHA-256 is `aae8b4e67a88cb3edc074070527dda23ea5bac09b7574403fdaa18eb1e31ab8c`; its current-profile verification record and importer-retained evidence are in this directory and `support/verification`.

The selected core pin now points to this run so the pgAudit PostgreSQL 16.15 macOS arm64 feasibility workflow can be dispatched. That extension run remains the next step.

On 2026-10-20, the selected build archive was rechecked against the pin and its embedded `postgresql/LICENSES/inventory.json` was retained as [license-inventory.json](license-inventory.json) (SHA-256 `7d8b238db1458c118ca86d359a38e52de1be5c977eb452a765d8f2a5b1b6356b`). PostgreSQL 16.15, ICU 78.3, libxml2 2.15.4, libxslt 1.1.45, LZ4 1.10.0, OpenSSL 3.5.8 and zstd 1.5.7 all record `resolved` with source obligation `none`. The archive inventory checker passed for 133 native payloads across seven components; this checks inventory structure and archive coverage, not the accuracy of the recorded licence interpretations.
