# Implementation decisions

AI-maintained technical rationale for the [functional specification](functional.md) and [architecture](architecture.md). Entries distinguish established consequences, candidate approaches and unresolved research. Human scope choices belong in [product decisions](product-decisions.md); build output and individual test results belong in verification records.

## D01 — Coverage policy and generated records

**F01, F02, F13 — design.** Maintain date selectors and compatibility intervals in the authored inventory. Generate exact releases, coverage and downloads separately, so adding builds cannot change the target or require editing a large release ledger. New release lines without compatibility rules create research tasks.

## D02 — Source, SQL and build identities

**F02, F03, F08, F11 — required distinction.** One source release can contain several SQL extensions; an extension can move source projects; a corrected build can change bytes without changing either version. Metadata retains all three identities.

PostgreSQL's [extension packaging rules](https://www.postgresql.org/docs/18/extend-extensions.html) distinguish installation scripts, update scripts and control files. SQL version strings are arbitrary. An update script's presence does not prove that its starting version can be installed with the packaged library. Test each advertised installation or update path; this creates no general production-upgrade guarantee.

**Agreed dependency scope:** Record upstream control-file dependency names. Clients choose dependency versions and handling, including any restriction on `CASCADE`. Do not recommend dependency versions, research compatibility ranges between extensions or build a general version-resolution system. Verification records the exact versions tested and establishes only that concrete combination. This leaves PostgreSQL-version compatibility and native runtime packaging requirements intact. The [dependency research](research/extension-dependencies.md) explains the upstream behaviour.

## D03 — Extension build reuse

**F08 — initial build strategy; runtime compatibility requires verification.** Start with separate native builds per PostgreSQL major, using the oldest eligible compatible minor to avoid dependence on later server symbols. PostgreSQL's [C-extension guidance](https://www.postgresql.org/docs/18/xfunc-c.html) informs expected ABI compatibility; our tests establish the advertised runtime range.

If a minor needs different interfaces, split the build range. SQL-only packages can also require version-specific generation or syntax, so broader reuse needs tests even without compilation.

## D04 — Relocation and indirect dependencies

**F04, F09 — established by pilot failures.** The pilot missed an ICU data library on macOS, required relocated PROJ/GDAL resource paths on Linux, and inherited pgvector's `-march=native` before correction. These failures justify checking transitive loading, resource lookup and effective compiler flags as well as startup. See [evidence](evidence.md).

Platform adapters must remove builder-path dependencies and derive resource paths from the extracted prefix. Loader inspection finds known dependencies; feature execution catches runtime loading and resource access that inspection misses.

## D05 — Windows runtime packaging

**F04 — runtime required, linking choice open.** The pilot's external VC redistributable prerequisite violates F04. Microsoft's [deployment guidance](https://learn.microsoft.com/en-us/cpp/windows/choosing-a-deployment-method?view=msvc-170) describes app-local DLLs and static linking; the [UCRT guidance](https://learn.microsoft.com/en-us/cpp/windows/universal-crt-deployment?view=msvc-170) distinguishes OS-provided UCRT from other runtime files.

Try permitted app-local DLLs first. Compare static linking for size and behaviour, including allocations crossing library boundaries. Check files against the exact toolchain's [redistribution terms](https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files?view=msvc-170).

Establish the dependency set, test without preinstalled non-OS CRT files, and measure compressed/extracted overhead. The pilot's combined archive sizes do not provide that measurement. Use an isolated environment without removing runtimes from a shared runner.

## D06 — Shared runtime ownership

**F03 — packaging research.** Separate SQL downloads are required; shared-library ownership still needs implementation. Moving TIGER and address standardizer to standalone source projects changes intake and versioning while preserving their SQL identities.

A shared PostGIS runtime containing every optional library could erase the download savings from separate extensions. Measure dependency sets and sizes, then verify each package with only its required dependencies and explicit file ownership. See [extension profiles](extensions/README.md).

## D07 — Resource inclusion

**F09 — resource policy applied to packaging.** Retain install-time seed data, standardizer rules and required coordinate definitions. PROJ's [resource-search rules](https://proj.org/en/stable/resource_files.html) require testing lookups after relocation.

Bulk TIGER Census records populate application tables through generated import scripts; the [TIGER profile](extensions/supported/postgis_tiger_geocoder.md) describes that workflow. Exclude that corpus while keeping small default lookup/configuration data. Document any DDL that invokes operations needing external data. The [resource research](research/extension-resources.md) identifies PROJ grids as a separate question: some transformations need them during DDL execution.

## D08 — Corrected-build publication

**F10, F11 — publication protocol.** Stage archives named with their full SHA-256 and matching metadata, verify them, then activate the catalogue revision. Changed bytes require a new filename and URL. Clients can identify stale cached builds while continuing to request the same upstream version.

Keep provenance after removing superseded binaries. Pinned sources alone do not establish reproducible archive bytes: local and CI pilot builds produced different hashes. The current contract requires integrity and traceability.

## D09 — OS and ABI baselines

**F04 — exact ranges unresolved.** Assess named OS releases under the four-year policy. An older compiler SDK or build container can remain useful even when that OS is outside the supported runtime window.

Identify Linux libc/CPU requirements and distributions, Intel macOS releases, Windows desktop editions/feature releases, and available verification environments. Record any evidence gaps or narrowing needed to preserve current OS support. The glibc scope option is a [product decision](product-decisions.md#linux-abi-scope).

## D10 — Capability audit

**F05–F09 — research.** Map compile options to SQL/configuration, dependencies and tests for each release. Audit contrib, procedural languages and integrations, including PL/Python, PL/Perl, PL/Tcl, LLVM/JIT and LDAP/GSSAPI, to expose schema-relevant omissions.

Use tagged PostGIS requirements: the [SFCGAL profile](extensions/supported/postgis_sfcgal.md) records a stricter requirement than the moving manual cited by the pilot. Classify optional external-data operations separately from missing binary dependencies.

The [capability sections](capabilities.md) explain inclusion decisions, schema use, delivery, size considerations and verification. The [technical audit](research/postgresql-capabilities.md) retains build-option details and outstanding extension-module research. Apply F07 to resolve feature inclusion from evidence. Only policy conflicts or exceptions require product decisions; XML and OpenSSL/TLS follow directly from schema functionality and upstream build coupling.

Complete the per-module contrib inventory and verify selected capabilities. Use existing size evidence or inexpensive estimates; record unknown costs as unmeasured. Agree any targeted measurement experiment separately when its result could change a decision. Before proposing a schema-relevant exclusion to the user, provide affected SQL, known size considerations and alternatives.

