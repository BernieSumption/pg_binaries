# Build tests

Reject incorrect packages before [artifact verification](artifact-verification.md). These
checks support FUNC004, FUNC007–FUNC010 and FUNC012 and establish the identities used by
FUNC001–FUNC003 and FUNC008. Follow the shared [execution and record details](test-execution-and-evidence.md).

## Sources and options

Verify downloaded source hashes before extraction. Match each release against
the dated discovery entry; unresolved publication dates remain research work.
Read SQL version strings from the shipped scripts rather than assuming they
match source tags.

Record the exact PostgreSQL headers/version used to compile an extension,
separately from its intended runtime range. SQL/data packages must record their
generation inputs too. Choosing an older build baseline does not establish
compatibility with later minors.

Capture effective compiler/linker flags and configure/Meson/CMake/Make options.
Inspect generated commands for `-march=native` and equivalent host tuning. Fail
builds that exceed their declared CPU baseline; success on the builder's CPU
cannot resolve this failure.

For each required or included capability, identify its build option, dependency
and runtime test for the exact PostgreSQL major. Audit other optional features,
procedural languages and contrib modules as `included`, `excluded` or
`research_required`. Unknowns block complete coverage; exclusions affecting schema acceptance
must follow the inclusion policy or an agreed exception. Test required XML and TLS support.
Keep dependency versions explicit where they affect SQL functionality.

Inspect linked and dynamically loaded dependencies. Classify each as a core OS
component, bundled runtime or static input. Follow transitive dependencies and
resource lookups, including ICU, PROJ/GDAL and Windows CRT files. Reject undeclared
dependencies and builder/package-manager paths. Clean runtime tests later check
whether this audit found everything.

## Package contents

Generate a staged-file manifest and compare it with the final archive: format,
checksum, permissions, relative paths and file ownership. Verify that the full
SHA-256 in the archive filename matches both the catalogue and final bytes. Reject traversal paths and links that escape the destination.

Check required PostgreSQL executables and support files. Enumerate SQL extensions,
directly installable versions and update paths separately: an update script does
not establish that its starting version can be installed directly. Label control
file defaults as upstream facts without creating catalogue selection defaults.

Map each module's control, SQL, native and resource files to its package or a
declared shared runtime. Compare dependencies against the exact source. Each
shared file must have one owner; conflicting bytes at one path fail acceptance.
An upstream combined installation tree still needs independently usable output
packages.

Map redistributed components to exact versions, licence texts, notices and
source obligations. Verify required texts are inside the archives and mappings
refer to shipped files. Unresolved obligations block advertisement.

List retained defaults and excluded datasets with their source, loading method
and affected operations. Removing a small upstream default requires a reason,
measured saving and behaviour tests. When evaluating packaging choices, measure
compressed/extracted overhead of runtimes such as Windows CRT and geospatial
libraries. These internal comparisons do not require published size metadata.

## Smoke test from final archives

Extract final archives into a fresh prefix in the disposable build environment
and run as an ordinary user:

1. Initialize UTF-8 with `initdb`, start with `pg_ctl`, connect with packaged
   `psql`, and verify the server version.
2. Run a small table/function/constraint fixture and check that `pg_dump` and
   `pg_restore` start with matching versions.
3. For each extension, install its fixture-selected prerequisites and required
   native/runtime packages into a matching core installation. Record exact dependency
   versions. Create the explicit SQL version, check `pg_extension` and run
   one [representative operation](artifact-verification.md#extension-observations).
4. Probe ICU and included XML/TLS capabilities, then stop cleanly.

Retain failures and candidate checksums. A smoke-test pass permits independent
verification; build-environment libraries and resources can conceal omissions.

## Completion

Implement these checks under [TEST01–TEST08](../../testing-policy.md), connect them to the pipeline and retain verification records. See the [requirement map](../../testing-notes.md#requirement-map) for the guarantees they establish.
