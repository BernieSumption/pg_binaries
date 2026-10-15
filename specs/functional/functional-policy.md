# Functional policy

These guarantees define the product. Implementation items describe how to satisfy them.

## Purpose and boundary

This repository supplies PostgreSQL binaries, extension binaries and download metadata for schema migration tools. A tool reads its SQL files upfront, identifies required extensions, and asks a separate client library to obtain an installation, start PostgreSQL and return a connection.

We provide standard binaries runnable through ordinary shell and process tools. SQL parsing, version-selection defaults, process lifecycle and connection APIs belong to the client. The database's short lifetime motivates small downloads; schema and DDL compatibility determine what those downloads must contain.

## Inventory, coverage and downloads

FEEDBACK: functional-inventory.json belongs outside specs, it's part of the implementation - the initial downloadable asset that clients will fetch to learn what releases they can download and from where.

The **inventory** is the authored coverage policy: version ranges, platforms and capabilities we intend to offer. **Release discovery** expands that policy into exact upstream releases at a dated snapshot. A generated **coverage report** records progress, including failed builds and unresolved research. The **download catalogue** lists currently verified, publicly downloadable artefacts.

This separation keeps the definition of success stable while builds catch up. A missing download remains missing coverage.

## Versions and builds

Three decisions determine which archive a client downloads:

