# postgis_topology

`postgis_topology` supplies topology types, schemas and functions. It follows
[PostGIS source versions, licence and expected PostgreSQL ranges](postgis.md),
including the 3.6.1–3.6.4 candidates.

## Dependencies and resources

The [3.6.4 control file](https://github.com/postgis/postgis/blob/3.6.4/extensions/postgis_topology/postgis_topology.control.in)
requires `postgis` and fixes the SQL schema to `topology`. Its `relocatable = false`
means the extension's SQL objects cannot move to another schema; the extracted
binary directory must still support filesystem relocation. No preload is expected.
Shared native references must resolve through declared package dependencies.

Include topology's default catalogue objects. Application road networks, Census
imports and user topology content are excluded.

## Schema transitions

PostGIS 3.5 changes `TopoGeometry` inequality behaviour; 3.6 introduces bigint
topology identifiers and replacement signatures. The 3.6.1 notes also prescribe
`FixCorruptTopoGeometryColumn` for affected existing columns after upgrades.
Use the [release notes](https://github.com/postgis/postgis/blob/3.6.4/NEWS)
to select fixtures for exact versions and any advertised update paths.

## Evidence and remaining tests

The Linux pilot created the extension and a topology after relocation. See
[pilot evidence and common gaps](../README.md#pilot-evidence).

Add a topology-backed table and index, representative edits, and fixtures for
the identifier/signature transitions above.
