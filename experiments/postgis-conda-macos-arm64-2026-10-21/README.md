# PostGIS conda-forge macOS arm64 dependency trial

Created 2026-10-21.

## Question

Do conda-forge GEOS, PROJ and GDAL packages and their resolved runtime dependencies have macOS deployment targets compatible with macOS 11, and can their dylib dependencies be identified for a later relocation assessment?

## Inputs

- A standard GitHub-hosted `macos-15` arm64 runner.
- Current conda-forge packages for `geos`, `proj` and `gdal`, resolved together with their transitive dependencies by micromamba.
- The manually dispatched `postgis-conda-macos-arm64-feasibility.yml` workflow. SFCGAL is excluded because conda-forge does not currently publish it for macOS arm64.

The workflow records the explicit package URLs, package metadata, each loadable Mach-O file's deployment target and absolute `LC_RPATH` entries, and non-system absolute dylib dependencies. The temporary conda environment is kept outside the uploaded reports. It does not build PostGIS, alter package binaries, or produce a release archive.

## Completion and cleanup

The question is answered when a successful run records the resolved packages and all runtime dylibs can be inspected. A package with a deployment target newer than 11.0, an unresolved absolute dependency, or missing deployment metadata is a finding to carry into a later experiment. Preserve the workflow and short-retention artifact only while this question is active; remove this experiment after the dependency source is selected or if the package stack cannot meet macOS 11 without upstream changes. Recheck by 2027-01-21 if it remains open.
