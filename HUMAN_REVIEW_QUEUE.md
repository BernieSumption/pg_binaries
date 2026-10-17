# Human review queue

## Temporary production release scope

The [functional specification](specs/functional.md) currently requires every qualifying stable PostgreSQL 15+ release on Linux, macOS and Windows, plus the extension versions selected under its compatibility rule. A production release containing only a subset would conflict with that requirement even if `support.json` and coverage reporting kept the missing targets visible. The current declaration has 105 PostgreSQL platform/version targets and 2,291 extension SQL targets, grouped into 234 candidate extension builds. These are target claims rather than 2,291 independent CI jobs, but required endpoint and SQL-name checks still need measured batching or evidence reuse. The [testing specification](specs/testing.md) asks for a proposed alternative if the requirements imply thousands of test combinations. A latest-version release would reduce historical build and compatibility work but would not itself resolve archive dependency verification, redistribution obligations or post-publication retrieval checks.

Proposed first scope, if a staged production rollout is desired: PostgreSQL 18.6 and pgvector 0.8.7 on Linux x86-64 and arm64, retaining all bundled PostgreSQL extensions. These targets have the most developed publication-profile checks. PostGIS 3.6.4 and TIGER Geocoder 2025.2 are promising next additions on the same two platforms, but their larger dependency and redistribution review should not delay the smaller first set. PostgreSQL 17.11 is the next candidate core version. This proposal is a sequence for review, not an exception under the present specification; none of these assets is ready to advertise until the applicable Linux portability and redistribution requirements pass.

Decision needed: Keep the present full-support requirement before the first production release, or amend the specification to permit an explicit initial release subset while retaining the full intended-support declaration and visible unmet coverage? If allowing a subset, decide whether the proposed Linux PostgreSQL 18.6 plus pgvector scope is appropriate, and state which guarantees apply to it. Until the specification changes, the full-support requirement remains in force.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.
, different distros
