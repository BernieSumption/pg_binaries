# Inventory and generated metadata

Format version 1. This reference defines the authored inventory, release discovery, coverage report and download catalogue introduced in the [specification guide](README.md#inventory-coverage-and-downloads).

## 1. Release selection

The inventory changes when policy or compatibility rules change. New patch releases normally update generated discovery and coverage only, preserving a stable definition of success.

Dates are ISO `YYYY-MM-DD` publication dates in UTC. Select actual stable releases on or after the inclusive cutoff, within PostgreSQL's inclusive `major_range`. An omitted upper bound includes future stable majors; the policy sets only a floor of 15. Include eligible `.0` releases; exclude prereleases and releases below the floor. Missing or contradictory dates create research work. Preserve upstream date evidence rather than inferring dates from tags or schedules.

Source projects declare version ordering. `numeric_tuple` compares dot-separated nonnegative integers with trailing zeros padded for comparison. Normalize source tags explicitly while retaining their original spelling; unrecognized formats need research. SQL extension version strings remain exact and use no assumed numeric ordering.

A source range is `{ "all": true }` or a conjunction of `gte`, `gt`, `lte`, `lt` bounds. Missing bounds are unbounded; `all` cannot be combined with bounds. Multiple extension `sources` entries are alternate source projects. A selected release must actually contain the SQL extension; establish absence from source evidence.

## 2. Expected compatibility

A compatibility rule maps a source-version interval to a PostgreSQL-major interval. Optional `sql_names` restricts it to named extensions; otherwise it expresses a source-wide expectation. For minor-level constraints, `postgresql_versions` may contain a union of bounded `gte`/`lt` intervals, intersected with selected releases.

These rules guide research and testing. Check each release and extension before advertising compatibility. Unmatched releases remain `research_required`, including eligible older maintenance branches and newly released PostgreSQL majors. The open-ended PostgreSQL policy does not extend a researched extension compatibility range automatically. A source-wide build requirement can exclude an independently packaged SQL extension only if it applies to that extension. Conflicting overlapping rules are invalid; array order gives no precedence.

## 3. Dependencies and SQL versions

| Field | Meaning |
| --- | --- |
| `required_sql_names` | Dependency names declared by upstream control files, checked per exact source/SQL version |
| `creation_dependencies_status` | `expected_requires_release_checks` or `research_required`; an unresolved empty list proves nothing |

Copy names from each release's applicable primary and version-specific control files. Do not infer additional SQL dependency edges from usage, recommend dependency versions or research cross-extension version ranges. Operation notes may explain, for example, that normalization uses a parser even when the data extension's control file declares no prerequisite.

Clients choose dependency versions and handling, including any restrictions on `CASCADE`. Verification records identify the exact dependency versions and builds tested; they are evidence of that concrete combination, not selection rules or claims about other versions. PostgreSQL server-version compatibility remains governed by section 2.

Read installable SQL versions from installation scripts and supported update paths. An update script alone does not establish that its starting version can be installed with the packaged library. Preserve separate identities when different source projects provide the same SQL name/version.

## 4. Platforms and capabilities

`platform_selection: all` selects every platform entry. Empty `os_release_ranges`, null ABI values and `research_required` represent unresolved scope. Candidate fields identify options under evaluation; `review_required` identifies an unresolved product decision. Neither establishes support. Linux's libc choice remains open.

Resolved OS entries name family, edition/distribution, feature release, original release date, minimum patch constraints and exclusions. Record the assessment date and any narrowing reason. Apply the four-year policy to the named OS release, such as a Windows feature release, rather than the product family's first release or a patch date.

`required_when_upstream_supports` lists required capabilities. `excluded_capabilities` lists features excluded by policy. `undecided_capabilities` lists features needing technical classification or a policy exception. `inclusion_policy` links the functional rule used to derive these outcomes. `profiles` maps each capability identifier to its section in [capabilities.md](capabilities.md), which explains the decision, affected functionality, dependencies, delivery and verification. These paths resolve relative to `spec/`. Required, excluded and undecided lists must be disjoint and every listed capability must have a profile. Recommendations in profiles do not change inclusion policy.

Expand compression into release-specific operations such as TOAST, WAL and dump/restore; an algorithm name alone does not define applicability. Generated artifact records carry assessed version/platform ranges and test evidence. Unmeasured size considerations do not block coverage or require new experiments.

## 5. Notes and validation

Any object may contain a `notes` array of plain-text strings, scoped to that object and written for human readers. Machine-actionable constraints also need structured fields. Profile/evidence paths resolve relative to `spec/`.

Reject unknown fields and enum values to catch misspelled policy. The formal schema must define object-specific required fields and the optional range/scoping fields described above. Pending research and review decisions block a claim of complete coverage.

## 6. Release discovery records

Retain the snapshot date, inventory revision/hash and checked upstream sources. For each release, record:

- Source project/version, original tag, stable status, publication date and evidence URL.
- Source download URL/checksum and applied patches with checksums.
- Provided SQL extensions, installable versions, dependencies and required settings.
- Expected PostgreSQL ranges, supporting evidence, exceptions and open questions.

This captures the exact upstream inputs used to expand the inventory without turning it into a manually maintained release ledger.

## 7. Artifact records and download catalogue

An artifact is a downloadable archive: PostgreSQL, a SQL extension or a shared runtime. Its record contains the facts below. Generated field names remain a design choice; these meanings are required.

| Group | Required facts |
| --- | --- |
| Identity | Build ID, artifact kind, source project/version/checksum, recipe revision |
| Provided SQL | SQL names and exact installable versions; labelled upstream control default; tested update paths |
| Build target | Exact PostgreSQL headers/version, target OS/architecture/ABI, toolchain/SDK and options |
| Runtime compatibility | Verified PostgreSQL releases, OS ranges, CPU requirements and evidence references |
| Dependencies | Upstream-declared SQL dependency names; native/shared-runtime package dependencies, installation layout and file ownership |
| Activation | Preload libraries, restart needs, configuration, environment values and resource paths |
| Capabilities | Status, applicable ranges, dependency versions, tests and structured exclusions with affected operations |
| Resources | Included paths, provenance/version/licence; excluded data, loading instructions and affected operations |
| Download | URL with checksum-bearing archive filename, format, SHA-256, manifest and relative layout |
| Obligations | Component licences, notices and source obligations |
| Diagnosis | Build/test timestamps, exact dependency versions/builds tested, verification records/logs, limitations, notes and replacement-build identity |

`distribution.archive_filename_contains_full_checksum` requires the complete lowercase hexadecimal SHA-256 in each archive basename, for example `postgresql-18.0-linux-x86_64-<sha256>.tar.gz`. The name, catalogue checksum and bytes must agree. Changed bytes get a new filename and URL; the current catalogue selects the corrected build.

Activation is declarative: prefix-relative paths, environment templates, PostgreSQL settings and SQL dependencies. Clients must not need to execute embedded shell code to discover requirements.

Keep `built_against` exact and `verified_for` separate. An archive built against 17.7 might pass on 17.7–17.11; if 17.9 fails, split the range or list passing releases explicitly. Ranges expand against a dated discovery snapshot, so later minors cannot inherit a pass. Multiple installable SQL versions require tests with the packaged library for each. Alternate compiled providers may require isolated installations.

A request identifies PostgreSQL release, platform, SQL extension and client-selected source/SQL versions, including prerequisites. Source-project identity resolves ambiguity. Exact dependency build IDs in test evidence identify the tested combination; they do not pin or recommend the client's SQL-extension dependency versions. Native/shared-runtime package identities still define the files required to run the selected binaries.

## 8. Coverage and completion

Expand one target per core release/platform and per applicable extension source/SQL version, PostgreSQL release and platform. Attach required OS and capability tests. Count required dependencies within those targets; do not enumerate unrelated extension subsets.

Each target has a state: `research_required`, `pending`, `build_failed`, `verification_failed`, `verified_unpublished` or `available`, with reasons and evidence. Proven upstream incompatibility is a visible `not_applicable` record excluded from the denominator. Build failure alone cannot justify it.

Report core and extension progress separately as available targets divided by resolved applicable targets, alongside unresolved counts and snapshot dates. Percentages are provisional while scope research remains. Completion requires resolved scope, all applicable targets available, required tests passed and current public-download checks. Failed discovery or a zero denominator cannot produce 100%.

## 9. Future presentation

The JSON is intended to support a future website, so keep facts structured and notes readable without build-system knowledge. Defining or implementing an HTML renderer is outside this specification.
