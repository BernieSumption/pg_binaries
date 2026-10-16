# Testing spec

Tests establish that our packaged PostgreSQL and extensions satisfy the functional spec. Agents choose the test machinery and representative cases.

Document testing decisions and their reasoning in `policies/testing.md`, explaining how the chosen checks satisfy this spec.

`policies/delivery-process.md` specified elsewhere also relates to tests in that it documents the role tests play in delivering routine additions to the inventory.

## Test the archives on supported systems before publication

Before publication, test the final archives on clean supported systems, outside the environment used to build them. The test systems must not supply development tools or dependencies that would hide missing files in our downloads.

Assemble installations using only the archives, their metadata and the documented installation process. PostgreSQL must run as an ordinary user without undeclared setup or dependencies.

Test each supported OS and architecture. For compatibility ranges, testing the start and end is sufficient; testing every intermediate version is not required. This applies to OS versions and PostgreSQL versions supported by an extension build. Known intermediate incompatibilities must prevent advertising a continuous range even when both endpoints pass.

## Treat the documented install process as a tested asset

This process is designed to be implemented by client library. During tests, we should make our own implementation, use agents to verify that our implementation is a faithful reproduction of the install process, and confirm that it works.

## Exercise the intended use case

Initialize a UTF-8 database, connect, execute representative DDL, inspect the resulting definitions and stop the server cleanly. Exercise the supplied command-line tools, enabled PostgreSQL features and each extension's schema functionality.

Comprehensive testing of extension functionality is not necessary. Consider executed DLL to be a smoke test to detect build, packaging and compatibility problems. For example, create an extension, create a table or function using its objects, and execute a representative operation with an expected result. Successful startup or `CREATE EXTENSION` alone is insufficient, but we do not need to duplicate upstream's comprehensive tests.

## Verify relocation

Move the extracted installation to a different path and repeat representative operations with the original location unavailable. PostgreSQL and its extensions must still work using the documented installation process.

## Test the published downloads

After publication, retrieve the public inventory and check that its download URLs are accessible without authentication. Verify checksums and establish that the downloaded bytes are the same archives that passed pre-publication testing.

Include downloads referenced from older releases. A successful local build does not establish that the public release contains the correct files or that clients can obtain them.

## Verify inventory claims and report coverage

Verify every inventory field against build evidence or behavioural tests. Check versions, included extensions, prerequisites and platform compatibility. Compatibility claims must also respect the upstream documentation required by the functional spec.

Compare available downloads with the versions and platforms required by the specs and policy decisions. Report missing intended coverage separately from failures in published downloads. Failed or skipped checks must remain visible and must not count as passing evidence.

The ambition is that any incorrect fact in the inventory would cause a test failure. If that is not possible, then get as close as practical with the available compute.

Retain enough information to identify the archive checksums, test revision, execution environment and results for each verification. Passing smoke tests establishes the tested behaviour; it does not prove that every possible schema works.

## Stay within free GitHub runner limits

Be aware of the free runner limits and consult them when deciding how many tests to run, and do not design a system that cannot be effectively run within this.

Switching to a paid plan is an option, but would require going through HUMAN_REVIEW_QUEUE.md.

## Verify that failures can be investigated

For representative failures, verify that the documented diagnostic collection process produces the information needed to investigate them. Cover both system-level failures, such as a library failing to load or a process crashing, and errors reported through PostgreSQL logs. There is no requirement to reproduce every possible failure.

## Keep testing proportionate

Prefer tests driven by intended-support metadata over a manually maintained list of combinations that is difficult to check for completeness.

Keep routine feedback fast and avoid repeating expensive checks when the relevant archives, tests and environments have not changed. Reused results must remain applicable to what is being verified.

The intention is not to require thousands of test combinations. If the requirements imply that scale, add an item to HUMAN_REVIEW_QUEUE.md proposing alternatives rather than silently reducing coverage.
