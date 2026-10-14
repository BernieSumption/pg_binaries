# pg_partman

Deferred while the initial portfolio is developed; the
[shared selection requirements](../README.md) apply.

## Schema use and version transitions

pg_partman manages time- and number-based partition sets. Its routines and
configuration tables can appear in migrations. The
[upstream README](https://github.com/pgpartman/pg_partman) describes a PL/pgSQL
installation and optional native maintenance worker, currently requiring
PostgreSQL 14+. Historical releases need separate compatibility research.

The pre-cutoff [5.0.1 transition](https://github.com/pgpartman/pg_partman/blob/development/doc/pg_partman_5.0.1_upgrade.md)
removed trigger-based partitioning in favour of PostgreSQL declarative
partitioning. This illustrates a schema compatibility break without adding
those older releases to the target.

## Questions before selection

- Include `pg_partman_bgw`? It requires `shared_preload_libraries` and supplies
  maintenance automation. Any proposed omission needs explicit review.
- Which support scripts belong in the package, and when is the optional
  `pg_jobmon` integration needed?
- Which native dependencies, runtime resources and notices accompany the exact
  release's [licence](https://github.com/pgpartman/pg_partman/blob/development/LICENSE.txt)?
- Can partition creation, configuration inspection and maintenance pass after
  relocation on all targets, with the worker included where offered?
