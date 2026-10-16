# Testing spec

The overarching

## Test build outputs outside of the container used to build them

Before publishing a release, test the built archive on a clean supported systems, set up without any development utilities or dependencies that might be missing on client systems.

## Test the released artefacts

While we should test as much as possible before release, only a post-release test can check if the paths in inventory.json are reachable and really correspond to the correct downloads.

## Ensure sufficient test coverage that any incorrect information in inventory.json would fail a test

Go through inventory.json systematically and specify tests.

Test on different OS versions to verify that our declared OS support ranges are correct.

Whenever a range is claimed, it is sufficient to test the start and end of the range, not every version in between. This applies to OS versions, PG versions for extensions, and any other compatibility ranges ranges.

## Prefer data-driven tests

Prefer a metadata structure that defines intended support

## Optimise test execution time

If tests take longer than a few minutes iteration speed suffers.

Use parallelism for IO-bound tests and caching if appropriate.

For example, if much of the test time considers of running an unchanged test suite against combinations of Postgres and extensions that have been tested before, consider committing a record of test outcomes (making sure of course that test suite changes would invalidate the cache). This is an example not a suggestion.

## TEST07 — Verify failure behaviour

Test unavailable versions, corrupt archives, missing required files and conflicting packages as well as successful installations. Check that failures are reported accurately, do not silently substitute versions, and leave no running server or invalid download marked as usable.

These cases establish that clients can detect an unusable installation before relying on it.

## TEST08 — Make the checks repeatable

Required checks must run through repository test commands and the delivery pipeline. A written test procedure is complete only when its checks are implemented and produce retained results.

Connect each promised behaviour to a test that observes it. Where a required environment or test is unavailable, report the gap and keep that part of coverage incomplete.

## Exercise the intended use case

Tests must initialize a database, connect, execute representative DDL, inspect the resulting definitions and stop the server. Exercise the supplied command-line tools, enabled PostgreSQL features and each extension's schema functionality; successful startup or `CREATE EXTENSION` alone is insufficient.

## Follow the documented installation process

Tests must assemble installations using only the published archives, metadata and documented installation instructions. They must work as an ordinary user without undeclared setup or dependencies.

## Verify relocation

Repeat representative operations after moving the extracted installation to a different path, with the original location unavailable.

## Check intended coverage as well as published coverage

Compare available downloads with the versions and platforms required by the specifications and policy decisions. Report missing coverage separately from failures in published downloads.

## Identify exactly what passed

Retained results must identify the archive checksums, test revision and execution environment. Reused results must apply to the same artifacts and checks. Failed or skipped checks must remain visible.

## Account for known exceptions within compatibility ranges

Endpoint testing is the required sampling rule, not proof that every intermediate version works. Known intermediate incompatibilities must prevent advertising a continuous range even when both endpoints pass.

## Verify each inventory field

Verify every inventory field against build evidence or behavioural tests. For compatibility ranges, use the required endpoint tests and documented upstream compatibility. Passing sampled tests does not establish compatibility for every possible schema or environment within the range.

## Verify the debugging process

For representative failures, verify that the documented diagnostic collection process produces the information needed to investigate them. Cover both system-level failures, such as a library failing to load or a process crashing, and errors reported through PostgreSQL logs. There is no requirement to reproduce every possible failure.
