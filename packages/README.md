# Building an extension package

## Package layout

A package is one downloadable archive supplying one or more SQL extensions. The build harness (`build.py` and its shared tooling) discovers packages from `packages/<package>/build.json`, using the folder name as the package name.

```text
packages/<package>/
  build.json              Sources, dependencies and expected SQL extensions
  build.sh                Build entry point
  probes/<extension>.sql  Tests run by the verifier
  internal/               Helpers, patches, lock files and other build-script details
```

The first three entries have the public contracts described below. `internal/` contains files used only by the build script. Additional public entries require discussion and an agreed contract specifying their format and how the harness uses them.

## Package metadata

`build.json` uses JSON; the comments below document its fields. Fields are required unless marked optional.

```jsonc
{
  // Source packages required by the build. The harness downloads, verifies and
  // extracts them into WORKSPACE/sources/<id>/. Ids match [a-z][a-z0-9_]*.
  // A single enclosing directory is removed; internal subdirectories are preserved.
  "sources": {
    "<id>": {
      "project": "Example Project", // Must match the project's entry in LICENSES.md.
      "url": "https://...", // Archive download URL e.g. .tar.gz or .tar.bz2 file.
      "sha256": "<64 hex digits>" // Expected archive checksum.
    }
  },
  // Every SQL extension expected in the package. Names are extension SQL names.
  "extensions": {
    "<name>": {
      // Optional, extension-level config for inventory.json as specified in ../design/distribution.md
      "config": {}
    }
  },
  // Optional, package-level config for inventory.json as specified in ../design/distribution.md
  "config": {},
  // Optional. Additional APT packages installed on Linux before build.sh runs
  "linux_apt_packages": ["<apt-package>"]
}
```

## Build script

The harness invokes `packages/<package>/build.sh`:

```text
build.sh OS ARCH WORKSPACE
```

- `OS`: `linux` or `macos`.
- `ARCH`: `arm64` or `x86_64`.
- `WORKSPACE`: an absolute path to this build's prepared workspace.

```text
WORKSPACE/
  sources/<id>/     Prepared source trees
  postgresql/       PostgreSQL development installation - can be modified if required
  build/            Intermediate build files
    dependencies/   Installation prefix for private dependencies
      lib/          Private dependency libraries
      lib64/        Where used by the dependency's build system
  payload/          Selected runtime files
```

On Mac the harness sets `MACOSX_DEPLOYMENT_TARGET` to the minimum supported macOS version. Build scripts use `WORKSPACE/postgresql/bin/pg_config`. They may install into this private PostgreSQL copy or stage installation beneath `build/` using `DESTDIR`.

The build script copies the files needed to use the extension into `payload/`, including libraries, control files, SQL files and required data. `payload/<path>` installs as `postgresql/<path>`. Build tools, headers and sources stay out of the payload.

The build script does not need to concern itself with portability of the payload folder. The harness copies required libraries from the build environment into `payload/`, then patches executables and libraries to find them using paths relative to their own location. This allows the installation directory to be moved. Libraries supplied by PostgreSQL or guaranteed by the operating system are reused. The harness handles any required signing.

The build script installs private dependencies under `WORKSPACE/build/dependencies/`. The build harness resolves library references using the build environment and this prefix's `lib/` and `lib64/` directories, copying only required libraries into `payload/`.

The build script includes runtime data and dynamically loaded libraries that binary inspection cannot discover, such as PostGIS's PROJ/GDAL data. The harness adds the licence pointer and creates the archive and checksum, following the [distribution layout and overlap rules](../design/distribution.md#archive-format-and-installation).

Each build has its own workspace. Before each invocation, the harness provides unmodified source trees, a fresh writable PostgreSQL copy, and empty `build/` and `payload/` directories. The workspace remains available until bundling finishes.

### Designing the build script

Use a single build script that calls the upstream build system with any options needed for the selected OS and architecture. Where platforms need only small differences, use conditionals around the platform-specific code.

If two platforms are sufficiently different that it is more elegant to maintain two separate build scripts, create e.g. internal/build-mac.sh and delegate to it.

Build scripts may check package-specific assumptions but should assume that the harness has fulfilled the contract, e.g. populating the right source directories and using valid OS and ARCH values.

## Probes

Every declared extension has a `probes/<extension>.sql` file that exercises representative behaviour and fails on a wrong result.

Build scripts should not verify the build output. Verification runs later in the build pipeline, including the SQL probes.

Before the probe file executes, `CREATE EXTENSION <sql-name> CASCADE` will already have been executed. The probe file should be a basic smoke test checking a bit of actual functionality and raising an exception on error. Assume that the extension is either fully working or completely broken, don't build a test suite for it.

Example probe for pgvector:

```sql
DO $$
BEGIN
    IF ('[1,2]'::vector <-> '[4,6]'::vector) IS DISTINCT FROM 5 THEN
        RAISE EXCEPTION 'Unexpected vector distance';
    END IF;
END;
$$;
```
