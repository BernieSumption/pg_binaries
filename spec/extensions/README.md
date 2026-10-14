# Extension profiles

Research snapshot: 14 October 2026. Profiles explain version compatibility,
dependencies and data requirements that need more context than inventory notes.

- `supported/` contains intended offerings in [inventory.json](../inventory.json).
  Availability is established separately by verification and publication.
- `unsupported/` contains deferred, excluded or blocked candidates, with a reason
  in each profile. All five current candidates are deferred while the initial
  portfolio is developed; none has an advertised release, build baseline or download.

## Intended offerings

| SQL name | Purpose |
| --- | --- |
| [vector](supported/vector.md) | Vector types and indexes from pgvector |
| [postgis](supported/postgis.md) | Core spatial types and functions |
| [postgis_raster](supported/postgis_raster.md) | Raster types and functions |
| [postgis_topology](supported/postgis_topology.md) | Topology schemas and operations |
| [postgis_sfcgal](supported/postgis_sfcgal.md) | SFCGAL spatial operations |
| [address_standardizer](supported/address_standardizer.md) | Address parser and standardization functions |
| [address_standardizer_data_us](supported/address_standardizer_data_us.md) | Upstream US rules and lookup tables |
| [postgis_tiger_geocoder](supported/postgis_tiger_geocoder.md) | TIGER schema, normalization and geocoding functions |

Each SQL extension is independently downloadable, with declared dependencies.
Shared native files have one declared package owner to prevent conflicting
copies. Source project, SQL extension version and binary build identity are
recorded separately; a source repository may supply several SQL extensions.

## Shared version and packaging rules

The inventory selects stable releases published from **25 September 2025**,
including qualifying patches to older branches, for compatible PostgreSQL
15 and later releases on all three target platforms. Deferred candidates follow this
policy if selected. The profiles record research; the inventory owns maintained
range rules and generated verification records establish actual compatibility.

The provisional build baseline is the oldest eligible compatible minor in each
PostgreSQL major: currently 15.15, 16.11, 17.7 and 18.0. A release may require a
newer baseline. Native modules are built separately per major; SQL-only packages
also record the tooling used to generate their files. Using an early baseline
reduces accidental reliance on later symbols. Reusing an archive requires tests
on every advertised runtime minor, with its required dependencies.

Downloads include control, installation/update SQL, native modules, licences
and required runtime resources. Retain small upstream defaults. Exclude large
external datasets used only for application queries, maintenance, administration
or table population. Profiles identify affected operations and data provenance;
removing a default file requires a reason, size measurement and behaviour tests.

## Pilot evidence

The [evidence summary](../evidence.md) links the verification runs. The pilot tested vector 0.8.7 with PostgreSQL 18.6 on all three platforms,
and PostGIS 3.6.4's seven modules together on PostgreSQL 18.6 / Ubuntu 24.04 x86-64.
Profiles below describe the operations tested and their limits.

The combined PostGIS archive measured about 85 MB compressed and 253 MB staged.
Per-module and shared-dependency sizes remain unmeasured. Independent module
downloads, broader PostgreSQL/OS ranges and macOS/Windows PostGIS remain
unverified. These gaps require package isolation, size and compatibility tests
in addition to the extension-specific tests below.

## Profile contents and maintenance

Use this order:

1. SQL name, purpose, source and licence identity; reason for selection or deferral.
2. Release sources, expected PostgreSQL ranges and departures from shared build
   rules. Distinguish source versions, SQL versions and verified combinations.
3. Dependency names from upstream control files, libraries and activation settings.
   Describe optional usage in prose without adding inferred SQL dependency edges
   or dependency-version recommendations. Identify resources and data-loading workflows.
4. Significant schema or API transitions, with examples that explain why a
   migration might require an exact version.
5. Verification evidence, limits, extension-specific tests and unresolved choices.

Record exact SQL dependency versions in test evidence. Do not research compatibility
ranges between extensions or treat a tested combination as a client selection rule.

Follow the [writing guide](../style.md). Cite tagged source or release-specific
manuals where possible; identify moving documentation. Keep exact results in
verification records rather than maintaining a second release ledger. Update
structured constraints when a research finding changes machine decisions.

Deferred candidates are [Citus](unsupported/citus.md),
[TimescaleDB](unsupported/timescaledb.md), [pgRouting](unsupported/pgrouting.md),
[H3](unsupported/h3.md) and [pg_partman](unsupported/pg_partman.md). Selection
requires release-specific compatibility research, a dependency/licence inventory,
package sizes and clean-host DDL/query tests on the target platforms.
