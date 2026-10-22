# Verification of packaged downloads

Clients use downloaded archives to create and inspect PostgreSQL schemas. Verification must run against final archive bytes, using [the documented installation procedure](install-process.md), because a successful build does not establish that a client can use the package.

## Evidence and eligibility

Each verification record must identify archive SHA-256, source and component versions, test revision, operating system and architecture, environment image or runner version, test cases, and outcome. A failure, skip, missing record, or record for different bytes or tests must not satisfy a claim. Reuse evidence only while its inputs, checks and claimed compatibility remain applicable. [Coverage reporting](delivery-process.md) distinguishes missing intended coverage from broken published downloads.

When the [testing specification](../specs/testing.md#allow-non-code-patching-of-archives) permits reusing runtime results after a non-code archive patch, retain both archive checksums and a checked member comparison showing the exact changed files. A derived verification record must identify the original result and patch proof; validate the patched archive's current metadata and licence checks before using it in a candidate.

Publication profiles define the complete required case set. Records must give one passed, failed or skipped result per case and derive the aggregate result from those outcomes. Pilot smoke evidence cannot satisfy a publication profile merely by changing its label. Bind a profile revision to the test logic, outcome recording and environment; edits unrelated to verification should not invalidate otherwise applicable evidence. Preserve failed and skipped attempts even when a failure occurs before archives exist; such attempts cannot claim archive-bound results.

An extension record must identify the exact PostgreSQL archive and any prerequisite extension archives used to assemble the installation, including their versions and checksums. Candidate generation, coverage and publication preflight must match those bytes to the proposed downloads. Matching version numbers alone cannot establish that separately built archives work together.

Test each archive with every selected PostgreSQL release it supports. When the selected minor changes, test with the new core bytes before reusing an extension archive. Historical-minor endpoints and extension-version substitution tests are not required. A known incompatibility still prevents an affected claim. Each SQL extension advertised from a project archive needs a representative case, but those cases may share a job and installation where their prerequisites permit it.

Verify that every staged download contains the exact central licence pointer required by [the release policy](releases.md#licence-pointer). Licence declarations and decisions are maintained centrally in `LICENSES.md` and [licenses.md](licenses.md).

## Verification environments

Before publication, assemble the installation from archives and metadata outside the build environment. Use fresh standard GitHub-hosted runners for macOS and Windows. Prefer less developer-equipped environments where available; installed runner software must not silently become an archive prerequisite. Inspect native dependencies and restrict search paths where practical, recording the checks and their limits.

Run the routine Linux behavioural suite in one Alpine-based verification container per architecture, separate from the build environment and sharing the runner kernel. Keep verifier dependencies minimal and do not install host glibc to satisfy archive dependencies. Exercise the portable locale path as well as the operations below.

Assess the intended minimum OS using [build settings and dependency evidence](os-support.md). Minimum-OS execution, additional older-Ubuntu tests and QEMU guest tests are not routine release requirements. Existing guest tools may be useful for the proposed [manual post-release bug hunting](../HUMAN_REVIEW_QUEUE.md#backlog-ideas); that process remains pending discussion.

## Static analysis of packaged artifacts

Before publication, inspect the final archives for dependency and relocation invariants that can be checked without executing their contents. Cover every shipped executable and native library in the assembled PostgreSQL and extension installation, including transitive library dependencies. Required dependencies must resolve within that installation or to universal OS components permitted by [the OS support policy](os-support.md). Finding a dependency installed on the verifier does not establish that it is permitted.

Use established binary-format inspection tools to check architecture, declared imports, loader and library search paths, and available minimum-target metadata against the declared target. Check installation links and runtime configuration references for dependencies on build-machine paths. Resolve paths according to the platform's loading rules and the documented launch procedure after relocation. Absolute paths in debug information or other non-runtime metadata are not themselves portability failures.

Record the inspected files, tool versions, findings and analysis limits with the archive-bound verification evidence. Missing required dependencies and forbidden external references must fail verification. An unanalysed binary or unresolved loading rule must remain an explicit verification gap, not a passing result. Select additional static checks where they enforce a specified invariant and add useful coverage without duplicating existing checks.

Static inspection cannot establish all dependencies selected dynamically by application code or all data-file accesses. Retain behavioural and relocation tests for those paths; do not describe a passing import check as proof of complete independence from host files.


## PostgreSQL and extension behaviour

Run packaged `initdb` as an ordinary user with UTF-8 encoding, start PostgreSQL with `pg_ctl`, connect using packaged `psql`, apply representative types, collations, defaults, constraints, indexes, views, functions and procedures, inspect their catalogue definitions, and stop cleanly. Exercise `pg_dump` and `pg_restore`, checking restored definitions and representative results. Assert expected outcomes rather than relying on successful exit codes alone.

Discover built-in SQL extensions from the final core archive and compare them with inventory and manifest claims. Exercise representative schema behaviour for each advertised built-in extension and enabled option. For every selected external SQL extension, create it, use its objects in DDL, execute a representative operation and check the result. These are packaging and schema smoke tests, not exhaustive upstream functionality or cross-version equivalence tests. Select releases under [the shared version rule](delivery-process.md#declare-and-reconcile-support), without adding versions solely to preserve historical DDL behaviour.

Stage different versions of an extension separately, and assemble each test installation using only its selected archives and declared prerequisites. Check file collisions, runtime libraries and required support data. For example, TIGER Geocoder requires PostGIS and `fuzzystrmatch`; its smoke test can check address normalization without downloading Census data or claiming populated geocoding support.

Use ordinary file copying in a user-writable directory, then move the installation and make its original path unavailable before repeating representative operations. An agent review must establish that the test installer faithfully implements [install-process.md](install-process.md), without undeclared setup. Retain the review and test evidence with the relevant installer revision.

## Diagnostics and published bytes

Follow [debugging.md](debugging.md) to collect a representative PostgreSQL log error and a system-level loader or crash failure. Verify that retained evidence identifies the archive and supports investigation, including symbol resolution where applicable.

After publication, retrieve the public latest inventory anonymously, download every referenced archive including those on older release tags, and verify checksums against the tested bytes. Removing a superseded version from current support removes its coverage obligation; it does not permit changing bytes at an existing URL. A local dry run cannot establish public accessibility.

## Cost and implementation transition

Derive checks from selected target metadata, include prerequisites, and expose unresolved dependencies before expensive CI dispatch. Measure job duration and artifact storage, reuse applicable evidence, and keep batches within standard runner limits. Job grouping and parallel fan-out remain design options, not requirements of this policy.

The current declaration, selectors, range planner, workflows and publication profiles still implement parts of the previous version and OS contracts. Static analysis is also incomplete. Migrate them through [the version-policy backlog](../GOAL_BACKLOG.md#version-policy-migration) and the existing OS/static-analysis tasks before treating old green runs as evidence of the new contract. Historical results and implementation details are retained in [the transition history](../support/evidence/policy-transition-history-2026-10-17.md) and archive-bound records under `support/`; they are not additional release requirements.
