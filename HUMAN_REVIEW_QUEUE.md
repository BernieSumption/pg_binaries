# Human review queue

## Address Standardizer 3.7.0 on Windows

The selected [standalone 3.7.0 source](https://github.com/postgis/address_standardizer/tree/v3.7.0) documents a PGXS build and tests PostgreSQL 14–19 on Linux, but has no Windows build instructions or CI target. Our [native Windows probe](https://github.com/BernieSumption/pg_binaries/actions/runs/39062327837) built unmodified PCRE2 and compiled eight of 13 Address Standardizer C files with `clang-cl` against the PostgreSQL 18.6 pilot. It then failed because `pagc_tools.c` calls POSIX `getcwd`, which is undeclared under that Windows toolchain. MSVC also rejected GNU-style macro syntax and an exported-function declaration earlier in the source. A source edit or build-time API substitution could work around these errors, but the functional specification prohibits porting upstream packages.

Decision needed: Should we treat Windows as unsupported by this upstream release and remove both SQL names from the intended Windows support matrix, or is there an upstream-supported, unmodified-source Windows build method we should try? If Windows support is required despite the source issues, that would need an explicit specification change. Until resolved, retain the declared Windows targets as unverified and continue Linux/macOS work.

## Scope of the upstream-only source rule for packaged dependencies

The [functional specification](specs/functional.md#never-patch-or-modify-extensions-or-dependencies) requires straightforward upstream builds without modifying dependencies. The macOS 11 dependency-floor probe built suitable Mach-O targets with vcpkg, but its port recipes applied source patches to libxml2, LZ4 and OpenSSL. The Windows pilot also obtains PostgreSQL dependencies through vcpkg. Linux archives copy runtime libraries from Ubuntu packages. [Exact-source review](support/evidence/linux-redistribution-audit-2026-10-17.md) now confirms that the selected Ubuntu packaging applies source changes to ICU, liblzma, libxml2 and libxslt; this is an actual release eligibility question, not only a possible patch in an unaudited package. Existing Linux packaging also changes ELF RPATHs after compilation, and macOS packaging rewrites Mach-O load paths for relocation.

Decision needed: Does the prohibition include source patches applied by a standard package manager or distribution before we receive its packages, and does it include post-build changes to binary load paths needed for relocation? Pending an answer, treat patched-source dependencies as ineligible for release evidence. Continue independent implementation and tests; do not claim the current platform archives meet the upstream-only rule.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.
