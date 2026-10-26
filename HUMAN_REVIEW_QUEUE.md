# Human review queue

## Inventory of PostgreSQL built-in extensions by platform

The checked PostgreSQL 15.19, 16.15, 17.11 and 18.6 archives contain `uuid-ossp` on Linux and macOS but omit it on Windows, as [the PostgreSQL extension policy](policies/extensions.md#built-in-extensions) permits. The functional specification's `inventory.json` example places `included_extensions` once per PostgreSQL version. That field cannot accurately describe both sets, and `candidate_inventory.py` rejects the staged first-release candidate when the five platform archives disagree.

Proposed specification change: place `included_extensions` in each PostgreSQL `downloads[platform]` entry, alongside that archive's URL and checksum. Derive the list from the exact archive as before. This gives clients the answer for the platform they download and avoids a second field for platform exceptions. After the specification changes, update the candidate generator, coverage and preflight checks, and their tests. Other builds and archive staging can proceed meanwhile.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.

4. Coherent release installation test. Discuss and specify a release test that assembles a maximal installation from the selected PostgreSQL archive and every compatible extension archive for each supported platform and PostgreSQL version, choosing one version per extension project. Before calling a release coherent, start one PostgreSQL instance from that installation and confirm that every included extension passes its verifier script against the same instance. Also load the extensions in one backend session where possible, so separate sessions do not hide conflicts between bundled versions of a shared library. Define how the test handles extension prerequisites, configuration requirements, shared-library dependencies and multiple selected versions before implementing it.
