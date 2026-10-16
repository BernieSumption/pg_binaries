# Work towards release authorization

This backlog records work for the current development goal. The specifications define requirements; policies record decisions; verification records establish results. Items here do not change any requirement.

## Policy decisions

- [ ] Derive OS, PostgreSQL option, installation, testing, delivery, release, debugging, and extension policies from the specifications. Record source evidence and unresolved decisions. Do not infer required behaviour from the pilot scripts.
- [ ] Investigate whether a Linux archive can satisfy the kernel-only support declaration on clean supported distributions, including non-glibc systems. If no compliant approach is feasible within the allowed infrastructure, add the decision to `HUMAN_REVIEW_QUEUE.md`.
- [ ] Establish a supported OS minimum and practical clean-system tests for the minimum and current endpoints on all five OS/architecture combinations.
- [ ] Resolve Address Standardizer's US address-data redistribution rights before deciding whether its project can be included under the specification's hard licensing rule.
- [ ] Align optional PostgreSQL capabilities across platforms: provide and test `uuid-ossp` where advertised, and make the readline exclusion explicit in every build script.

## Support and coverage

- [ ] Define one authoritative intended-support source and a coverage report that shows every missing PostgreSQL version, platform, extension version, or verification result, including failed and skipped work.
- [ ] Represent and check documented extension OS and PostgreSQL subsets without hiding architecture gaps; MobilityDB and online_advisor are candidates that need this before an inclusion declaration.
- [ ] Drive builds, endpoint tests, and candidate inventory generation from the intended-support source. Demonstrate that a routine support addition does not require editing parallel workflow lists.
- [ ] Record immutable archive checksums, source versions, applicable upstream compatibility, test revision, environment, and results so evidence can be reused only while applicable.
- [ ] Retain verification records beyond pilot artifact expiry, including failed and skipped attempts; define a complete publication test profile before any record can establish eligibility.
- [ ] Require release evidence to map each redistributed component and version to its licence, notices, and any required source offer or source link; check those files in final archive bytes.

## Archives and tests

- [ ] Produce self-contained `.tar.gz` PostgreSQL archives and a common extension installation layout for the declared targets. Exercise the documented installation procedure and relocation on clean supported systems.
- [ ] Verify tools, UTF-8 schema operations, enabled features, built-in and selected external extensions, licensing, and representative diagnostic failures against the final archive bytes.
- [ ] Test DDL written for each intended extension version against the next-highest selected package version, including the documented compatibility boundaries.
- [ ] Extend the archive-derived built-in extension checks beyond the Linux pilots. The Linux verifier now checks every control in its PostgreSQL 15.19, 16.15, 17.11 and 18.6 archives, including version-specific modules; other platform archives still need the same discovery and behaviour coverage.
- [ ] Keep routine checks within standard GitHub-hosted runner and storage limits; investigate any combination count that appears impractical before reducing coverage.

## Publication readiness

- [ ] Implement and test candidate inventory and publication logic without creating a GitHub Release. It must retain unchanged URLs and place verified assets before a new inventory becomes public.
- [ ] Reassess the release restriction after each substantial milestone. Stop this goal when enabling releases becomes the appropriate next step, with a concrete proposed release action, evidence, remaining gaps, and the checks that require actual publication.
