# PostgreSQL distribution

A user downloads PostgreSQL and any selected extensions for their operating system and architecture, unpacks them into one writable directory, and uses the packaged tools to create and inspect a database schema. An operating-system and architecture pair selected in `support.json` is a target. The distribution selects the latest stable PostgreSQL release and one latest compatible release of each project in [extensions.md](extensions.md). `support.json` records the exact upstream versions, source URLs, checksums and targets used for a build.

## Download units and installation

PostgreSQL and each extension project have separate `.tar.gz` archives. Every archive contains one top-level `postgresql/` directory with files at their final installation paths. The PostgreSQL archive uses the normal `bin/`, `lib/` and `share/` layout. It includes `postgres`, `initdb`, `pg_ctl`, `psql`, `pg_dump`, `pg_restore` and their required support files.

An extension archive contains its native modules, SQL files and runtime dependencies under `postgresql/`. The archive contains no separate metadata file. Every archive carries the licence pointer described in [dependency-licenses.md](dependency-licenses.md). `support.json` records the selected project's SQL names, build inputs, extension and built-in prerequisites, and required PostgreSQL settings; `inventory.json` supplies the corresponding information for published downloads.

To install, unpack the PostgreSQL archive and each compatible extension archive into the same parent directory, preserving paths and permissions. Their `postgresql/` directories merge. Selected archives may share directories and identical files. Shared paths agree on member type, file bytes, link destination and permissions affecting use; file-versus-directory overlaps and incompatible copies are packaging conflicts rejected before extraction. Installing the same archives in a different order produces the same files, links and usable permissions. Each archive contains the runtime files it needs when installed with PostgreSQL and its declared extension prerequisites. A user can download PostgreSQL alone or add any compatible selection of extensions without a separate shared-dependency archive.

The installation runs from an arbitrary user-writable path without an installer, administrator privileges, host package manager or development tools. Dependencies not guaranteed by the selected target's operating system are bundled or linked into the archives. PostgreSQL and selected extensions continue to work after the installation moves and its original path becomes unavailable. Package loader paths and runtime data locations resolve within the moved installation.

An extension archive is compatible with the exact PostgreSQL build used to compile and verify it. Build results record that core archive’s checksum, and each published extension download identifies the matching core checksum. A rebuild of the same upstream PostgreSQL version does not establish compatibility with older extension outputs.

Archive names identify the project, selected release, PostgreSQL version where applicable, operating system and architecture. PostgreSQL uses `postgresql-<version>-<os>-<arch>.tar.gz`; an extension uses `<project>-<version>-postgresql-<build-version>-<os>-<arch>.tar.gz`. The project name in a filename is lowercase, with each run of non-alphanumeric characters replaced by `_` and leading or trailing underscores removed.

## Selected support and public downloads

`support.json` is the source of selected build targets. It records the PostgreSQL release, selected extension project releases, source URLs and checksums, SQL names, prerequisites, operating systems and architectures. A selected target remains visible when its build or verification fails.

`inventory.json` describes public downloads, not local archives or temporary CI artefacts. PostgreSQL entries are keyed by release and contain downloads by target. Extension entries are keyed by project and release, identify their SQL extension names, extension and built-in prerequisites, and required PostgreSQL settings or runtime setup. Their downloads are keyed by compatible PostgreSQL release and target. A client can therefore find the project archive for a SQL name such as `vector` and its setup requirements before downloading it. Each download provides an immutable URL and SHA-256. A PostgreSQL download lists the built-in SQL extensions found in that target's final archive.

The inventory advertises a target only after its final archive passes verification and the public URL serves those bytes. The minimum supported operating-system version for a target is recorded with its selection and used to set build options and assess system dependencies. The inventory and public download process are completed before publication; local build output stays outside the public inventory.
