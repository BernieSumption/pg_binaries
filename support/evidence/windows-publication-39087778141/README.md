# Windows PostgreSQL 18.6 current-profile verification

[Run 39087778141](https://github.com/BernieSumption/pg_binaries/actions/runs/39087778141) passed the Windows x86-64 PostgreSQL 18.6 and pgvector 0.8.7 publication profiles after the PE dependency checker was corrected to merge case variants of Windows DLL names. The importer validated the exact final archives, symbols, diagnostics and PE report, then retained two current-profile records. The PostgreSQL core archive SHA-256 is `19ee6d8c09136eacbeca353c9d4f71eca0104982dce632e10c723ebb63406712`.

The [vcpkg DLL map](vcpkg-dll-map.json) attributes 16 bundled DLLs to versioned ports. The [core licence inventory](core-license-inventory.json) still marks their redistribution review pending. This run establishes current build and runtime verification; it does not clear the dependency review or make the core release eligible.
