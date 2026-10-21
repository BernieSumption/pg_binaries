# PostGIS macOS arm64 build feasibility

Created 2026-10-20.

## Question

Can unmodified PostGIS 3.6.4 compile against the selected PostgreSQL 18.6 macOS arm64 core on a standard GitHub-hosted macOS runner with all four declared SQL extensions enabled: `postgis`, `postgis_raster`, `postgis_sfcgal` and `postgis_topology`?

## Inputs

- The checked PostgreSQL 18.6 macOS arm64 core archive and its resolver-generated target configuration.
- The upstream PostGIS 3.6.4 source archive from OSGeo, checked against SHA-256 `ed8dc6679f1e06f7b113592b04cde2a7e00f1b1e681294c8ca2204058990cec6`.
- Standard `macos-15` arm64 GitHub-hosted runner and Homebrew packages for GEOS, PROJ, GDAL, SFCGAL, JSON-C, libxml2, protobuf-c, PCRE2 and pkgconf.

The registered `postgis-pilot.yml` manual workflow exposes this experiment through an opt-in input. The trial compiles and installs into its temporary selected core, then checks that each declared SQL name has control and versioned SQL files. It does not produce a final extension archive or release evidence.

## Completion and cleanup

The question is answered when the unmodified upstream source compiles against the selected core and all four SQL extension file sets are installed. If the first run fails, retain the logs and correct only concrete recipe errors before retrying. Stop if upstream requires source changes or an unreasonable dependency workaround.

After a passing build, document the exact runner dependencies and configure options, then assess the work required for a final archive: runtime dylib closure and relocation, data files, central `LICENSES.md` entries and archive pointer, archive packaging, fresh-runner Mach-O inspection, SQL DDL and behaviour probes, and archive-bound verification records. Remove this experiment after migration or if the build cannot meet the question without source changes. Recheck it by 2027-01-20 if it remains open.
