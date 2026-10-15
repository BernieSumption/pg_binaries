# Testing policy

Verification establishes which packaged bytes satisfy the [functional guarantees](../functional/functional-policy.md). The inventory defines intended coverage; generated records hold the results.

## T01 — Test levels

| Level | Purpose | Why a separate level is needed |
| --- | --- | --- |
| [Build](items/planned/build-verification.md) | Check sources, build options, dependencies and package contents; run a smoke test. | The builder may supply libraries or resources missing from the archive. |
| [Artifact](items/planned/artifact-verification.md) | Test the final archives on clean supported systems after extraction and relocation. | This establishes portability and functionality for the tested bytes. |
| [Consumer](items/planned/consumer-verification.md) | Resolve an explicit version request through public metadata, download it and run SQL. | This checks that a client can obtain and assemble the verified installation. |

Test each SQL extension with explicitly selected prerequisite versions, recording
the exact combination. Optional operation fixtures may select additional modules.
These results establish no compatibility with other dependency versions; no
dependency-version matrix or general resolver is required.

[Build items](../build/items/) identify the observations required for
each feature. Build checks establish its configuration and dependencies; artifact
tests establish behaviour after relocation. Tests proposed for unresolved features
apply only if those features are selected. Unmeasured sizes do not fail acceptance,
and no capability requires paired builds solely to measure its size.

## T02 — Verification records

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
the request and catalogue revision. [Metadata fields](../functional/functional-inventory-format.md)
connect these records to the downloadable bytes.

## T03 — Invalidation and coverage

Changed binaries, dependencies, resources or packaging invalidate affected
artifact results. Resolver changes require affected consumer tests. Every new
PostgreSQL minor needs runtime verification, even when it reuses an extension
archive. Reuse earlier results only where the tested inputs and environment
still apply.

[Coverage checks](items/planned/coverage-verification.md) account for every intended target, including failures and unresolved research. Passing binary tests establishes verification; a public download check establishes availability. Neither reduces the inventory's intended scope.

## T04 — Execution rules

Run all local compilation and tests of compiled binaries inside Docker. The host
may inspect files and validate metadata. Use standard free GitHub-hosted runners
for native macOS and Windows tests. If available runners cannot demonstrate a
required OS or runtime condition, record the evidence gap.

Set explicit job timeouts, scope expensive jobs to affected targets, and retain
compact logs and verification records. Give temporary archives short, explicit
retention. Repeat tests to address changed inputs, failures, unresolved risks or
required acceptance checks.

## T05 — Completion of testing work

A test item is complete when its checks are executable, run at the appropriate pipeline stage, and retain the evidence required by T02. Exercise failure cases as well as successful fixtures. Writing the procedure alone does not complete its implementation. Per-target results belong in coverage records.
