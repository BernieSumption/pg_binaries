# pgTAP 1.3.4 Windows publication verification

[Run 39083314732](https://github.com/BernieSumption/pg_binaries/actions/runs/39083314732) passed on a standard Windows 2022 x86-64 runner. It generated pgTAP SQL from pinned, unmodified upstream source, installed its final archive with the exact PostgreSQL 18.6 core from run 39077749917, and passed `CREATE EXTENSION pgtap` plus four assertions after relocation. The final-archive check found no native pgTAP files and bound the package metadata to the core and source hashes. The imported [receipt](x86_64/current-receipt.json) and verification record bind both passing cases to the final archives.

This establishes the current scoped profile. The core input remains a temporary CI artifact, and its bundled vcpkg components still need source-provenance and redistribution review before release eligibility.
