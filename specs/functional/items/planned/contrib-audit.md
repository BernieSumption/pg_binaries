# D10 — Capability audit

**F05–F09 — research.** Map compile options to SQL/configuration, dependencies and tests for each release. Audit contrib, procedural languages and integrations, including PL/Python, PL/Perl, PL/Tcl, LLVM/JIT and LDAP/GSSAPI, to expose schema-relevant omissions.

Use tagged PostGIS requirements: the [SFCGAL profile](../../../extensions/items/planned/postgis_sfcgal.md) records a stricter requirement than the moving manual cited by the pilot. Classify optional external-data operations separately from missing binary dependencies.

The build items explain inclusion decisions, schema use, delivery, size considerations and verification. The [technical audit](../../../build/build-notes.md) retains build-option details and outstanding extension-module research. Apply the [build policy](../../../build/build-policy.md) to resolve feature inclusion from evidence. Only policy conflicts or exceptions require product decisions; XML and OpenSSL/TLS follow directly from schema functionality and upstream build coupling.

Complete the per-module contrib inventory and verify selected capabilities. Use existing size evidence or inexpensive estimates; record unknown costs as unmeasured. Agree any targeted measurement experiment separately when its result could change a decision. Before proposing a schema-relevant exclusion to the user, provide affected SQL, known size considerations and alternatives.

## Completion

Complete the per-module inventory and option audit, apply the inclusion policy, and verify selected modules and declared exclusions.
