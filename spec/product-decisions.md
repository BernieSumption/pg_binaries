# Product decisions

This is the human review queue for choices that affect the project's scope or guarantees. Technical reasoning belongs in [implementation decisions](implementation-decisions.md). When a choice is settled, record the outcome here and update the relevant specification; unresolved alternatives do not change the current contract.

## Capability policy exceptions

**Settled:** [F07](functional.md#f07--capability-inclusion-follows-schema-requirements) determines feature inclusion. XML and compiled OpenSSL/TLS support follow from that policy; clients choose runtime activation. Feedback 9 is resolved as a general rule.

**Remaining decisions:** Review only conflicts or exceptions. NUMA inspection exposes SQL functionality but requires OS/kernel support that portable archives cannot supply. SELinux security labels likewise require system policy and provisioning. For remote authentication, first establish which promised schema operations need it; classify features by F07 before requesting a product decision. Context: [capabilities](capabilities.md), [extension-module research](research/postgresql-capabilities.md#extension-module-build-dependencies).

## Extension build reuse — feedback 10

**Decision:** State explicitly that we minimize distinct extension builds by reusing archives across genuinely compatible PostgreSQL minors, using upstream compatibility claims to plan verification?

The architecture already describes reuse. The proposed addition would make its objective explicit while retaining tests on every advertised minor. Context: [F08](functional.md#f08--each-advertised-extension-combination-works), [build planning](architecture.md#build-planning-and-reuse).

## Large datasets — feedback 11

**Decision:** What offline coordinate-transformation coverage should PostGIS provide, and which optional PROJ grids does it require?

Bulk TIGER Census records are excluded application data. Some PROJ grids can instead be needed when DDL evaluates a transformation. Retain ordinary runtime resources; decide the grid scope using the [resource research](research/extension-resources.md) and [F09](functional.md#f09--resource-scope-follows-the-schema-task).

## Real-world extension dependency conflicts

**Decision:** Does observed dependency usage or version conflict frequency justify special handling beyond recording upstream dependency names?

The current policy assumes extension-to-extension dependencies are rare in practice. We therefore chose not to track required dependency versions, which would be difficult to ascertain reliably. That assumption has not yet been established by a survey. Clients handle dependency selection; verification records exact tested combinations without promising compatibility with other dependency versions.

**Evidence needed:** Inspect a named sample of intended and likely extensions. Report how many declare SQL-extension dependencies, how many share prerequisites, and how many have documented or reproduced version conflicts. Identify the releases and sources behind each conflict; distinguish missing information from evidence that a combination works. Shared prerequisites alone do not establish a conflict. Keep native-library collisions separate from SQL-extension version requirements.

Use those findings to decide whether the current policy is sufficient or a specific exception is warranted. This investigation does not itself authorize a general version resolver or exhaustive compatibility matrix. The agreed names-only policy remains in force: [F03](functional.md#f03--sql-extensions-can-be-obtained-separately), [dependency scope](research/extension-dependencies.md#agreed-dependency-scope).

## Download hosting

**Decision:** Choose public hosting and publication permissions. GitHub Releases is a candidate; temporary Actions artifacts do not meet the public-download requirement. Publishing permanent releases still requires authorization.

Context: [F12](functional.md#f12--downloads-include-redistribution-obligations), [publication architecture](architecture.md#verification-and-publication).

## Linux ABI scope

**Decision:** Use glibc as the first Linux ABI target, and whether to include musl systems such as Alpine.

Exact distribution and OS ranges still need research under the four-year support policy. Context: [F04](functional.md#f04--relocation-requires-no-system-provisioning), [OS baseline reasoning](implementation-decisions.md#d09--os-and-abi-baselines).
