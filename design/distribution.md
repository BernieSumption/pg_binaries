# Mac ARM64 distribution

The first installation lets a user unpack PostgreSQL and selected extensions
into a writable directory, initialize a database, run schema DDL and use the
normal PostgreSQL command-line tools. It consists of the latest stable
PostgreSQL release and the latest stable release of pgvector compatible with
that PostgreSQL release. A selection records exact versions and source
checksums so the build cannot change inputs partway through a run.

## Download units and installation

PostgreSQL and each extension have separate `.tar.gz` archives. The
PostgreSQL archive contains one `postgresql/` directory with the normal
`bin/`, `lib/` and `share/` layout. An extension archive contains a
project-named payload directory with paths relative to `postgresql/`, plus
a sibling `metadata.json`. To install an extension, copy its payload into
the PostgreSQL directory, merging directories and rejecting conflicting
files. The metadata file describes the archive; it is not copied into the
installation.

An extension archive identifies its PostgreSQL build version, macOS ARM64
target, SQL extension names, required extension projects, and required
PostgreSQL settings or runtime setup. The PostgreSQL archive identifies its
version, target and built-in SQL extensions from the packaged control files.
Archive names include the project, selected version, PostgreSQL version where
applicable, operating system and architecture.

The installation works from an arbitrary user-writable path, without an
installer, administrator privileges, host package manager or development
tools. PostgreSQL and extension runtime dependencies are bundled unless a
dependency is guaranteed by the supported operating system. Moving the
installation leaves `initdb`, `pg_ctl`, `psql`, `pg_dump`, `pg_restore` and
selected extension functionality usable.

## Platform-shaped support data

`support.json` declares the currently selected PostgreSQL and extension
releases and the targets being built. Its target keys include an operating
system and architecture, such as `macos-arm64`; adding another target uses
the same structure. It records source URLs and checksums and extension
prerequisites. A target is selected only when it is part of the current
slice.

`inventory.json` advertises public downloads only. PostgreSQL entries are
keyed by release and contain a `downloads` map keyed by target. Extension
entries are keyed by project, release and compatible PostgreSQL release, then
by target in a `downloads` map. Each download gives an immutable URL and
SHA-256. The PostgreSQL download entry also lists its packaged built-in SQL
extensions, since built-ins can vary by platform. No entry advertises an
unbuilt or unverified target. The inventory appears when archives are first
published; local build output remains outside it.

The source tree uses `scripts/postgresql/`, `scripts/extensions/<project>/`,
`scripts/platform/<os>/` and `scripts/verify/`. Each project owns its build
and SQL probe. Platform code supplies native setup and dependency inspection.
Generated archives, build trees and VM state stay outside Git.
