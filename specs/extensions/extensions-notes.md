# Extensions notes

Research findings and open technical questions for the extension board. Item folders record the selected, proposed, rejected and deferred work.

## Selection criteria still needed

The initial inventory is selected, but a general rule for adding further extensions has not been agreed. Existing candidate items remain deferred. Gather facts about schema relevance, build requirements and portability before proposing additions; this note does not expand the portfolio.

## Intended offerings

| SQL name | Purpose |
| --- | --- |
| [vector](items/planned/vector.md) | Vector types and indexes from pgvector |
| [postgis](items/planned/postgis.md) | Core spatial types and functions |
| [postgis_raster](items/planned/postgis_raster.md) | Raster types and functions |
| [postgis_topology](items/planned/postgis_topology.md) | Topology schemas and operations |
| [postgis_sfcgal](items/planned/postgis_sfcgal.md) | SFCGAL spatial operations |
| [address_standardizer](items/planned/address_standardizer.md) | Address parser and standardization functions |
| [address_standardizer_data_us](items/planned/address_standardizer_data_us.md) | Upstream US rules and lookup tables |
| [postgis_tiger_geocoder](items/planned/postgis_tiger_geocoder.md) | TIGER schema, normalization and geocoding functions |

Each SQL extension is independently downloadable, with declared dependencies.
Shared native files have one declared package owner to prevent conflicting
copies. Source project, SQL extension version and binary build identity are
recorded separately; a source repository may supply several SQL extensions.

## Pilot evidence

The [evidence summary](../testing/testing-evidence.md) links the verification runs. The pilot tested vector 0.8.7 with PostgreSQL 18.6 on all three platforms,
and PostGIS 3.6.4's seven modules together on PostgreSQL 18.6 / Ubuntu 24.04 x86-64.
Extension items describe the operations tested and their limits.

The combined PostGIS archive measured about 85 MB compressed and 253 MB staged.
Per-module and shared-dependency sizes remain unmeasured. Independent module
downloads, broader PostgreSQL/OS ranges and macOS/Windows PostGIS remain
unverified. These gaps require package isolation, size and compatibility tests
in addition to the extension-specific tests in those items.

## Build baseline research

The provisional build baseline is the oldest eligible compatible minor in each
PostgreSQL major: currently 15.15, 16.11, 17.7 and 18.0. A release may require a
newer baseline. Native modules are built separately per major; SQL-only packages
also record the tooling used to generate their files. Using an early baseline
reduces accidental reliance on later symbols. Reusing an archive requires tests
on every advertised runtime minor, with its required dependencies.

## PostgreSQL extension files, versions and dependencies

### PostgreSQL behavior (official documentation)

