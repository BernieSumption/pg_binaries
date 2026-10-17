# Human review queue

## Scope of the upstream-only source rule for packaged dependencies

The [functional specification](specs/functional.md#never-patch-or-modify-extensions-or-dependencies) requires straightforward upstream builds without modifying dependencies. The macOS 11 dependency-floor probe built suitable Mach-O targets with vcpkg, but its port recipes applied source patches to libxml2, LZ4 and OpenSSL. The Windows pilot also obtains PostgreSQL dependencies through vcpkg. Linux archives copy runtime libraries from Ubuntu packages; the retained source identities include Ubuntu packaging source, but we have not audited each package's applied patch series. Existing Linux packaging also changes ELF RPATHs after compilation, and macOS packaging rewrites Mach-O load paths for relocation.

Decision needed: Does the prohibition include source patches applied by a standard package manager or distribution before we receive its packages, and does it include post-build changes to binary load paths needed for relocation? Pending an answer, treat patched-source dependencies as ineligible for release evidence. Continue independent implementation and tests; do not claim the current platform archives meet the upstream-only rule.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.
