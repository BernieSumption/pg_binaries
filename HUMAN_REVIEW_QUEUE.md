# Human review queue

## Pending decision

### PostGIS macOS redistribution work

The PostGIS 3.6.4 / PostgreSQL 18.6 arm64 [feasibility run](support/evidence/postgis-macos-feasibility-39474535469/README.md) builds unmodified upstream source and creates all four selected SQL extensions. A relocatable archive would include source-built GDAL 3.13.3, PROJ/GDAL data and libraries from 15 Homebrew formulae. The checked PostgreSQL core already inventories libxml2 and zstd, leaving up to 13 additional formulae to review; shared library bytes and versions still need comparison. The current macOS licence collector cannot describe a bundle that mixes source-built GDAL with Homebrew libraries. Meeting the [redistribution policy](policies/releases.md#redistribution-review-before-publication) requires exact component, notice and source-obligation evidence before advertising the archive.

Should we invest in a bounded PostGIS-specific macOS packaging and redistribution review for this closure? If so, first prove one relocatable arm64 archive against PostgreSQL 18.6, then reuse the route for the remaining macOS targets. Until this decision, keep the successful run as feasibility evidence and continue work on other targets.

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.
