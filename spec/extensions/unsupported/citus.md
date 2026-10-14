# citus

Deferred while the initial portfolio is developed; the
[shared selection requirements](../README.md) apply.

## Schema use and version transitions

Citus adds distributed/reference tables, distribution metadata and columnar
storage. Its SQL functions and access methods can appear in migrations. The
[upstream overview](https://github.com/citusdata/citus/blob/main/README.md)
describes a single-node starting configuration worth testing for local schema
inspection.

The [changelog](https://github.com/citusdata/citus/blob/main/CHANGELOG.md)
records that 14.0 dropped PostgreSQL 15, added 18 and tightened colocation rules
for keys with different collations. The
[upgrade guide](https://docs.citusdata.com/en/latest/admin_guide/upgrading_citus.html)
warns of API breaks and coordinated binary, restart and SQL-extension updates.
Release-specific research must establish eligible PostgreSQL combinations.

## Questions before selection

- What minimal configuration accepts representative migration SQL and exposes
  distribution metadata? Upstream requires `shared_preload_libraries = 'citus'`
  before `CREATE EXTENSION`.
- Which releases supply `citus_columnar` separately, with what dependencies?
  A selected companion needs its own download.
- Which non-OS libraries and runtime resources need bundling, and what terms
  permit their redistribution?
- Can single-node DDL and catalogue inspection work on every target platform?
