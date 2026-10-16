# Testing policy

Clients need to know that the downloads they select can run PostgreSQL and load their schemas on a supported machine.

Tests must demonstrate the [functional guarantees](../functional/functional-policy.md) through the following checks.

## TEST01 — Check each build before distributing it

Check that a build uses the requested source versions and settings, and that its archives contain the promised programs, extensions, libraries, resources and licence texts. Compare the files with their metadata and run a short startup and extension test.

This catches incorrect or incomplete packages before testing them on other machines.

## TEST02 — Prove that the archives work away from the builder

Test the final archives on clean supported systems, without access to the build machine's files or installed dependencies. Run as an ordinary user, move the extracted installation, and repeat the checks using only documented settings.

Apply and inspect representative schemas, install the selected extensions, and exercise the advertised features and schema dump/restore. These operations must work offline after downloading the packages. The tested archive bytes must be the bytes distributed to clients.

## TEST03 — Test the client's download and startup path

Use a reference test client to request explicit PostgreSQL and extension versions through the public metadata. Download without authentication or payment, assemble the installation, start PostgreSQL, run supplied SQL and exercise the packaged `psql` interactively.

The client must obtain everything it needs from the downloads and their metadata, without system provisioning or build-tree files. Check that it receives the requested versions, including the current corrected build when one replaces an earlier build of those versions.

## TEST04 — Account for the whole promised range

Check coverage against every eligible release in the inventory. For each extension version, test every PostgreSQL minor and OS range advertised as compatible.

Use explicitly selected prerequisite extension versions and record the combination tested. That result applies to that combination; it does not establish compatibility with other prerequisite versions or arbitrary extension pairs.

Keep failed builds, failed tests and missing checks visible. A release cannot disappear from the coverage report because it is difficult to build. Passing local tests alone does not establish that a download is publicly available.

## TEST05 — Keep a record of what passed and failed

For each test run, retain what was tested, on which system, how it was tested and the result. Identify the exact archives and dependency versions so a later corrected build cannot be mistaken for the tested build.

Keep enough commands, settings and diagnostic output to investigate a failure and repeat the test. Preserve this history even when temporary archives or superseded downloads are removed.

## TEST06 — Retest claims affected by a change

Changes to binaries, dependencies, resources or packaging require the affected archive tests to run again. Changes to metadata or download selection require the affected client tests.

Every new PostgreSQL minor needs its own runtime verification, even when an extension archive is reused. Earlier results remain usable only for checks whose tested inputs and environment still apply.

## TEST07 — Verify failure behaviour

Test unavailable versions, corrupt archives, missing required files and conflicting packages as well as successful installations. Check that failures are reported accurately, do not silently substitute versions, and leave no running server or invalid download marked as usable.

These cases establish that clients can detect an unusable installation before relying on it.

## TEST08 — Make the checks repeatable

Required checks must run through repository test commands and the delivery pipeline. A written test procedure is complete only when its checks are implemented and produce retained results.

Connect each promised behaviour to a test that observes it. Where a required environment or test is unavailable, report the gap and keep that part of coverage incomplete.
