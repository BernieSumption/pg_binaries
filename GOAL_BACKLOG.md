# Work towards release authorization

This backlog records work for the current development goal. The specifications define requirements; policies record decisions; verification records establish results. Items here do not change any requirement.

## Verified pilot progress

- PostgreSQL 18.6 and pgvector 0.8.7 Linux pilots pass on clean current runners and on older-glibc and no-glibc hosts. The [x86-64](https://github.com/BernieSumption/pg_binaries/actions/runs/38975180522) and [arm64](https://github.com/BernieSumption/pg_binaries/actions/runs/38975180567) combined runs passed current and Linux 5.15 guest checks on the same archive bytes and emitted separate checksum-bound records for both endpoints. Guest output and records are retained under `support/evidence/` and `support/verification/`.
- The PostGIS 3.6.4 Linux x86-64 pilot passes assembled runtime, relocation, older/no-glibc, licence-inventory and representative SQL checks for its four declared SQL extensions. The [same-revision reuse run](https://github.com/BernieSumption/pg_binaries/actions/runs/38979052354) used the verified x86-64 core archive; its [four records](support/verification/) bind PostGIS to that archive's exact SHA-256. This is pilot evidence, not publication coverage.
- The [Linux x86-64 run 38979052339](https://github.com/BernieSumption/pg_binaries/actions/runs/38979052339) and [arm64 run 38979052343](https://github.com/BernieSumption/pg_binaries/actions/runs/38979052343) passed current and Linux 5.15 guest checks on the same archive bytes within each architecture. Their retained records, symbol indexes, guest logs, and missing-loader and PostgreSQL-error diagnostic captures are under `support/verification/` and `support/evidence/`.
- Pilot CI runs have passed at least once for all five intended platform and architecture pairs. The [macOS arm64 run](https://github.com/BernieSumption/pg_binaries/actions/runs/38975259894) passed its fresh-runner archive checks. No publication test profile exists; macOS 11 and Windows 10 client minimum endpoints remain unresolved in [the human review queue](HUMAN_REVIEW_QUEUE.md).

## Policy decisions

- [ ] Derive OS, PostgreSQL option, installation, testing, delivery, release, debugging, and extension policies from the specifications. Record source evidence and unresolved decisions. Do not infer required behaviour from the pilot scripts.
- [ ] Investigate whether a Linux archive can satisfy the kernel-only support declaration on clean supported distributions, including non-glibc systems. If no compliant approach is feasible within the allowed infrastructure, add the decision to `HUMAN_REVIEW_QUEUE.md`.
- [ ] Establish a supported OS minimum and practical clean-system tests for the minimum and current endpoints on all five OS/architecture combinations.
- [ ] Resolve Address Standardizer's US address-data redistribution rights before deciding whether its project can be included under the specification's hard licensing rule.
- [ ] Align optional PostgreSQL capabilities across platforms: provide and test `uuid-ossp` where advertised, and make the readline exclusion explicit in every build script.

## Support and coverage

- [x] Define one authoritative intended-support source and a coverage report that shows every missing PostgreSQL version, platform, extension version, or verification result, including failed and skipped work.
- [x] Represent and check documented extension OS and PostgreSQL subsets without hiding architecture gaps; MobilityDB and online_advisor still need project-level inclusion decisions.
- [ ] Drive builds, endpoint tests, and candidate inventory generation from the intended-support source. The Linux pilot selector now chooses one missing declared core target per architecture when no version is supplied; without durable inventory entries, repeated dispatches select the same target. Demonstrate that a routine support addition does not require editing parallel workflow lists across all platforms.
- [ ] Record immutable archive checksums, source versions, applicable upstream compatibility, test revision, environment, and results so evidence can be reused only while applicable.
- [ ] Retain verification records beyond pilot artifact expiry, including failed and skipped attempts; define a complete publication test profile before any record can establish eligibility.
- [ ] Require release evidence to map each redistributed component and version to its licence, notices, and any required source offer or source link; check those files in final archive bytes. Local preflight now checks explicit resolved declarations and included files for newly staged archives; pilot inventories still need normalization and obligation review, and legal sufficiency remains a publication decision.

## Archives and tests

- [ ] Produce self-contained `.tar.gz` PostgreSQL archives and a common extension installation layout for the declared targets. Exercise the documented installation procedure and relocation on clean supported systems.
- [ ] Verify tools, UTF-8 schema operations, enabled features, built-in and selected external extensions, licensing, and representative diagnostic failures against the final archive bytes.
- [ ] Retain matching debug symbols for advertised archives and verify representative loader, crash, and PostgreSQL log diagnostics. Both Linux architectures produce archive-bound GNU build-ID and DWARF indexes and passed CI missing-loader and PostgreSQL-log probes. Both macOS architectures passed fresh-runner UUID/dSYM validation, and Windows x86-64 passed PDB validation for 133 packaged modules. A crash capture, client collection guidance, and durable symbol retention remain.
- [ ] Test DDL written for each intended extension version against the next-highest selected package version, including the documented compatibility boundaries.
- [ ] Extend the archive-derived built-in extension checks beyond the Linux pilots. The Linux verifier now checks every control in its PostgreSQL 15.19, 16.15, 17.11 and 18.6 archives, including version-specific modules; other platform archives still need the same discovery and behaviour coverage.
- [ ] Keep routine checks within standard GitHub-hosted runner and storage limits; investigate any combination count that appears impractical before reducing coverage.

## Publication readiness

- [ ] Implement and test candidate inventory and publication logic without creating a GitHub Release. Local candidate generation and preflight have CLI entry points and tests for retained URLs, staged bytes, and explicit redistribution declarations. A filesystem dry run now tests ordering, retained references, checksums, and failures before the current inventory changes. GitHub upload checks and anonymous retrieval still require a publication-capable integration test. The eventual publication flow must place verified assets before a new inventory becomes public.
- [ ] Reassess the release restriction after each substantial milestone. Stop this goal when enabling releases becomes the appropriate next step, with a concrete proposed release action, evidence, remaining gaps, and the checks that require actual publication.