An extension control file can declare prerequisite extension names with `requires`, for example `requires = 'foo, bar'`. PostgreSQL says those extensions **must be installed before** the dependent extension is installed. The field names extensions; it does not express a required version. ([Extension files](https://www.postgresql.org/docs/18/extend-extensions.html#EXTEND-EXTENSIONS-FILES))

`CREATE EXTENSION A;` does not implicitly install missing prerequisites. It fails if a required extension is not already installed. `CREATE EXTENSION A CASCADE;` installs missing prerequisites recursively. An already-installed prerequisite is reused. For dependencies installed by `CASCADE`, PostgreSQL always selects each dependency's own control-file `default_version`; the requested `VERSION` on A does not propagate. Without an explicit `VERSION`, A also uses its own control-file `default_version`. ([CREATE EXTENSION](https://www.postgresql.org/docs/18/sql-createextension.html))

Example: suppose `a.control` says `requires = 'b'`, and `b.control` says `requires = 'c'`:

```sql
CREATE EXTENSION a;          -- errors if b is not installed
CREATE EXTENSION a CASCADE;   -- installs missing c, then b, then a
-- Or, explicitly:
CREATE EXTENSION b;           -- itself requires c to be installed first
CREATE EXTENSION a;           -- succeeds because b is installed
```

Before `CREATE EXTENSION` can load an extension, PostgreSQL requires its supporting files to be installed on the server: a control file and versioned SQL script (and any other needed files). The command runs the SQL script; it does not fetch extension packages or files. ([CREATE EXTENSION](https://www.postgresql.org/docs/18/sql-createextension.html), [Extension files](https://www.postgresql.org/docs/18/extend-extensions.html#EXTEND-EXTENSIONS-FILES))

Control/SQL files are distinct from native runtime requirements. When an installation script defines a normal C function, PostgreSQL's C validator loads its library and checks the symbol, even with `check_function_bodies` disabled. Creation therefore tests loadability, but does not prove correct behavior or the native library's release identity. PostgreSQL does not compile missing libraries. ([C validator source](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/catalog/pg_proc.c), [C-language functions](https://www.postgresql.org/docs/18/xfunc-c.html))

### Files and version coexistence

Research checked on 14 October 2026 against PostgreSQL 15–18 documentation and source. No new binary tests were run.

The PostgreSQL installation contains executables, extension files and libraries. A cluster's data directory contains databases and their catalogues. Multiple clusters can use one installation and consequently share its extension files. Separate data directories alone do not isolate native extension releases.

Illustrative Linux layout; actual directories come from the installation's `pg_config --sharedir` and `--pkglibdir`:

```text
share/extension/
  a.control
  a--1.0.sql
  b.control                 # primary metadata, including default_version
  b--2.2.sql                # installation script
  b--2.2--2.3.sql           # update script
  b--2.3.control            # optional version-specific overrides
lib/
  a.so
  b.so
```

The extension author supplies the primary control file, directly or through build-time generation. PGXS installs it with the extension's scripts. PostgreSQL reads it; it does not derive a default from script filenames. Optional secondary controls can override `module_pathname` for individual SQL versions, but cannot set `default_version` or `directory`. An installable target can also be reached through an installation script followed by update scripts. ([PGXS](https://www.postgresql.org/docs/17/extend-pgxs.html), [secondary controls](https://www.postgresql.org/docs/16/extend-extensions.html#EXTEND-EXTENSIONS-FILES), [installation/update chains](https://www.postgresql.org/docs/17/extend-extensions.html#EXTEND-EXTENSIONS-UPDATES))

Different extension names have distinct primary control files and normally distinct module names. Independently downloaded packages can therefore share an installation, provided shared files and native dependencies are compatible. Downloads of different releases of the same extension can overwrite its primary control file, library and other common paths. PostgreSQL has no archive-overlay conflict resolver.

`pg_extension.extversion` records the SQL version in each database. C functions separately record a shared-library reference in `pg_proc.probin`. Two databases can report different SQL versions while both reference the same `b.so`. Replacing that file can change the code loaded by new sessions without changing either SQL version; existing sessions can retain an already loaded library. This follows from the catalogue and loader behavior. ([Extension catalogue](https://www.postgresql.org/docs/18/catalog-pg-extension.html), [function catalogue](https://www.postgresql.org/docs/18/catalog-pg-proc.html), [dynamic loading](https://www.postgresql.org/docs/18/xfunc-c.html#XFUNC-C-DYNLOAD))

Upstream can deliberately support separate libraries, such as `b-2.so` and `b-3.so`, selected by version-specific controls or scripts. That requires upstream-compatible packaging and runtime dependencies. An explicit SQL `VERSION` does not manufacture an isolated native binary.

PostgreSQL 18 adds `extension_control_path`, allowing control files outside the installation directory. The first matching primary control file wins; versions from different package directories are not merged. Native-library lookup remains separate. Changing `dynamic_library_path` alone does not redirect an explicit `$libdir/b` reference. This feature does not establish a portable PostgreSQL 15–18 mechanism for combining arbitrary releases. ([PG18 path settings](https://www.postgresql.org/docs/18/runtime-config-client.html#GUC-EXTENSION-CONTROL-PATH), [lookup implementation](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/commands/extension.c))

### Author and administrator responsibilities

Concrete upstream packaging examples:

| Project | Control-file creation | Native-library naming |
| --- | --- | --- |
| pgvector v0.8.2 | The source `vector.control` directly declares `default_version = '0.8.2'`. | `$libdir/vector`; the release number is absent from the library name. |
| PostGIS | The build substitutes its release version into `postgis.control.in`. | Default PostGIS 3 builds use `$libdir/postgis-3`. |

Sources: [pgvector control](https://github.com/pgvector/pgvector/blob/v0.8.2/vector.control), [pgvector build rules](https://github.com/pgvector/pgvector/blob/v0.8.2/Makefile), [PostGIS template](https://github.com/postgis/postgis/blob/master/extensions/postgis/postgis.control.in), [PostGIS generation rules](https://github.com/postgis/postgis/blob/master/extensions/postgis/Makefile.in). The PostGIS links describe moving upstream source checked on the research date.

PostGIS explicitly documents that its default library naming permits only one PostGIS 3 release per server installation. `--with-library-minor-version` restores names such as `postgis-3.6`, useful for testing separate minor lines. The name still does not distinguish patch releases, and this option alone does not resolve primary control-file ownership. ([PostGIS installation](https://postgis.net/docs/manual-dev/en/postgis_installation.html))

The documented administrator workflow is:

1. Install extension server files with the distribution package manager, or build/install upstream source against the intended PostgreSQL installation's `pg_config`.
2. Connect to each intended database and run `CREATE EXTENSION`, optionally selecting an explicit SQL version.
3. For an upgrade, first install the newer server files, then apply the extension's SQL upgrade in each database. Pgvector documents `ALTER EXTENSION vector UPDATE`; PostGIS documents `postgis_extensions_upgrade()` for its related modules.

Sources: [PostGIS package installation](https://postgis.net/documentation/getting_started/install_ubuntu/), [pgvector upgrades](https://github.com/pgvector/pgvector/blob/v0.8.2/README.md#upgrading), [PostGIS upgrades](https://postgis.net/documentation/getting_started/).

These workflows do not instruct administrators to edit the primary control file. Explicit selection uses SQL `VERSION` or `UPDATE TO`; updating without `TO` uses the packaged default. Manually editing `default_version` changes subsequent default selection, but does not install a library, migrate existing objects or provide binary isolation. Package replacement can overwrite that edit. ([ALTER EXTENSION](https://www.postgresql.org/docs/18/sql-alterextension.html))

Administrators can inspect the packaged default and current database version through `pg_available_extensions`, installable SQL versions through `pg_available_extension_versions`, and update routes through `pg_extension_update_paths()`. These expose metadata and script paths; they do not independently establish native release identity. ([Available defaults](https://www.postgresql.org/docs/18/view-pg-available-extensions.html), [available versions](https://www.postgresql.org/docs/18/view-pg-available-extension-versions.html), [extension information functions](https://www.postgresql.org/docs/18/functions-info.html#FUNCTIONS-INFO-EXTENSION))

### Installation packaging

The [installation-version proposal](../functional/items/proposed/installation-version-isolation.md) records the recommendation for human review.

### Agreed dependency scope

[E03](extensions-policy.md#e03--declared-dependency-names) defines the names-only policy. Exact tested dependency versions belong in verification records; native runtime packaging and PostgreSQL compatibility remain separate requirements.

## Resource and dataset sizes in the PostGIS family

Research checked on 14 October 2026. The [PROJ-grid proposal](items/proposed/proj-grid-scope.md) records the unresolved operation scope.

### Finding

TIGER is the clearest example of a large, external, application-populated
dataset, but it is not the only substantial geospatial data collection. PROJ
distributes optional coordinate-transformation grids separately from its
required runtime database. The PROJ CDN reports 806 MB of content. This describes the full
collection, not the download size of a required baseline. [PROJ CDN](https://cdn.proj.org/)

Those grids are not all equivalent to TIGER data. PROJ grids can be required
to perform a requested coordinate transformation accurately. PostGIS says
`ST_Transform` may error when a referenced grid is absent. PROJ can retrieve
needed grids from its CDN when networking is enabled, but network access is
disabled by default; relying on it conflicts with this project's offline
artifact tests. Thus retain `proj.db` and the ordinary PROJ configuration as
runtime resources, and treat optional grids as operation-specific resources:
bundle and verify those needed for advertised transformations, or state the
tested limits. A blanket “no grids” rule is unsafe. [PROJ resource files](https://proj.org/en/stable/resource_files.html),
[PROJ network capabilities](https://proj.org/en/stable/usage/network.html),
[PostGIS `ST_Transform`](https://postgis.net/docs/manual-dev/en/ST_Transform.html)

This matters even when the SQL only defines a schema object. For example, a
`CHECK (ST_X(ST_Transform(geom, 26910)) > 0)`, an expression index on
`ST_Transform(geom, 26910)`, or a materialized view selecting that expression
can execute the transform while applying or populating DDL. A schema parser
cannot infer that every transform will use a grid, but it also cannot safely
assume all DDL is independent of grids. This is an inference from PostGIS's
documented runtime behavior and PostgreSQL's expression-bearing schema
objects.

Other bundled geospatial defaults are small by comparison. GDAL's official
support-data RFC describes its then-current data directory as roughly 1.8 MB
uncompressed, mostly coordinate-system dictionaries, plus S-57 dictionaries,
seed files and logos. This is an older published figure, so it establishes
order of magnitude rather than a current exact package size. GDAL's ordinary
support files belong with the runtime; user raster/vector files, imagery,
basemaps and other project corpora are input data and should stay external.
GEOS does not have a comparable required geography corpus. [GDAL RFC 27](https://gdal.org/en/stable/development/rfc/rfc27_supportdata.html)

TIGER is distinctly different: its Census geography is downloaded/imported
into database tables for geocoding, and the PostGIS loader generates scripts
for selecting and loading geographic areas. It is not needed to create the
geocoder extension or use its basic normalization functions. The US address
standardizer's default lexicon, gazetteer and rules are instead part of that
extension's purpose and should be retained. No published current byte count
was found for those defaults, so do not describe them as large without
measuring the release being packaged. [PostGIS Extras](https://postgis.net/docs/Extras.html),
[TIGER loader](https://postgis.net/docs/Loader_Generate_Nation_Script.html)

### Packaging implication

Keep schema/install SQL and extension defaults, PROJ's required database and
GDAL's ordinary support files. Exclude TIGER Census imports and user imagery,
vector or raster corpora. Do not exclude every grid as “application data”:
record which transformations are tested offline and keep their required grid
resources available after relocation. Size claims should be measured per
selected release and archive; published figures above describe upstream
collections, not proposed bundle totals.
