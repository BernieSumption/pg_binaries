# Building PostgreSQL

PostgreSQL is compiled once per target. That installation supplies the runtime archive downloaded by users and a development archive used to build extension packages.

`build.json` declares source archives and `linux_apt_packages` using the formats in [the package guide](../README.md#package-metadata). PostgreSQL has no `extensions` field: its built-in SQL extensions are determined from the selected PostgreSQL source and capabilities. The source named `postgresql` is PostgreSQL itself; the other sources supply dependencies built on macOS. Linux uses the declared APT packages for those dependencies. Windows uses vcpkg at the commit pinned in `internal/vcpkg-commit.txt`, which is included in build records.

The harness prepares verified sources under `WORKSPACE/sources/<id>/` and empty build and installation directories, then invokes `build.sh` on Linux/macOS or `build.ps1` on Windows:

```text
build.sh OS ARCH WORKSPACE
```

The script compiles PostgreSQL and its selected built-in extensions into `WORKSPACE/postgresql/`. On macOS it first builds private dependencies under `WORKSPACE/build/dependencies/`. The harness supplies `MACOSX_DEPLOYMENT_TARGET`.

The harness reads the PostgreSQL version from the installed `pg_config`. It copies the installation into `WORKSPACE/payload/`, removes development-only files, bundles required libraries and makes the runtime installation relocatable. Linux retains its bundled loader and launcher; macOS rewrites library references and signs the resulting binaries; Windows places required DLLs beside the executables.

`WORKSPACE/development/` contains the same runnable installation plus headers, PGXS, static libraries and `pg_config`. Private dependency development files are included under `dependencies/`. The development archive contains one enclosing `postgresql/` directory, as does the runtime archive.

Each extension build receives a private writable copy of the development installation. The harness rewrites installation paths in PGXS and dependency configuration files for that copy. The development installation's `pg_config` wrapper translates compiled-in paths to its current location. `share/pg_build_paths.json` records the original paths and identifies the matching runtime archive by filename and checksum; it is included only in the development archive.

`build.py archive-check` validates the runtime archive's installation contract. The development archive is checked by checksum and by preparing and using its relocated installation in extension builds.

The archives are named `postgresql-<version>-<target>.tar.gz` and `postgresql-development-<version>-<target>.tar.gz`. The packaging command writes their checksums and a `postgresql-build.json` result containing the built version and both archive filenames and checksums. Later jobs use that result rather than reconstructing filenames from a separately declared version. Verification checks the version reported by the runtime archive's `postgres` executable. During PostgreSQL-only verification, the shared verifier invokes the Python checks in `probes/` for PostgreSQL capabilities, built-in extensions and TLS.
