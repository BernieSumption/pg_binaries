# PostgreSQL distribution

A user downloads PostgreSQL and the extensions they need, extracts the archives into one writable directory, and uses the packaged tools to create and inspect a database schema. The installation runs without administrator privileges, a host package manager or development tools.

A target is an operating system and CPU architecture, such as macOS ARM64. The distribution provides the latest stable PostgreSQL release and the latest compatible release of each selected upstream project in [extensions.md](extensions.md) for its selected targets.

A package is a downloadable archive produced by one build job for a target. The `postgresql` package supplies PostgreSQL and its built-in SQL extensions. Other packages supply groups of SQL extensions that can be installed alongside PostgreSQL without downloading another extension package.

Extensions connected by dependencies are built and packaged together. If A and B both require C, all three belong to the same package. PostgreSQL’s built-in extensions are supplied by the common `postgresql` package and do not join these groups. This grouping concerns SQL extensions; shared native libraries are handled by the packaging rules below.

Package names identify build recipes and downloads; SQL extension names are used in `CREATE EXTENSION`. The pgvector package supplies `vector`. The PostGIS package supplies `postgis`, `postgis_raster`, `postgis_sfcgal`, `postgis_topology` and `postgis_tiger_geocoder`. TIGER Geocoder has its own source release but is built in the PostGIS package’s job because it depends on PostGIS. Address Standardizer has a separate package containing `address_standardizer` and `address_standardizer_data_us`.

## Choosing downloads

`inventory.json` maps SQL extension names to package names, including built-ins such as `citext` in the `postgresql` package. A client selects its target, looks up the requested SQL names and downloads each distinct package once, together with `postgresql`.

Download URLs are immutable. Clients select PostgreSQL and extension packages from the same inventory, which describes a complete release built and verified together.

## Download units and installation

PostgreSQL has its own `.tar.gz` archive, and each extension package is a separate `.tar.gz` archive. Every archive contains one top-level `postgresql/` directory with files at their final installation paths. The PostgreSQL archive uses the normal `bin/`, `lib/` and `share/` layout and includes `postgres`, `initdb`, `pg_ctl`, `psql`, `pg_dump`, `pg_restore` and their support files. Each extension archive contains its modules, SQL files and runtime dependencies.

Installation consists of extracting the PostgreSQL archive and the chosen extension archives into the same parent directory, preserving paths and permissions. Their `postgresql/` directories merge into one installation. Each extension package contains its required SQL extensions beyond those supplied by PostgreSQL. PostgreSQL can also be installed alone.

The installer executes no downloaded code, installation scripts, hooks or SQL, and makes no configuration changes. Archives and inventory records provide no commands for the installer to execute.

The archives supply the runtime libraries and data needed beyond the components guaranteed by the target operating system. Each extension archive supplies what it needs alongside PostgreSQL, so users can choose extensions without downloading a separate shared-dependency archive.

The archives contain PostgreSQL executables, extension libraries and SQL files for use after installation. Creating a database, starting PostgreSQL and issuing `CREATE EXTENSION` are runtime operations, not installation steps. Any automated behaviour beyond file extraction requires an explicitly defined protocol; free-text instructions are not an installation interface.

Every archive contains the licence pointer described in [dependency-licenses.md](dependency-licenses.md). Download metadata is supplied through `inventory.json`; the archives contain no separate metadata file.

### Installation paths

The installation runs from any user-writable path. PostgreSQL and its extensions continue to work if the software directory is moved and its original path becomes unavailable. References to packaged libraries and runtime data resolve within the moved installation.

### Files shared between archives

Archives can contain shared directories and identical files. When two archives contain the same path, they agree on the file type, contents, link destination and permissions affecting use. Conflicting files or a file in place of a directory are packaging errors rejected before extraction. Extracting the selected archives in a different order produces the same installed files, links and usable permissions.

## Archive names

