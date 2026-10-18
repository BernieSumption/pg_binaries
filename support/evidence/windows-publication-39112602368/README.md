# Windows PostgreSQL 16.15 publication run 39112602368

GitHub Actions run [39112602368](https://github.com/BernieSumption/pg_binaries/actions/runs/39112602368) passed its Windows x86-64 build and relocated verification jobs on source revision `90837a1ff8dcb62f5b7ca3306a59932fc12af092`. The PostgreSQL archive SHA-256 is `a684c780408f6528e7e8c7efcaef707a030f4fb6d3a2ffb42ea5eaa8f7cb5168`; the bundled pgvector 0.8.7 archive SHA-256 is `074a18403d4b49f10d0de8528b0a271d3cf0f3d6ee256c740690dcca19a23570`.

The core build used the exact upstream PostgreSQL `REL_16_15` Git tag at commit `7d3e000c5961a544302072058a1184e9a588837b` and tree `e97d2bd54137833e68079ed70e1a4a6621453264`. Imported current-profile records bind both archives to archive-suite, diagnostics, symbols and static-analysis evidence. The core dependency redistribution review remains open; release eligibility is false.

These records match the registered Windows core profile at the run revision. The upcoming PE-checker correction changes a shared profile source, so this evidence will become historical until the Windows core runs are refreshed.
