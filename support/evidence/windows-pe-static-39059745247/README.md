# Windows archive and PE verification

[Run 39059745247](https://github.com/BernieSumption/pg_binaries/actions/runs/39059745247), source revision `f0855d537c7e687af45da982ea1fa4e97ec29de2`, passed the Windows x86-64 PostgreSQL 18.6 and pgvector 0.8.7 build and fresh-runner verification on 2026-10-17. Both retained schema-v2 records pass `tools/coverage.py` validation against the current Windows pilot profile. They establish pilot evidence, not publication eligibility.

The downloaded final archives match their SHA-256 sidecars, the two records and the retained static report. The report passed inspection of 144 PE files, including application-local runtime DLL closure after adding the documented Windows LDAP DLL to the system allowlist. Relocated schema, built-in extension and pgvector checks and downloaded-archive PDB verification passed in CI.

The exact artifact bytes of the static report, symbol index, checksum sidecars and verification records are retained. `build-record.json` is derived from the core manifest and downloaded archive/index hashes. Local inspection checked all 125 symbol-index module and PDB checksums against the downloaded archives and PDB files. Large archives and PDBs remain outside Git; the Actions artifacts expire after one day.

The report checks imported DLL names and PE target fields; it does not establish imported function/API-set availability on Windows 10 build 10240 or complete loader search order. Current-runner execution does not establish execution on that minimum OS. The vcpkg dependency source-patch audit and exact runtime DLL versions and redistribution declarations remain unresolved. These results do not establish upstream-only dependency provenance or redistribution clearance.
