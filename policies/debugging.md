# Diagnosing packaged PostgreSQL failures

Clients run PostgreSQL and its extensions inside their own application or development environment. When a packaged process fails, maintainers need enough information to distinguish a PostgreSQL or extension error from a missing runtime file, an incompatible system library, or a native crash. The diagnostic process must use ordinary process and file APIs so clients can collect evidence without an installer.

## Identify the exact package

Every diagnostic report must identify the operating system and architecture, the PostgreSQL and extension versions, and the archive URLs and SHA-256 checksums used to assemble the installation. Include the inventory revision or retrieval time and the package metadata when present. The archive checksums identify the actual bytes even when a client has copied several packages into one prefix.

Builds must carry a stable build identifier in package metadata. It must distinguish rebuilds of the same source version and identify the source revision, build configuration, target platform and architecture. Preserve the identifier in build records and associate each produced binary with its archive checksum. Version strings alone cannot identify a binary after a rebuild.

## Collect process and server evidence

Clients must be able to direct PostgreSQL output to a known writable location using standard process APIs. For server startup through `pg_ctl`, use its `-l` option to capture server output; when a client launches `postgres` directly, capture both standard output and standard error. Preserve the complete log from startup through failure, along with the command line, working directory, exit status, and the time of failure. PostgreSQL application errors such as extension errors and missing support files are diagnosed from these logs.

For a process that cannot start or exits abnormally, collect the operating system's loader or crash report where available. Also record the exact executable and extension module paths involved, the loader error text, and the environment variables that affect library or support-file lookup. On Linux, include `ldd` or `LD_DEBUG=libs` output as applicable; on macOS, include `otool -L` and the crash report; on Windows, include the full loader dialog or event report and the executable's exit code. Run inspection tools against the installed package and record their versions. Do not require installing a diagnostic helper to collect this evidence.

Reports should include only evidence needed to reproduce and locate the failure. Clients must review logs, command lines and environment values for credentials, connection strings, user data and other secrets before sharing them. Do not request database contents or a full data directory by default.

## Resolve native symbols

Release binaries must retain a platform build identifier or equivalent that links each executable and shared module to matching debug symbols. Keep unstripped symbols or platform debug-symbol files for PostgreSQL and packaged extensions as build artifacts, indexed by build identifier and archive checksum. On ELF platforms use the ELF build ID and separate debug information; on macOS retain matching dSYM bundles and UUIDs; on Windows retain matching PDB files and image identifiers. Symbol files must be generated from the exact binary bytes placed in the archive. Stripping or symbol-file generation must not change the archived binary after its checksum and symbol association are recorded.

Symbols need not be included in client archives. They must remain available to maintainers for as long as the corresponding download is advertised, and be retrievable from a build record without requiring the client to rebuild the package. A crash report containing module paths, build identifiers and addresses can then be resolved against the matching symbols. If symbols or build identifiers are missing for an artifact, record that limitation with the build evidence rather than attempting to resolve addresses against a nearby version.

## Verify diagnostic collection

For representative failures, verify that the documented collection steps provide enough evidence to identify the package and investigate the cause. Exercise one system-level failure, such as a missing shared library or a native process crash, and one PostgreSQL log failure, such as an extension error or missing support file. Confirm that the report includes package checksums, build identifiers, logs or OS failure details, and matching symbols where a stack trace is available. Follow [testing.md](testing.md) for the required test evidence and retain the collection output with the archive and environment identifiers.

## Current implementation gaps

The pilot package manifests identify component and version, PostgreSQL version, platform and architecture, but do not consistently provide a unique build identifier or source revision. The build scripts do not preserve or index matching debug symbols for Linux, macOS or Windows artifacts. Linux and macOS verification already start PostgreSQL with a log file, and Windows does the same with `pg_ctl -l`; there is no common client-facing diagnostic record format or representative failure-collection check across platforms. These gaps must be closed before claiming the diagnostic process is implemented.
