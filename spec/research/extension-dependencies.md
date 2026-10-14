# PostgreSQL extension files, versions and dependencies

## PostgreSQL behavior (official documentation)

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

## Files and version coexistence

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

## Author and administrator responsibilities

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

## Implications for package metadata (recommendation for discussion, not an approved implementation)

For exact native release selection, assemble one chosen release of each extension and its dependencies into an installation. Use a separate installation prefix when another task needs a conflicting release. Preserve upstream controls and record their defaults. Supporting upstream-designed multiple SQL versions remains possible after testing their compatibility with the packaged library; do not infer it from script filenames or database version labels alone. This recommendation does not change the agreed specification without review.

## Agreed dependency scope

Record dependency names declared by the applicable upstream control files. Do not add dependency-version recommendations, researched compatibility ranges between extensions or a general version-resolution system.

Clients decide how to handle dependencies. A client may, for example, reject `CREATE EXTENSION ... CASCADE` when it would create a prerequisite not explicitly created beforehand. This is an example client policy, not a requirement on clients of this catalogue.

Build verification records exact dependency versions and tests that concrete combination. A successful result promises no compatibility across other dependency versions. PostgreSQL server-version compatibility and native/shared-runtime packaging remain separate requirements.
