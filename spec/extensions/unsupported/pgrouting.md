# pgrouting

Deferred while the initial portfolio is developed; the
[shared selection requirements](../README.md) apply.

## Schema use and version transitions

pgRouting provides routing and graph-analysis functions whose signatures and
result columns can appear in migration-defined wrappers and views. The
[upstream README](https://github.com/pgRouting/pgrouting/blob/main/README.md)
requires PostGIS and uses Boost Graph Library. Its policy of supporting current
PostgreSQL versions needs checking against each eligible tagged release.

The [4.0.0 release notes](https://github.com/pgRouting/pgrouting/releases/tag/v4.0.0)
describe removal of `pgr_createTopology`, old `pgr_trsp` signatures and other
interfaces, plus result-column changes. Confirm the release date during intake;
this example explains schema compatibility concerns without asserting coverage.

## Questions before selection

- Which dependency names do the release's control files declare, and which exact
  versions were used in its verification fixture?
- Which Boost/C++ runtime libraries and resources must ship for relocation on
  Linux, Intel macOS and x86-64 Windows?
- What notices and redistribution obligations cover the upstream GPL-2.0-or-later,
  Boost and MIT-X portions and their dependencies?
- Can routing queries, dependent view creation and catalogue inspection pass
  using small test graphs? Application road networks are external datasets.
