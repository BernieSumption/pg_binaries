# Artifact tests

Test final archives independently of the builder. This level establishes
F03–F10 and F12 for exact bytes and supplies runtime evidence for F01,
F02 and F11. Follow the shared [execution and record rules](../../testing-policy.md) and
[coverage requirements](coverage-verification.md).

## Clean environment

Use a separate verifier with no build tree or project dependency installation.
Download the archives, verify their SHA-256 values against metadata and filenames, inspect
paths and links, then compare extracted files with the manifest. Public
availability also requires the [consumer download check](consumer-verification.md).

Permit core OS libraries and verification tools, but do not install a missing
runtime to make a test pass. A CI image may contain extra runtimes; document
these and check loaded libraries against the declared OS components and package
closure. Detect builder/package-manager paths and test resource lookup with
only the documented environment.

## Startup and relocation

Extract to location A, initialize a UTF-8 cluster in a user-owned directory,
start with packaged `pg_ctl`, connect with packaged `psql`, check the version
and execute a query. Stop, move the installation to B, remove access to A and
repeat startup and the schema/capability cases below. Include spaces and
non-ASCII characters in the installation paths and quote them correctly.

Use only documented prefix-relative settings. Require no administrator rights,
service or runtime installation. After each run, confirm clean shutdown and no
orphaned server. Record timings if useful; no startup threshold is specified.

After downloading all packages, disconnect external network access while
allowing local database connections. Schema and resource cases must complete
offline so missing resources cannot be fetched silently.

## Identity and schema behaviour

Check exact versions of the server and packaged `postgres`, `initdb`, `pg_ctl`,
`psql`, `pg_dump` and `pg_restore`. Compare bundled SQL names/versions with
metadata, including PL/pgSQL and required `fuzzystrmatch`.

Create each requested extension with an explicit SQL version. Check
`pg_extension.extversion`, installed scripts/control files and native-library
identity. Use an upstream version-reporting function where available and
loaded-library paths/hashes otherwise. SQL version alone cannot identify the
loaded native library.

Apply a version-appropriate fixture with schemas, enum/domain types, SQL and
PL/pgSQL functions, tables, sequences/identity columns, constraints, indexes,
views and partitions. Inspect catalogue definitions and execute representative
queries and constraints, including an expected constraint failure. The
[pilot fixture](../../../../tests/schema.sql) is a starting point; assess its syntax
and coverage for each major.

Create a schema-only archive with `pg_dump` and restore with `pg_restore` into
an empty database with required extension files available. Compare definitions,
extension versions, constraints, indexes and function/view signatures. Keep
both databases on the requested server version. Application-row preservation,
data-directory upgrades and cross-major upgrades are outside this test.

## Core capabilities

| Capability | Observation |
| --- | --- |
| ICU | Create/use an ICU collation with representative locale options; record ICU version and provider metadata. |
| libc | Discover an available host locale and create/use its libc collation; record the locale inventory. |
| Compression | For the exact major, exercise every advertised TOAST method, WAL compression operation and compressed dump/restore format. Observe the result or format. |
| XML | Create an XML column and SQL definition using an XML operation; query a small value and verify behaviour after schema restore. |
| TLS | Start with a disposable certificate/key, connect with packaged `psql` using certificate verification, and confirm encryption in server metadata. A wrong trust certificate must fail. |

XML and compiled TLS support are included by the capability policy. Determine operation applicability
from each major's upstream documentation: an algorithm may support different
operations across majors. Record upstream absence as sourced `not_applicable`;
missing compiled support for a required applicable operation fails.

Use compressible fixtures and meaningful observations without requiring exact
compressed sizes. Read back data when testing a dump compression format. Keep
this small data round trip separate from schema-only verification. Collation
results need not be identical across ICU versions or host locale inventories.

## Independent modules and resources

For each SQL extension, start with fresh core files, explicitly selected prerequisite
versions and required native/runtime packages. Record exact identities; the pass
applies only to this combination. Test optional operations with their fixture-selected
modules separately. Do not generate a dependency-version compatibility matrix.
Installing `postgis` alone must not require its optional companion modules.

Reject conflicting file ownership before overlaying packages. After installation,
repeat core probes affected by shared libraries so an extension cannot silently
remove a core capability.

Record resources used by representative operations. Verify that required
PROJ/GDAL resources and coordinate definitions resolve inside the moved prefix.
Check small upstream-default tables/files. Document excluded datasets, loading
methods and affected operations without adding bulk data to schema fixtures.

## Extension observations

Use release-specific signatures and expected results from each profile. Add
cases when an API or dependency change exposes a gap.

| Module | Minimum observations |
| --- | --- |
| [vector](../../../extensions/items/planned/vector.md) | Create vector columns and HNSW/IVFFlat indexes; insert known vectors; verify nearest-neighbour results and index/type definitions. |
| [postgis](../../../extensions/items/planned/postgis.md) | Create geometry/geography columns and a spatial index; test a GEOS operation and a numeric EPSG transformation offline after relocation; report dependency versions. |
| [postgis_raster](../../../extensions/items/planned/postgis_raster.md) | Create a raster column; construct/read a known pixel; inspect drivers; round-trip a fixture through each advertised import/export driver with declared settings. |
| [postgis_topology](../../../extensions/items/planned/postgis_topology.md) | Create a topology and topology-backed table, add geometry, inspect metadata and test an edit/query. |
| [postgis_sfcgal](../../../extensions/items/planned/postgis_sfcgal.md) | Create a dependent SQL definition; test a known 3D operation and representative APIs gated by the selected SFCGAL version. |
| [address_standardizer](../../../extensions/items/planned/address_standardizer.md) | Create without PostGIS or US data where permitted; inspect function/result types and normalize an address using fixture rules. |
| [address_standardizer_data_us](../../../extensions/items/planned/address_standardizer_data_us.md) | Check lexicon/gazetteer/rule seed content; add the fixture-selected parser and normalize an address with supplied defaults. |
| [postgis_tiger_geocoder](../../../extensions/items/planned/postgis_tiger_geocoder.md) | Create with PostGIS/fuzzystrmatch; inspect `tiger` schema and lookup/configuration objects; normalize an address without Census data. This does not test Census geocoding. |

Test every advertised directly installable SQL version in a separate database.
Advertised update paths need fixtures too; exhaustive production upgrades are
outside scope. Isolate alternate native providers with conflicting file paths.

## OS and PostgreSQL coverage

Test the same artifact on the oldest and current claimed OS releases and any
intermediate releases needed to justify the range. Until assessment resolves
exact releases and narrowing, keep those targets unresolved. An oldest-host
pass alone establishes neither current nor intermediate OS support.

Every advertised PostgreSQL minor needs verification of the same extension
archive hash, including SQL/data packages. Attach required OS tests to each
coverage row. Shared path/manifest checks may reuse evidence for unchanged
artifacts and environments; untested server minors cannot inherit a pass.

Windows desktop claims require tests without a preinstalled non-OS CRT masking
missing files. Linux records must identify libc family/version and distribution releases;
macOS tests must use the claimed Intel environments. The pilot's Windows Server
result does not satisfy desktop coverage.

An artifact pass alone does not establish public download availability.

## Completion

Implement these checks under [T01–T05](../../testing-policy.md), connect them to the pipeline and retain verification records. See the [requirement map](../../testing-notes.md#requirement-map) for the guarantees they establish.
