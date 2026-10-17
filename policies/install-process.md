# Installing PostgreSQL and extensions

Clients download a PostgreSQL archive and any required extension archives, unpack them, and copy their files into one installation prefix. PostgreSQL and its extensions must then work with ordinary process and shell tools, without running an installer or depending on the build machine.

## Archive layout

Each platform and architecture has a PostgreSQL `.tar.gz` archive containing one top-level `postgresql/` directory. Its contents use PostgreSQL's normal installation layout: commands in `bin/`, shared libraries in `lib/`, and support files in `share/`, including `share/extension/` and `share/locale/` where provided. The Linux pilot keeps native executable payloads in `libexec/` and places statically linked launchers in `bin/` so commands use the bundled C library after relocation without invoking a host shell. Include all runtime libraries and other files needed by the packaged programs, along with applicable licence and notice files.

The PostgreSQL archive must include `postgresql/manifest.json` identifying its PostgreSQL version, target operating system and architecture, and included SQL extension names. The target fields must match the candidate download claim, and the included names must match the packaged `.control` files so the inventory cannot advertise a different package.

Each extension archive name identifies its project, selected extension version, platform and PostgreSQL build version or verified support range. Native modules may need separate archives for different PostgreSQL majors; the inventory alone advertises which PostgreSQL versions can use an archive, after those versions pass the required tests. The `.tar.gz` contains a payload directory named for the extension project and a sibling `metadata.json` file:

```text
archive root/
├── pgvector/
│   ├── lib/vector.so
│   ├── share/extension/vector.control
│   ├── share/extension/vector--<version>.sql
│   └── LICENSES/...
└── metadata.json
```

The payload directory contains files at paths relative to the PostgreSQL installation prefix. An extension may add support data under `share/` or runtime libraries under `lib/`. Include redistribution notices for the extension and bundled dependencies in the payload directory.

Archives must not require installer scripts, environment setup from the build machine, or a fixed extraction path. Preserve executable file permissions for packaged programs that require them. Archive names and download URLs identify their platform, architecture, and version as described in `policies/releases.md`.

## Installation

1. Unpack the PostgreSQL archive. The resulting `postgresql/` directory is the installation prefix.
2. For each selected extension, unpack its archive and copy the contents of the project-named payload directory into the PostgreSQL prefix, preserving relative paths and merging directories. Leave the sibling `metadata.json` available for inspection; do not copy it into the PostgreSQL prefix. Replace neither PostgreSQL files nor files from another extension silently; packaging conflicts must be resolved before release.
3. Run tools from the prefix's `bin/` directory or add that directory to `PATH`. Initialize a database with `initdb`, then manage it with `pg_ctl` and connect with `psql` or another PostgreSQL client.

Use ordinary archive extraction and file-copy operations, either through a client's archive library or tools available on the supported system. No post-extraction installer, generated configuration, registration step, or privileged installation is required. The installation can live in a user-writable directory and PostgreSQL can run as an ordinary user. Clients may install by downloading and extracting directly to a chosen directory, provided they preserve the same layout and merge extension files in the same way.

## Extension metadata and prerequisites

An extension archive must include machine-readable JSON metadata in the sibling `metadata.json` file at the archive root. Metadata identifies the project, release version, target operating system and architecture, every SQL extension name provided by the project, required extension projects, and explicit lists of PostgreSQL configuration and runtime prerequisites, empty when none apply. The target fields must match the archive's candidate platform so a download cannot claim another target without changing its bytes. Metadata must distinguish required setup from optional recommendations and name the affected configuration setting and value when setup is needed. The package metadata format must stay small and descriptive; it does not define an installer language or a collection of user-selectable install modes.

The inventory remains authoritative for which SQL extension versions and PostgreSQL ranges are available. The metadata in an archive describes how to use that particular package: for example, prerequisite extensions that must also be copied into the prefix, or a requirement to add `pg_stat_statements` to `shared_preload_libraries` before starting the server. It must not imply that metadata itself performs configuration. A client can inspect the metadata and apply the documented steps using its own configuration interface.

Extension prerequisites must be explicit and resolvable from supported packages. Include required runtime libraries in the PostgreSQL or extension archive unless the functional specification guarantees their presence on every supported machine. Do not rely on packages installed by a system package manager, developer tools, shell startup files, or machine-specific library paths.
When an extension needs a built-in SQL extension that has no separate project archive, list its SQL name and `CREATE EXTENSION` step in `configuration_prerequisites`. The sibling control file remains authoritative for PostgreSQL dependency ordering.

## Relocation

All packaged programs, support files, and extensions must continue to work after the installation prefix is moved. Do not encode the build path or require the original extraction location. Resolve PostgreSQL support files relative to the executable or through PostgreSQL's standard relocatable installation behaviour. Bundled shared libraries must be found using platform mechanisms that work from the relocated prefix.

Tests must make the original prefix unavailable before exercising the relocated installation, following `specs/testing.md`. Installation guidance and client implementations must preserve the archive layout and use the same copy process tested there.

## Current spike evidence

The pilot scripts currently build PostgreSQL and extension archives separately. All three x86-64 pgvector pilots use the project-named payload and sibling metadata described above. The [HypoPG 1.4.3 Linux feasibility run](https://github.com/BernieSumption/pg_binaries/actions/runs/38986224334) passed on x86-64 and arm64, checking this layout, file collisions and relocated installation on a clean current Ubuntu container. The PostGIS 3.6.4 Linux pilot stages prefix-relative payload files and sibling metadata that describes its bundled runtime data and the environment paths required to locate it. [Both architecture jobs](https://github.com/BernieSumption/pg_binaries/actions/runs/38987607546) passed archive merge and relocation on clean current Ubuntu and Linux 5.15 QEMU guests on 2026-10-17. These format checks do not establish every operating system or dependency claim required for publication.
