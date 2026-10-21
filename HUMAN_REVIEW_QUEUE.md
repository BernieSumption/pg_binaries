# Human review queue

## Public-domain runtime dependencies

The macOS PostGIS diagnostic archive's runtime closure includes SQLite through its conda-forge package. [SQLite declares its deliverable code and documentation to be in the public domain](https://www.sqlite.org/copyright.html), and the package metadata describes its terms as `blessing`. This permits redistribution, but it is not an OSI-approved licence. The [functional specification](specs/functional.md#maintain-a-list-of-all-licenses-and-link-to-it-in-downloads) requires a human-reviewed acceptable alternative for any dependency without an OSI-approved licence.

Decision needed: May projects whose authors explicitly dedicate their shipped code to the public domain be accepted as a general alternative? If approved, record that decision in `policies/licenses.md` and retain SQLite's declaration and source link in `LICENSES.md`. If not, the macOS PostGIS runtime closure needs a suitable replacement before publication. Other build and verification work can continue.

## IJG JPEG library licence

Selected PostGIS builds include libjpeg-turbo, whose shipped JPEG implementation includes code under the [Independent JPEG Group licence](https://github.com/libjpeg-turbo/libjpeg-turbo/blob/main/README.ijg). `LICENSES.md` records that declaration. The IJG licence is absent from the [OSI-approved licence list](https://opensource.org/licenses), and `policies/licenses.md` has no human-reviewed alternative for it. This is a licence-classification question, not a finding that the terms prohibit redistribution.

Decision needed: Is the IJG licence acceptable for the JPEG code in our downloads? If approved, record the human-reviewed alternative in `policies/licenses.md`. If not, selected archives that include this code need a suitable replacement before publication. Build and verification work can continue.

## Custom permissive licences in the Linux PostGIS closure

The selected Linux PostGIS archive includes bzip2, e2fsprogs `com_err` and Qhull. The [bzip2 licence](https://gitlab.com/bzip2/bzip2/-/blob/bzip2-1.0.8/LICENSE) permits source and binary redistribution with notice, origin and endorsement conditions. [The `com_err` source declaration](https://github.com/tytso/e2fsprogs/blob/master/lib/et/et_name.c) permits use, copying, modification and distribution, with a condition against using MIT or MIT SIPB names in advertising without permission. [Qhull's declaration](https://github.com/qhull/qhull/blob/master/COPYING.txt) permits copying, modification and redistribution with notice conditions. These are custom licences absent from the [OSI-approved list](https://opensource.org/licenses), so the [functional specification](specs/functional.md#maintain-a-list-of-all-licenses-and-link-to-it-in-downloads) requires a human-reviewed alternative. This is a licence-classification question, not a finding that redistribution is prohibited.

Decision needed: Are these three declared licences acceptable for our downloads? A general policy accepting custom permissive licences that clearly allow free source and binary redistribution, subject to ordinary notice and non-endorsement conditions, would also settle similar future cases. If approved, record the decision in `policies/licenses.md`. Build and verification work can continue.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.
