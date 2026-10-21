# Selected macOS PostGIS arm64 trial

[Run 39644346558](https://github.com/BernieSumption/pg_binaries/actions/runs/39644346558) built PostGIS 3.6.4 for PostgreSQL 18.6 on macOS arm64. A separate fresh runner passed relocation, Mach-O static analysis, and SQL probes for all four PostGIS extension names. The retained files under `arm64/18.6` bind those results to the tested archive digests.

The [build's runtime owner report](arm64/18.6/conda-package-owners.json) identifies 39 bundled libraries with no unresolved owner, plus their runtime data and source-built GDAL and SFCGAL. Its 24 conda package owners and two source-built projects are represented in the central [`LICENSES.md`](../../../LICENSES.md).

This run predates registration of the macOS PostGIS publication profile and later recipe changes. It is historical technical evidence, not a current-profile publication verification record. A new selected run is required for current-profile coverage.