1. **Which releases we offer:** the inventory's cutoff and compatibility rules select upstream releases. See [release selection](functional-inventory-format.md#1-release-selection).
2. **Which versions a client requests:** the client supplies its PostgreSQL and extension versions, using catalogue metadata to apply its own selection policy.
3. **Which build serves that request:** one extension archive may serve several PostgreSQL minors after verification on each. Metadata records its exact build target separately from its verified runtime range. See [artifact records](functional-inventory-format.md#7-artifact-records-and-download-catalogue).

A packaging correction can replace the current archive without changing its upstream versions. New downloads receive the corrected build under a new checksum-bearing filename. See [corrected builds](functional-policy.md#f11--corrected-builds-are-the-normal-download).

## F01 — Version coverage remains visible

Offer every stable PostgreSQL release in majors 15 and later published on or after 25 September 2025 on all three target platforms. There is no upper major-version limit. Apply that fixed, inclusive cutoff to every selected extension source release that contains the requested SQL extension and supports a target PostgreSQL version. Include eligible maintenance releases and overlapping extension version lines; exclude prereleases and PostgreSQL <=14.

Build failures, missing ports and unknown compatibility remain incomplete targets. Exclude a combination from the applicable matrix only with evidence of upstream incompatibility.

**Why:** Schemas may depend on a particular extension release. Coverage policy must remain independent of build progress.

## F02 — Exact choices can be discovered

Metadata must identify PostgreSQL versions, SQL extension names and exact version strings, upstream source releases, platform/OS constraints, dependencies and available builds. A source release and its SQL extension versions are separate identities.

The catalogue has no version-selection defaults or silent substitutions. Report unavailable requests and ambiguous source/version choices explicitly. An upstream control-file default may be recorded as an upstream fact.

**Why:** The client chooses versions before startup and needs enough information to implement its own selection policy.

## F03 — SQL extensions can be obtained separately

Each selected SQL extension must be independently requestable. Record the dependency names declared by its upstream control files, without dependency-version recommendations, researched compatibility ranges between extensions or a general version-resolution system. Follow upstream SQL extension boundaries: requesting `postgis` must not force downloads of optional raster, topology, SFCGAL, standardizer or TIGER extensions.

Clients decide how to handle declared dependencies. For example, a client may reject `CREATE EXTENSION ... CASCADE` when it would create a prerequisite not explicitly created beforehand. This repository imposes no such client policy.

Packages may share source builds and explicit runtime dependencies. Each package lists its SQL names, installable SQL versions and required packages. Shared files have declared ownership; installing one package must not silently replace another's files with different bytes.

**Why:** Static analysis may find a single `CREATE EXTENSION` name. Its dependencies must be discoverable without downloading unrelated functionality.

## F04 — Relocation requires no system provisioning

The same artifact must work throughout its advertised OS range after extraction and after moving the installation directory. Bundle or statically link non-OS libraries and required resources. No builder paths, tools, package-manager installation, administrator rights, service setup or runtime installer may be required.

Prioritize the current OS release supporting each architecture. Prefer coverage back four years, ignoring older releases; narrow that window when older support compromises current support, recording the reason and evidence. Publish exact assessed OS releases, Linux libc/ABI requirements and CPU requirements. Windows Server tests alone do not establish desktop Windows support.

Builds must avoid accidental host-specific CPU tuning. Required environment/configuration values must be documented and derivable from the extracted prefix without machine-wide changes.

**Why:** The client needs to start an ordinary process on the user's machine without provisioning the OS.

## F05 — Standard tools and schema operations work

Include `postgres`, `initdb`, `pg_ctl`, `psql`, `pg_dump` and `pg_restore` with their support files. They must initialize UTF-8 databases, run under an ordinary user, accept connections, apply representative DDL, expose its definitions through PostgreSQL catalogues and stop cleanly. Schema-only dump/restore must preserve the tested definitions.

The DDL corpus covers schemas, types, functions, tables, constraints, indexes, views, sequences and version-appropriate features. Ship PL/pgSQL, enumerate bundled SQL extensions by name/version, and supply dependencies such as `fuzzystrmatch` where required. The remaining contrib selection needs research.

**Why:** Schema inspection requires standard PostgreSQL behaviour. Production operation and cross-major data-directory upgrades are outside the [project boundary](functional-policy.md#purpose-and-boundary).

## F06 — ICU and libc collations are usable

Every PostgreSQL artifact must support both providers. Verify creation and use of an ICU collation with representative supported locale options, and a libc collation available on the test host. Record the ICU version and host locale availability separately.

Locale inventories and sorting results may differ across OS and ICU versions. Report a missing host locale separately from missing provider support.

**Why:** Schema SQL declares collations, but their availability depends on both the binary and the host.

## F07 — Capability inclusion follows schema requirements

Apply the [build policy](../build/build-policy.md) to optional PostgreSQL build options. Inclusion and exclusion follow its criteria; conflicts and exceptions require human review.

Include upstream-supported zlib, LZ4 and Zstandard compression operations. Each advertised capability must state its applicable PostgreSQL range, dependency versions, activation requirements and verification test. Use a sourced `not_applicable` result for operations absent from an upstream release.

Extension installation must preserve core capabilities. Record inclusion outcomes in build items and the inventory, with supporting evidence and verification requirements.

**Why:** A successful build can omit SQL-visible features; policy and tests must establish the promised functionality.

## F08 — Each advertised extension combination works

For every advertised extension source/SQL version, PostgreSQL minor and platform, verify the final archives on the claimed OS range with required dependencies. They must install the requested SQL version and pass representative DDL and queries.

Record the exact PostgreSQL build target separately from compatible runtime versions. Reuse across minors requires verification on each minor; newly released minors start unverified. Record the exact dependency versions used and test that concrete combination. A pass promises no compatibility with other dependency versions. Compatibility between arbitrary unrelated extensions is the application's responsibility.

PostgreSQL permits one version of a named SQL extension per database. Installing several SQL script versions does not prove that their compiled libraries can coexist. Metadata must let the client select an isolated installation when necessary.

**Why:** Artifact reuse saves compilation and storage, while each advertised combination still needs evidence.

## F09 — Resource scope follows the schema task

Bundle libraries and resources required for schema initialization and supported DDL. Exclude very large external datasets used only for application queries, cluster maintenance, administration or populating data tables. Retain small upstream-default files unless removal has a tested justification.

Document excluded data's provenance, loading procedure and affected operations. TIGER's bulk Census data populates application tables; it is unnecessary for extension creation. Coordinate definitions needed by advertised PostGIS operations must remain available after relocation.

Covered schema tests must work offline after installation. Data-dependent DDL, such as populating a materialized view, can still require application inputs; document those requirements.

**Why:** Bulk application datasets would inflate schema-tool downloads. Trimming small defaults risks behaviour changes for little saving.

## F10 — Archives and installation requirements are inspectable

Every archive filename must contain its full SHA-256 checksum, matching its catalogue entry and downloaded bytes. Each archive must have a declared format, manifest, file ownership list and relative installation layout. Its contents and catalogue entry must agree. Paths and links must stay inside the extraction destination; overlays must preserve permissions and declare file conflicts.

The reference consumer must detect unsupported PostgreSQL/platform requests, corrupt archives, missing package files and conflicting files before starting PostgreSQL. It does not solve SQL-extension dependency versions.

**Why:** Clients need sufficient metadata to assemble a consistent installation from separate downloads.

## F11 — Corrected builds are the normal download

A correction may replace the current build for the same upstream versions. New resolutions must select that build, using build identities and checksums to detect stale cache entries and verify downloads. Changed bytes must have a new checksum-bearing filename and URL. Publication must keep catalogue entries consistent with available bytes.

Retain compact provenance and test results for diagnosis; superseded binary builds need not remain downloadable indefinitely. A correction must preserve the requested upstream versions.

**Why:** Users of this development utility should receive fixes without managing a production dependency lockfile.

## F12 — Downloads include redistribution obligations

Downloads must be free and public without authentication. Include applicable licence texts, notices and component/version mappings, plus any required source offers or source links. Resolve redistribution obligations before advertising a component. Original repository code and documentation use the [MIT licence](../../LICENSE); bundled upstream components retain their own licences.

**Why:** Clients must be able to retrieve and redistribute the packages with their associated obligations.

## F13 — Metadata serves clients and human readers

Represent version ranges, platform requirements, dependencies, capabilities, limitations and startup settings in structured fields. Use scoped notes for explanations, with links to extension profiles for detailed research. Identify generated discovery and coverage records by snapshot date and inventory revision.

**Why:** Clients need actionable fields; human reviewers need the same facts with enough context to understand them.
