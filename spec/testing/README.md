# Verification specification

These tests define acceptance criteria for [F01–F13](../functional.md).
The [inventory](../inventory.json) defines intended coverage; release discovery
expands it into exact targets. Passing tests establish verified builds, and a
public download check establishes availability. [Coverage checks](coverage.md)
account for all targets, including failures and unresolved research.

## Test levels

| Level | Purpose | Why a separate level is needed |
| --- | --- | --- |
| [Build](build.md) | Check sources, build options, dependencies and package contents; run a smoke test. | The builder may supply libraries or resources missing from the archive. |
| [Artifact](artifact.md) | Test the final archives on clean supported systems after extraction and relocation. | This establishes portability and functionality for the tested bytes. |
| [Consumer](consumer.md) | Resolve an explicit version request through public metadata, download it and run SQL. | This checks that a client can obtain and assemble the verified installation. |

Test each SQL extension with explicitly selected prerequisite versions, recording
the exact combination. Optional operation fixtures may select additional modules.
These results establish no compatibility with other dependency versions; no
dependency-version matrix or general resolver is required.

[Capability sections](../capabilities.md) identify the observations required for
each feature. Build checks establish its configuration and dependencies; artifact
tests establish behaviour after relocation. Tests proposed for unresolved features
apply only if those features are selected. Unmeasured sizes do not fail acceptance,
and no capability requires paired builds solely to measure its size.

## Verification records

Binary verification records identify the following inputs and environment.
Metadata-only tests record their input/fixture revisions, timestamps, commands
and results; binary and runtime fields do not apply.

- The inventory and release-discovery revisions, test revision and timestamps.
- Build IDs, recipe revision, source identities, and archive/dependency SHA-256 values.
- Exact PostgreSQL, SQL extension and native-library versions.
- OS release, edition and patch level; architecture and CPU capabilities; libc
  version on Linux; locale inventory and relevant preinstalled runtimes.
- Commands, results and retained diagnostic logs, including failures.

Build records additionally identify source URLs and hashes, patches, toolchains,
SDKs, dependency inputs and effective build options. Consumer records include
the request and catalogue revision. [Metadata fields](../inventory-format.md)
connect these records to the downloadable bytes.

Changed binaries, dependencies, resources or packaging invalidate affected
artifact results. Resolver changes require affected consumer tests. Every new
PostgreSQL minor needs runtime verification, even when it reuses an extension
archive. Reuse earlier results only where the tested inputs and environment
still apply.

## Execution rules

Run all local compilation and tests of compiled binaries inside Docker. The host
may inspect files and validate metadata. Use standard free GitHub-hosted runners
for native macOS and Windows tests. If available runners cannot demonstrate a
required OS or runtime condition, record the evidence gap.

Set explicit job timeouts, scope expensive jobs to affected targets, and retain
compact logs and verification records. Give temporary archives short, explicit
retention. Repeat tests to address changed inputs, failures, unresolved risks or
required acceptance checks.

## Requirement map

| Requirement | Main observations |
| --- | --- |
| F01 — Version coverage | Discover every eligible release; retain failed and unresolved targets. |
| F02 — Exact choices | Preserve requested source, PostgreSQL and SQL versions; report absence or ambiguity. |
| F03 — Independent modules | Install each module with its required closure; check ownership and omit unrelated downloads. |
| F04 — Relocation | Audit CPU flags; run as an ordinary user in two locations on required OS environments. |
| F05 — Tools and schemas | Initialize UTF-8, apply DDL, inspect catalogues, dump/restore schema and stop cleanly. |
| F06 — Collations | Exercise ICU and available libc locales; record provider and locale availability. |
| F07 — Capabilities | Audit options and test every included capability, including applicable compression operations. |
| F08 — Extension combinations | Verify SQL/library identity and operations on every advertised PostgreSQL minor with required dependencies. |
| F09 — Resources | Run offline with bundled resources; document exclusions and affected operations. |
| F10 — Inspectable archives | Compare manifests; reject corruption, unsafe paths, file conflicts and missing dependencies. |
| F11 — Corrected builds | Resolve the current build, detect stale caches and check consistent publication. |
| F12 — Redistribution | Audit component obligations, retain required texts and download without payment or authentication. |
| F13 — Metadata completeness | Check structured constraints, scoped notes and dated discovery/coverage records. |


## Current evidence

The [evidence summary](../evidence.md) records the pilot's passes and limits.
Outstanding work includes release coverage, independent PostGIS module downloads,
OS baselines and complete capability checks. In particular, the Windows server
runner supplied a Visual C++ runtime, and older GEOS/SFCGAL dependencies limited
the PostGIS pilot. Neither result establishes the full new contract.