- PostgreSQL: `postgresql-<version>-<os>-<arch>.tar.gz`
- Extension: `<package>-postgresql-<postgresql-version>-<os>-<arch>.tar.gz`

Package names in filenames are lowercase. Each run of non-alphanumeric characters becomes `_`, with leading and trailing underscores removed. A package can combine several upstream releases, so their versions are recorded in the inventory rather than as one extension version in the archive name. The GitHub release tag in the download URL distinguishes successive builds.

## Inventory format

`inventory.json` in the repo root records what downloads are available. The file format is JSON; this example shows it in YAML for readability. Versions, targets and the subset of extensions shown illustrate the format rather than declare available downloads.

The example defines the full set of inventory fields. Any change to these fields requires an item in `HUMAN_REVIEW_QUEUE.md` and human approval before implementation.

```yaml
schema_version: 1

os_support:
  macos:
    minimum_version: "major.minor"
  windows:
    minimum_version: "major.minor.build.revision"
  linux:
    minimum_version: "major.minor" # Linux kernel version

packages:
  postgresql:
    version: "18.6"
    downloads:
      macos-arm64:
        url: "https://github.com/BernieSumption/pg_binaries/releases/download/<tag>/postgresql-18.6-macos-arm64.tar.gz"
        sha256: "<PostgreSQL archive checksum>"
      linux-arm64:
        url: "https://github.com/BernieSumption/pg_binaries/releases/download/<tag>/postgresql-18.6-linux-arm64.tar.gz"
        sha256: "<Linux PostgreSQL archive checksum>"
  postgis:
    downloads:
      macos-arm64:
        url: "https://github.com/BernieSumption/pg_binaries/releases/download/<tag>/postgis-postgresql-18.6-macos-arm64.tar.gz"
        sha256: "<PostGIS package checksum>"
  pgvector:
    downloads:
      macos-arm64:
        url: "https://github.com/BernieSumption/pg_binaries/releases/download/<tag>/pgvector-postgresql-18.6-macos-arm64.tar.gz"
        sha256: "<pgvector package checksum>"

extensions:
  citext: # SQL name used in CREATE EXTENSION
    package: postgresql
  vector:
    package: pgvector
    version: "0.8.7"
  postgis:
    package: postgis
    version: "3.6.4"
  postgis_raster:
    package: postgis
    version: "3.6.4"
  postgis_sfcgal:
    package: postgis
    version: "3.6.4"
  postgis_topology:
    package: postgis
    version: "3.6.4"
  postgis_tiger_geocoder:
    package: postgis
    version: "2025.2"
  example_target_specific_extension:
    package: postgresql
    targets: [macos-arm64] # Illustrates a restriction within a package
```

`version` records the selected upstream release, rather than the SQL extension’s internal version. Built-in extensions omit it because they are supplied with PostgreSQL.

An extension is available on every target with a download for its package unless its optional `targets` list narrows that set. The list contains only targets with a package download. Verification checks that each target’s extension mapping matches the SQL extensions supplied by its archives. A package is advertised for a target only when the extensions it supplies have all their required extension files in that package or in PostgreSQL.

The inventory is downloaded from `https://github.com/BernieSumption/pg_binaries/releases/latest/download/inventory.json`. Each release builds and uploads the complete selected archive set and publishes an inventory pointing to that release’s archives.

## Build selection and publication

`support.json` records what the repository intends to build: exact PostgreSQL and upstream extension releases, source URLs and checksums, and selected targets. It records package grouping, supplied SQL names, build inputs, extension prerequisites and required PostgreSQL settings. A failed build or verification job leaves that selection intact so the missing target remains visible.

The minimum supported OS version is recorded with each target. Build options and allowed system dependencies are chosen to support that version. Publication includes the applicable minimum versions in `os_support`.

Publication adds package downloads and their SQL extension mappings to `inventory.json` after the archives pass verification and their public URLs serve the tested bytes. [Build and verification](build-and-test.md) defines how the archives are produced and tested, and how publication checks their metadata and public availability.
