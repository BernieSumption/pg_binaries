# PostgreSQL distribution

A distribution is a set of files and metadata that allows a client to download a Postgres release for its desired target (eg macos-arm64) with desired extensions and unpack and configure them to create a local, portable Postgres installation.

## Using the distribution

Clients know their target operating system and architecture and set of extensions required. To install and run PostgreSQL, a client:

- Downloads `inventory.json` from `https://github.com/BernieSumption/pg_binaries/releases/latest/download/inventory.json` and saves it locally in a folder named after its `inventory_version`. Subsequent package downloads for this installation use that saved inventory.
- Looks up the SQL extension names in the inventory, checks their availability for the target and identifies their packages (downloadable archives).
- Downloads the package identified by `postgresql.package` and each distinct extension package for the target using the inventory’s URLs, and verifies their SHA-256 checksums. An empty extension set selects PostgreSQL alone.
- Extracts the archives into the same parent directory, preserving their layout and permissions. Their `postgresql/` directories merge into one installation.
- Combines the `config` fields of the selected SQL extensions and their packages, including the PostgreSQL package.
- Initialises a PostgreSQL data directory and starts PostgreSQL with the combined configuration.
- Creates the database and executes DDL there, including `CREATE EXTENSION` statements.

## Inventory format

`inventory.json` is a generated build artefact published with the release. It records the available package downloads and their configuration metadata. The file format is JSON; this example shows it in YAML for readability. Versions, targets and the subset of extensions shown illustrate the format rather than declare available downloads.

The example defines the full set of inventory fields. Adding or changing a field, its meaning, or its allowed settings and values requires an item in `HUMAN_REVIEW_QUEUE.md` and human approval before implementation.

```yaml
schema_version: 1
inventory_version: "18.6-2026-10-27-a4c92e1f"

os_support:
  macos:
    minimum_version: "major.minor"
  windows:
    minimum_version: "major.minor.build.revision"
  linux:
    minimum_version: "major.minor" # Linux kernel version

postgresql:
  package: postgresql
  version: "18.6"

packages:
  postgresql:
    downloads:
      macos-arm64:
        url: "<release URL>/postgresql-18.6-macos-arm64.tar.gz"
        sha256: "<PostgreSQL archive checksum>"
      linux-arm64:
        url: "<release URL>/postgresql-18.6-linux-arm64.tar.gz"
        sha256: "<Linux PostgreSQL archive checksum>"
  postgis:
    config:
      environment_paths:
        PROJ_DATA: share/proj
    downloads:
      macos-arm64:
        url: "<release URL>/postgis-postgresql-18.6-macos-arm64.tar.gz"
        sha256: "<PostGIS package checksum>"
  pgaudit:
    downloads:
      macos-arm64:
        url: "<release URL>/pgaudit-postgresql-18.6-macos-arm64.tar.gz"
        sha256: "<pgaudit package checksum>"

extensions:
  citext: # SQL name used in CREATE EXTENSION
    package: postgresql
  postgis:
    package: postgis
    version: "3.6.4"
  postgis_tiger_geocoder:
    package: postgis
    version: "2025.2"
  pgaudit:
    package: pgaudit
    version: "<selected release>"
    config:
      shared_preload_libraries: [pgaudit]
  example_target_specific_extension:
    package: postgresql
    targets: [macos-arm64] # Illustrates a restriction within a package
```

### Inventory identity

`schema_version` identifies the format. `inventory_version` has the format `{postgres-version}-YYYY-MM-DD-{random-8-hex-digits}`, assigned by the inventory producer. The PostgreSQL version matches `postgresql.version`; the date is the inventory creation date in UTC, and the suffix is eight random lowercase hexadecimal digits. The producer must assign a new identifier whenever it changes the inventory’s contents. Clients can use this identifier without knowing a GitHub release tag. Publication must not reuse identifiers or replace an existing release’s inventory with different contents.

### Operating-system support

`os_support` maps operating systems to their supported minimum versions. `minimum_version` is the macOS or Windows version, or the Linux kernel version, using the formats shown in the example.

### PostgreSQL

`postgresql.package` identifies the entry in `packages` that supplies PostgreSQL and its built-in SQL extensions. `postgresql.version` records the PostgreSQL release.

### Packages

A package is a downloadable archive produced by one build job for a target. Extension packages supply groups of SQL extensions that can be installed alongside PostgreSQL without downloading another extension package.

Extensions connected by dependencies are built and packaged together. If A and B both require C, all three belong to the same package. PostgreSQL’s built-in extensions are supplied by the PostgreSQL package and do not join these groups. This grouping concerns SQL extensions; shared native libraries are handled by the packaging rules below.

Package names identify build recipes and downloads. The pgvector package supplies `vector`. The PostGIS package supplies `postgis`, `postgis_raster`, `postgis_sfcgal`, `postgis_topology` and `postgis_tiger_geocoder`. TIGER Geocoder has its own source release but is built in the PostGIS package’s job because it depends on PostGIS. Address Standardizer has a separate package containing `address_standardizer` and `address_standardizer_data_us`.

