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

The Linux x86-64 pilot accepts one declared PostgreSQL 15 through 18 minor at a time, defaulting to 18.6. The Linux arm64 pilot uses the same scripts and checks on a native Ubuntu 24.04 arm64 runner, with PostgreSQL 18.6 and pgvector 0.8.7 as its default target. Both check sixteen named built-in SQL extensions, enabled PostgreSQL options, dependency loading, dump and restore, and relocation. PostgreSQL 15 uses its supported numeric `pg_dump` compression option; PostgreSQL 16 through 18 use zstd. These pilots do not exercise every bundled extension or establish the declared product matrix. The arm64 workflow has been added, but no passing arm64 build and verification result is recorded yet.

The Linux x86-64 pilots for PostgreSQL [15.19](https://github.com/BernieSumption/pg_binaries/actions/runs/38954284096), [16.15](https://github.com/BernieSumption/pg_binaries/actions/runs/38954284089), [17.11](https://github.com/BernieSumption/pg_binaries/actions/runs/38952584371) and [18.0](https://github.com/BernieSumption/pg_binaries/actions/runs/38951633511) passed on Ubuntu 24.04 on 2026-10-16. The [macOS archive assembly and relocation pilot](https://github.com/BernieSumption/pg_binaries/actions/runs/38948048763) passed on macOS 15 x86-64. PostGIS 3.6.4 has a separate Linux x86-64 pilot. These results do not meet the eligibility rules above for the full intended support.

The [Windows x86-64 PostgreSQL 18.6 archive build and fresh verification](https://github.com/BernieSumption/pg_binaries/actions/runs/38949784738) passed on Windows Server 2022. That runner supplies the Visual C++ runtime, while the archive declares it as an OS prerequisite. The redistribution decision in [HUMAN_REVIEW_QUEUE.md](../HUMAN_REVIEW_QUEUE.md#windows-visual-c-runtime-redistribution) remains unresolved; this archive is not eligible for publication.
