# PostGIS macOS arm64 archive trial

Created 2026-10-21 to test whether conda-forge spatial dependencies, source-built GDAL and SFCGAL, and unmodified PostGIS 3.6.4 can produce a relocatable four-name extension archive against the selected PostgreSQL 18.6 macOS arm64 core.

The manually dispatched `postgis-pilot.yml` workflow uses a standard `macos-15` arm64 runner and a conda-forge environment for GEOS, PROJ, CGAL and related build dependencies. `build-four-extensions-sfcgal.sh` builds GDAL and SFCGAL from pinned upstream sources, builds PostGIS, exercises all four SQL extensions, and assembles the runtime dylib closure and data files. `assemble-diagnostic-archive.py` writes the central licence pointer and binds the archive to the selected core. A separate runner checks the final archive's checksum, macOS deployment target, load paths, relocation and SQL behaviour.

The first archive run [39602429364](../../support/evidence/postgis-conda-archive-39602429364/README.md) built the four SQL extensions and recorded its dependency owners, then stopped on an obsolete licence-inventory lookup. The revised archive and verifier are under test. The diagnostic route does not yet establish selected publication coverage for other PostgreSQL versions or macOS Intel.

Move the working recipe and verifier into `scripts/postgis/` when selected archive checks pass. Remove this experiment and its manual workflow jobs after that migration, or record the failure and remove them if the approach cannot meet the requirements without changing upstream source. Review it by 2027-01-21 if it remains open.
