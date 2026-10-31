# Building an extension package

## Package layout

A package is one downloadable archive supplying one or more SQL extensions. The build harness (`build.py` and its shared tooling) discovers packages from `packages/<package>/build.json`, using the folder name as the package name.

```text
packages/<package>/
  build.json              Sources, dependencies and expected SQL extensions
  build.sh                Linux and macOS build entry point
  build.ps1               Windows build entry point
  build-dependencies.sh   Optional Linux/macOS private-dependency build phase
  build-dependencies.ps1  Optional Windows private-dependency build phase
  probes/<extension>.sql  Tests run by the verifier
  internal/               Helpers, patches, lock files and other build-script details
```

The metadata, build entry points and probes have the contracts described below. `internal/` contains helpers used by those build scripts. Additional public entries require discussion and an agreed contract specifying their format and how the harness uses them.

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
      "url": "https://...", // HTTPS tar archive URL; gzip, bzip2 and xz compression are supported.
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

The harness invokes `packages/<package>/build.sh` on Linux and macOS, or `build.ps1` through PowerShell on Windows. Both receive:

```text
build.sh OS ARCH WORKSPACE
```

- `OS`: `linux`, `macos` or `windows`.
- `ARCH`: `arm64` or `x86_64`.
- `WORKSPACE`: an absolute path without whitespace to this build's prepared workspace. Upstream PostgreSQL build files require this; the final installation can be moved to a path containing spaces.

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

On Mac the harness sets `MACOSX_DEPLOYMENT_TARGET` to the minimum supported macOS version and supplies linker options in `PG_LDFLAGS` to reserve space for later library-path changes. Standard PGXS builds use these settings without extra arguments. Build scripts leave `MACOSX_DEPLOYMENT_TARGET` unchanged and retain the supplied `PG_LDFLAGS` when adding their own linker options. For build systems that do not interpret these environment variables, build scripts pass the equivalent compiler and linker options explicitly. Any prebuilt runtime libraries included by the build script must support the supplied minimum macOS version.

Build scripts use `WORKSPACE/postgresql/bin/pg_config`. They may install into this private PostgreSQL copy or use `build/` for build output.

The build script copies the files needed to use the extension into `payload/`, including libraries, control files, SQL files and required data. `payload/<path>` installs as `postgresql/<path>`. Build tools, headers and sources stay out of the payload.

Build scripts should default to statically linking package-private dependency libraries into extension modules and hiding the dependency symbols from other modules. PostgreSQL's extension entry points remain exported. This is because two extensions requiring different versions of the same library can lead to runtime issues. Later stages of the build pipeline validate that dependencies supplied by different extension packages do not cause symbol-binding conflicts. Using static linking reduces the chance of such a conflict.

Dynamic linking is used where static linking creates substantial build, plugin or licence constraints. The reason is recorded with the package's build implementation. libc and compiler support libraries retain their platform-specific linkage.

The harness copies required libraries from the build environment into `payload/`, then patches executables and libraries to find them using paths relative to their own location. This allows the installation directory to be moved. Libraries supplied by PostgreSQL or guaranteed by the operating system are reused. The harness handles any required signing.

The build script installs private dependencies under `WORKSPACE/build/dependencies/`. PGXS builds put private `-L` options first in command-line `PG_LDFLAGS`, retaining the harness flags, so private libraries precede inherited system paths. The build harness resolves library references using the build environment and this prefix's `lib/` and `lib64/` directories, copying only required libraries into `payload/`.

The build script includes runtime data and dynamically loaded libraries that binary inspection cannot discover, such as PostGIS's PROJ/GDAL data. The harness adds the licence pointer and creates the archive and checksum, following the [distribution layout and overlap rules](../design/distribution.md#archive-format-and-installation).

Each build has its own workspace. A fresh build receives unmodified source trees, a fresh writable PostgreSQL copy, and empty `build/` and `payload/` directories. Local iteration can retain source and intermediate build state, including installed dependencies and compiled Rust crates. Each invocation still receives a fresh PostgreSQL copy and empty `payload/` and `build/stage/` directories. The workspace remains available until bundling finishes. [Local iteration](LOCAL_ITERATION.md) defines the reuse command and invalidation rules.

### Dependency build phase

A package with expensive source-built dependencies can supply `build-dependencies.sh` or `build-dependencies.ps1`, receiving the same `OS ARCH WORKSPACE` arguments as its build entry point. It installs dependencies under `WORKSPACE/build/dependencies/`. Its helpers and lock files belong under `internal/dependencies/`; this directory separates dependency build inputs from the extension build implementation.

The harness runs the dependency phase before the main build on a fresh workspace. During local iteration it reuses a successful dependency installation while the declared sources, dependency script and helpers, PostgreSQL input, target, compiler and build settings match. Changes to the main build implementation preserve the dependency installation. Dependency scripts perform their build without implementing cache lookup or storage themselves.

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
