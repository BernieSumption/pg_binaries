# timescaledb

Deferred while the initial portfolio is developed; the
[shared selection requirements](../README.md) apply.

## Schema use and version transitions

TimescaleDB adds hypertables, time-bucketing and continuous aggregates whose
creation and inspection matter to migration clients. See the
[upstream overview](https://github.com/timescale/timescaledb/blob/main/README.md).
Eligible release/PostgreSQL combinations still need research.

The [distributed hypertables API](https://github.com/timescale/docs/blob/latest/api/distributed-hypertables/index.md)
was sunsetted in 2.14.x. This pre-cutoff example explains why a recent version
may reject older schema operations; those historical releases remain outside
the target selection.

## Questions before selection

- Which features are needed for representative migrations, and what terms permit
  free public redistribution? The [licensing metadata](https://github.com/timescale/timescaledb/blob/main/LICENSE)
  separates Apache-licensed code from Timescale-licensed `tsl` code and libraries.
  Any feature omission needs explicit review.
- Which loader, preload settings and background workers does each release require?
- Which non-OS libraries, resources and companion modules must ship, with what
  version constraints and download sizes?
- Can relocated installations create and inspect hypertables and continuous
  aggregates on every target platform?
