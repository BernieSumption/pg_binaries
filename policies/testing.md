# Verification of packaged downloads

Clients use downloaded archives to create and inspect PostgreSQL schemas. Verification must run against final archive bytes, using the installation procedure in [install-process.md](install-process.md), because a successful build does not establish that a client can use the package.

## Evidence and eligibility

Each verification record must identify archive SHA-256, source and component versions, test revision, operating system and architecture, environment image or runner version, test cases, and outcome. A failure, skip, missing record, or record for different bytes or tests must not satisfy a claim. A build and its verification may be reused only when their inputs and claimed compatibility remain applicable. The coverage report described in [delivery-process.md](delivery-process.md) must distinguish missing intended coverage from broken published downloads.

Before an archive is eligible for publication, a verifier outside its build environment must assemble the installation from archives and metadata alone. The verification environment must not supply development files or unbundled runtime libraries that conceal missing dependencies. A fresh job on a developer-equipped image, by itself, does not establish this property. Record the exact operating system and runtime dependency checks used to establish it.

For each supported OS and architecture, verify the minimum supported OS and a current supported OS. For an extension archive claiming a PostgreSQL range, verify both range endpoints. A known incompatible intermediate version splits the range even if its endpoints pass. A new PostgreSQL release, OS baseline, dependency, or test revision must invalidate only the evidence it affects; unchanged applicable results may be reused.

## PostgreSQL and extension behaviour

From the extracted archive, run `initdb` as an ordinary user with UTF-8 encoding, start `postgres` with `pg_ctl`, connect through packaged `psql`, apply representative types, collations, defaults, constraints, indexes, views, functions and procedures, inspect the resulting definitions through catalogues, and stop cleanly. Exercise `pg_dump` and restore the dump with `pg_restore` into a new database, then verify restored definitions. Assert expected results rather than relying on a zero exit status or printed output alone.

Discover included built-in SQL extensions from the final PostgreSQL archive and verify the inventory claim against that discovery. Exercise representative schema behaviour for each advertised built-in extension and enabled option. For each external SQL extension, create the extension, use at least one of its objects in DDL, execute a representative operation, and check its result. These checks detect packaging and compatibility failures; they do not replace upstream's full test suite. Verify version, prerequisite and platform claims against archive metadata, documented upstream compatibility, and endpoint results.

Assemble PostgreSQL and extensions with the documented copy procedure, run representative operations, move the assembled installation, make the old path unavailable, and repeat the operations. Check required data files and library loading after relocation. An agent review of the test installer must confirm that it follows [install-process.md](install-process.md) without undeclared setup.

## Diagnostics and published bytes

Follow [debugging.md](debugging.md) to collect a representative server log error and a system-level loader or crash failure. Verify that retained evidence lets a maintainer identify the archive and investigate the failure, including symbol resolution where applicable.

After a release, retrieve `inventory.json` anonymously from the public latest-release URL. Download every referenced archive, including those on older releases, verify its checksum, and compare its bytes with the archive that passed pre-publication tests. A local candidate inventory cannot substitute for this published-download check.

## Cost and current coverage

Routine checks must use metadata-derived combinations and reuse valid evidence so they can run within standard GitHub-hosted runner limits. If complete required coverage would imply thousands of combinations, put a proposed resolution in `HUMAN_REVIEW_QUEUE.md` before changing the test requirement.

The current pilot scripts exercise a subset of PostgreSQL 18.6 and pgvector 0.8.7 on x86-64 Linux, macOS and Windows, plus PostGIS 3.6.4 on Linux. The Linux pilot records the built-in extension names found in its core archive, checks that claim after extraction, exercises seven named built-ins, and rejects unbundled non-glibc ELF dependencies; it does not yet exercise every advertised extension. The macOS pilot checks the built-in inventory and assembles the extension before relocation. Historical passing jobs establish pilot behaviour only. They do not satisfy the eligibility rules in this policy until archive, environment and result evidence is recorded for the required support.
