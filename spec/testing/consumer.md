# Reference consumer tests

Test an explicit request through catalogue metadata, public downloads and
standard PostgreSQL tools. This level covers F02, F03, F05 and F10–F13 and checks
that F01/F08 availability constraints reach the requester. Follow the shared
[execution and record rules](README.md).

The reference consumer is a test harness. Fixtures supply selected SQL extension
names and versions; SQL parsing, a connection library and a production lifecycle
API are outside its scope. Fixtures explicitly select prerequisite versions;
the harness does not infer or recommend them. It must run a supplied SQL file or open packaged
`psql` interactively.

## Successful requests

For core-only requests and each selected module with its dependencies:

1. Read a dated catalogue and select exact PostgreSQL, source and SQL versions
   plus platform. Preserve SQL version strings exactly.
2. Resolve current available builds for the requested runtime and OS. Report
   explicitly selected extension builds and their native/shared-runtime packages
   with build IDs, URLs, hashes, file ownership and activation settings.
3. Download without authentication or payment, verify hashes against metadata and filenames, inspect paths and
   manifests, and extract into a user-owned prefix. Reject file conflicts.
4. Apply declared prefix-relative settings, initialize UTF-8, start PostgreSQL
   and execute the fixture's explicit prerequisite and extension SQL. Check server,
   SQL-extension and native-library identities.
5. Apply a schema fixture with SQL errors treated as failures, then inspect its
   catalogue objects. Separately open packaged `psql` in a real terminal,
   query versions/objects and exit. Stop PostgreSQL and check for orphan processes.

The flow must require no runtime installer, service setup, system package
installation or elevated privileges. The artifact suite tests detailed
capabilities; these cases verify discovery and installation through metadata.

## Failure cases

| Condition | Required result |
| --- | --- |
| Missing version selection | Show choices or an incomplete request; select no default. |
| Unavailable version/platform | Report absence and its known reason without substitution. |
| Same version spelling from different source projects | Preserve source identities and request disambiguation. |
| Unverified PostgreSQL minor | Reject an inferred compatibility claim. |
| Missing selected artifact or native/shared-runtime package | Identify it during preflight, before startup. |
| SQL prerequisite not created | Preserve PostgreSQL's error from the supplied SQL; do not silently select a version or create it. |
| Unsupported OS/CPU | Reject where inspectable; never present unresolved support as verified. |
| Corrupt/truncated archive | Fail SHA-256 verification before extraction; do not cache as valid. |
| Traversal path or escaping link | Reject before writing outside the destination. |
| Conflicting file ownership | Identify the packages and reject different bytes at the same path. |
| Missing resource or activation metadata | Fail the affected operation and report the gap; fetch no undeclared data. |

Use controlled fixtures for corruption and unsafe paths. Failed attempts must
leave no running server or successful cache entry. Diagnostics identify the
requested versions and failure.

## Corrected builds and caching

Resolve an upstream version selection V to build A and cache verified A bytes.
In a controlled publication fixture, replace A with corrected build B for the
same V, with a new identity/hash, checksum-bearing filename and URL, and consistent dependency records. A new
resolution must select and verify B and recognize A as stale. Requested
upstream versions must remain unchanged.

Check publication transitions: the current catalogue must always reference
available bytes with the stated hashes. Interrupted or mixed downloads must
fail integrity checks. The test cannot depend on superseded A remaining
publicly downloadable; retain its compact diagnostic record.

## Metadata completeness

Check that choices, dependencies, requirements, capability states and absence
reasons can be read from structured JSON. Preserve scoped explanatory notes.
Distinguish intended policy from dated verification and current downloads.

A warm cache must still validate the selected build and checksum. Controlled
fixture results do not establish public availability; that requires the real
download route.
