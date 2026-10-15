# D07 — Resource inclusion

**F09 — resource policy applied to packaging.** Retain install-time seed data, standardizer rules and required coordinate definitions. PROJ's [resource-search rules](https://proj.org/en/stable/resource_files.html) require testing lookups after relocation.

Bulk TIGER Census records populate application tables through generated import scripts; the [TIGER profile](../../../extensions/items/planned/postgis_tiger_geocoder.md) describes that workflow. Exclude that corpus while keeping small default lookup/configuration data. Document any DDL that invokes operations needing external data. The [resource research](../../../extensions/extensions-notes.md) identifies PROJ grids as a separate question: some transformations need them during DDL execution.

## Completion

Implement the resource policy in manifests and packaging, and pass offline relocation and DDL tests. Resolve the PROJ-grid proposal before claiming its affected operations.
