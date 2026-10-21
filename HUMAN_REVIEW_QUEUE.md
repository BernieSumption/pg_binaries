# Human review queue

## Public-domain runtime dependencies

The macOS PostGIS diagnostic archive's runtime closure includes SQLite through its conda-forge package. [SQLite declares its deliverable code and documentation to be in the public domain](https://www.sqlite.org/copyright.html), and the package metadata describes its terms as `blessing`. This permits redistribution, but it is not an OSI-approved licence. The [functional specification](specs/functional.md#maintain-a-list-of-all-licenses-and-link-to-it-in-downloads) requires a human-reviewed acceptable alternative for any dependency without an OSI-approved licence.

Decision needed: May projects whose authors explicitly dedicate their shipped code to the public domain be accepted as a general alternative? If approved, record that decision in `policies/licenses.md` and retain SQLite's declaration and source link in `LICENSES.md`. If not, the macOS PostGIS runtime closure needs a suitable replacement before publication. Other build and verification work can continue.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.
