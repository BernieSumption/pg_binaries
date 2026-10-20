# Human review queue

## Backlog ideas

From Bernie: Adding this here so that we don't forget it. Don't start work on this yet. I'd like to discuss the viability of these and specify them properly before we go ahead. If indeed we decide to go ahead at all.

1. Size review. Look for ways to reduce binary size before building out the backlog of many versions. Potential options include compiler flags like -Os, reviewing the enabled build options for any that provide does proportionately small value in return for their increase in binary size, different compression algorithms and so forth. As a first step in this, some analysis about of the built archive to get a picture of what the greatest contributors are to size might be helpful.

2. Adversarial correctness review. Have an Astra agent review the implementation and tests to identify both specific and systematic potential issues.

3. Manual post-release bug hunting. Discuss and specify an occasional, manually initiated process that downloads and exercises released assets in environments outside routine GitHub-runner coverage. Examples include different operating systems and distributions (including older Ubuntu, outside the routine Alpine verification environment), older OS versions and Linux kernels, different distros, Windows without the Visual C++ redistributable installed, and macOS without development tools. These investigations seek production bugs and inform fixes and useful regression tests; they are not an automatic CI job or a prerequisite for each release. Decide the process before implementing it.

4. PostGIS macOS redistribution evidence. The PostGIS 3.6.4 / PostgreSQL 18.6 arm64 feasibility run builds unmodified upstream source, but a relocatable archive would bundle 15 Homebrew formulae, source-built GDAL 3.13.3 and PROJ/GDAL data. Existing macOS licence collection only handles PostgreSQL and pgvector source manifests; it cannot establish the exact source, licence text, notice and source-delivery obligations for this closure. Decide whether to fund a bounded, target-specific redistribution inventory and verifier before extending the macOS PostGIS route. Until resolved, the successful build remains feasibility evidence and no archive is advertised.
