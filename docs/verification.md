# Verification strategy

Status: draft, 2026-10-13. This document defines evidence for the [specification](specification.md). The team may choose any tools or build route that produce that evidence. Tests exercise **the files a user downloads**, after packaging and publication, not merely intermediate build outputs.

## Release evidence

For each published PostgreSQL minor and platform, retain a result that identifies the exact downloaded artifact and demonstrates:

| Claim | Required observation |
| --- | --- |
| Correct release | The server reports the advertised PostgreSQL minor; the inventory points to the same downloadable bytes and their checksum. |
| Independent installation | On a clean host without the build toolchain or project-specific package-manager libraries, a fresh download can be unpacked, initialized, started, queried, and stopped. Repeat after moving the installation to another directory. |
| Schema usefulness | A representative migration corpus applies successfully and can be inspected through PostgreSQL catalogues. Include schemas, tables, types, constraints, indexes, functions, and version-appropriate features. Expand the corpus when a real consumer finds an omission. |
| Collation support | Create and use ICU collations with representative supported options; create and use a libc collation based on a locale present on the test host. Record host locale availability separately from binary capability. Do not compare exact sort order between OS releases. |
| Other declared capabilities | Exercise every advertised optional PostgreSQL capability with a test that would fail if it were missing. Record deliberately unsupported capabilities in the inventory. |
| Extension usefulness | For each advertised extension, install its download with the matching PostgreSQL artifact, run `CREATE EXTENSION`, and execute representative functions, types, operators, or configuration. For each advertised PostGIS component, exercise a feature of that component, including its required runtime data. |
| Distribution safety | A mismatched or corrupted download is detected. A previously published version remains downloadable and byte-identical after new versions are added. |
| Licensing | Every binary download contains the applicable license texts; an inventory maps redistributed components to their licenses. No published extension lacks permission for free redistribution. |

Dependency inspection is useful evidence, but passing a linker scan alone is insufficient: a library may dynamically load another library or need runtime data. The clean-host and real-feature tests are the decisive portability checks.

## Coverage matrix

- Keep a generated inventory of **all released PostgreSQL minors in majors 15–18**. Compare it with the published inventory. A release is complete only when every required platform passes its checks; failures remain visible instead of disappearing from the catalogue.
- Run the core download and schema checks for every PostgreSQL minor/platform pair. Run the extension checks for every advertised extension/minor/platform combination. A pass for PostgreSQL 17.6 does not stand in for 17.5.
- For each platform, run the **same artifact** on the current OS and the oldest OS that the project claims to support. Sample intermediate versions where needed to establish the range. Record the OS version, architecture, and relevant Linux runtime baseline with the result. If an older host is unavailable to test, do not claim it as verified.
- When a dependency, packaging method, or extension version changes, retest the affected combinations. Periodically re-download and test historical artifacts so old releases do not become inaccessible or misleading.
- Distinguish an upstream PostgreSQL feature absent from an old major from a feature accidentally missing in our build. Tests should be applicable to the upstream release they are checking.

## Acceptance at project level

The initial delivery is complete when the inventory shows every released minor of 15–18 on all three required platforms, the current OS works on each, the claimed backward compatibility has evidence, pgvector and the agreed PostGIS components work where advertised, each download includes its licenses, and the public download path has been exercised end to end. The evidence and known exceptions should be inspectable by a human without reconstructing build logs.

If a test exposes a conflict between an invariant and a feasible implementation, record the evidence and raise the relevant [review decision](decisions.md). Do not quietly weaken the invariant to make a test pass.
