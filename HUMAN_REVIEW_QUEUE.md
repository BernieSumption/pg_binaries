# Human review queue

## libcom_err licence in the Linux PostGIS closure

The selected Linux PostGIS archive copies `libcom_err.so.2` from e2fsprogs. The [e2fsprogs notice](https://github.com/tytso/e2fsprogs/blob/master/NOTICE) gives the `lib/et` library MIT-style terms as an explicit exception to its GPLv2 terms for the filesystem utilities. The [library source terms](https://github.com/tytso/e2fsprogs/blob/master/lib/et/et_name.c) permit use, copying, modification and distribution, with a condition against using MIT or MIT SIPB names in advertising without permission. This is a known permissive licence, but it differs from the standard OSI-approved MIT licence. The [functional specification](specs/functional.md#maintain-a-list-of-all-licenses-and-link-to-it-in-downloads) therefore requires a human-reviewed alternative.

Decision needed: May we accept the declared MIT-style terms for the copied `libcom_err` library? The bzip2 and Qhull licences have been reviewed and approved in `policies/licenses.md`. Build and verification work can continue.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.