The `packages` map is keyed by package name. Optional package `config` supplies the [paths to packaged data](#paths-to-packaged-data).

`downloads` maps targets to archives. Each entry’s `url` identifies the archive and `sha256` records its SHA-256 checksum. Download URLs are immutable. Each inventory describes a complete release built and verified together; PostgreSQL and extension packages for an installation come from the same inventory.

### SQL extensions

The `extensions` map is keyed by the SQL name used in `CREATE EXTENSION`. Each entry’s `package` identifies the package supplying its files. Its `version` is the SQL extension version reported by PostgreSQL after creation from the verified archive. Built-in extensions omit `version` because they are supplied with PostgreSQL.

Optional extension `config` supplies the [PostgreSQL startup settings](#postgresql-startup-settings).

An extension is available on every target with a download for its package unless its optional `targets` list narrows that set. The list contains only targets with a package download. Verification checks that each target’s extension mapping matches the SQL extensions supplied by its archives. A package is advertised for a target only when the extensions it supplies have all their required extension files in that package or in PostgreSQL.

## Archive format and installation

PostgreSQL has its own `.tar.gz` archive, and each extension package is a separate `.tar.gz` archive. Every archive contains one top-level `postgresql/` directory with files at their final installation paths. The PostgreSQL archive uses the normal `bin/`, `lib/` and `share/` layout and includes `postgres`, `initdb`, `pg_ctl`, `psql`, `pg_dump`, `pg_restore` and their support files. Each extension archive contains its modules, SQL files and runtime dependencies.

The installer executes no downloaded code, installation scripts, hooks or SQL, and makes no configuration changes. Archives and inventory records provide no commands for the installer to execute.

The archives supply the runtime libraries and data needed beyond the components guaranteed by the target operating system. Each extension archive supplies what it needs alongside PostgreSQL, so users can choose extensions without downloading a separate shared-dependency archive.

The packaged executables and SQL files are used after extraction to initialise and start PostgreSQL and create extensions. Configuration is defined by the inventory fields below; free-text instructions are not an installation interface.

Every archive contains the licence pointer described in [dependency-licenses.md](dependency-licenses.md). Download metadata is supplied through `inventory.json`; the archives contain no separate metadata file.

### Installation paths

The installation runs from any user-writable path. PostgreSQL and its extensions continue to work if the software directory is moved and its original path becomes unavailable. References to packaged libraries and runtime data resolve within the moved installation.

### Files shared between archives

Archives can contain shared directories and identical files. When two archives contain the same path, they agree on the file type, contents, link destination and permissions affecting use. Conflicting files or a file in place of a directory are packaging errors rejected before extraction. Extracting the selected archives in a different order produces the same installed files, links and usable permissions.

### Archive names

- PostgreSQL: `postgresql-<version>-<os>-<arch>.tar.gz`
- Extension: `<package>-postgresql-<postgresql-version>-<os>-<arch>.tar.gz`

Package names in filenames are lowercase. Each run of non-alphanumeric characters becomes `_`, with leading and trailing underscores removed. A package can combine several releases, so their versions are recorded in the inventory rather than as one extension version in the archive name. The GitHub release tag in the download URL distinguishes successive builds.

### Creating SQL extensions

The archives supply PostgreSQL control files and SQL files for creating their advertised extensions with `CREATE EXTENSION`. The control files identify SQL prerequisites so PostgreSQL can create them through `CREATE EXTENSION ... CASCADE`. All required files are included in the extension package or the PostgreSQL package.

Verification exercises creation through these control files. Missing prerequisite declarations are resolved before publication rather than hidden by manually creating unrecorded prerequisites.

## PostgreSQL startup configuration

To install a database with a set of SQL extensions, the combined startup configuration is the union of the `config` fields on those extensions and their packages, including the package identified by `postgresql.package`. Configuration on other SQL extension records in the same packages does not apply. The combined configuration supplies environment variables to the PostgreSQL server process and settings to PostgreSQL at startup.

Package configuration identifies bundled data directories. SQL-extension configuration identifies required PostgreSQL settings. An omitted field declares no additional requirement of that kind. Each extension record includes the configuration required by its SQL prerequisites, so clients do not need to traverse a dependency graph.

### Paths to packaged data

For each selected package, `config.environment_paths` maps an environment-variable name to a directory relative to the extracted `postgresql/` directory. The client resolves the directory against the current installation path and sets the variable in the PostgreSQL server process’s environment. It does not modify the host’s environment or shell startup files. After a move, paths are resolved again from the new installation location.

Values identify existing directories inside the installation; absolute paths and paths or links that escape it are rejected.

### PostgreSQL startup settings

`config.shared_preload_libraries` lists modules that must be loaded at PostgreSQL startup before the SQL extension can be created. A compliant client includes these modules in PostgreSQL’s `shared_preload_libraries` setting, combining requirements from multiple extensions without duplicate entries. This field allows the module names `pgaudit` and `pg_ivm`. Values are library names; filesystem paths and commands are rejected.
