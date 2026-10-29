# PostgreSQL build options

This document selects PostgreSQL features for creating and inspecting application schemas. The build uses the latest stable release selected by the source URL and checksum in `packages/postgresql/build.json`. Compiler optimisation, installation paths and library search paths are implementation details governed by the distribution’s packaging requirements.

The options below use PostgreSQL 18’s `configure` build system with Make.

## Enabled options

- ICU: `--with-icu`. Schemas can define ICU collations and use them in indexes and queries.
- LZ4: `--with-lz4`. Supports table-column and WAL compression.
- Zstandard: `--with-zstd`. Supports WAL compression and compressed dumps.
- zlib: `--with-zlib`. Supports compressed archives used by `pg_dump` and `pg_restore`.
- OpenSSL: `--with-ssl=openssl`. Supplies TLS and cryptographic facilities used by `pgcrypto`.
- libxml2: `--with-libxml`. Supplies SQL/XML parsing and query operations.
- libxslt: `--with-libxslt`. Supplies XSL transformations through the `xml2` module.
- PL/pgSQL: supplied by the standard build. Supports schema functions and procedures.
- `uuid-ossp` (not supported on Windows): `--with-uuid=e2fs`. Supports schemas that use UUID functions in defaults.

Required libraries and support data are packaged and verified as described in [build-and-test.md](build-and-test.md).

## Disabled options

- Readline and libedit: `--without-readline`. Interactive command editing and history in `psql` are outside automated schema use.
- libcurl OAuth support: `--without-libcurl`. Adds connection-authentication dependencies without enabling schema operations.
- GSSAPI/Kerberos, LDAP, PAM and Bonjour: disable the applicable options for the target. These integrate authentication or service discovery with host infrastructure rather than enabling schema operations.
- NUMA and io_uring: disable `libnuma` and `liburing` support where available. These are platform-specific performance integrations; io_uring also depends on Linux kernel support.
- SELinux `sepgsql`: disable SELinux support. It requires integration with the host’s security configuration.
- PL/Perl, PL/Python and PL/Tcl: disable them explicitly with `--without-perl`, `--without-python` and `--without-tcl`. They support application-defined functions, but packaging and relocating their interpreters and support files would add work beyond the selected PL/pgSQL capability.

On macOS, the grouped disable switches are `--without-gssapi`, `--without-ldap`, `--without-pam`, `--without-bonjour`, `--without-libnuma`, `--without-liburing` and `--without-selinux`. Use the applicable switches on other targets. Optional features must not be selected by the presence of libraries on the build machine.

## Bundled SQL extensions

Build and package every PostgreSQL `contrib` SQL extension available under the selected options. This includes `fuzzystrmatch`, which TIGER Geocoder requires, and `uuid-ossp` on targets where its selected UUID support is available. PL/pgSQL is supplied by the standard build. Building the full available set keeps the recipe and extension inventory simple; each bundled extension is checked from the final PostgreSQL archive.

The PostgreSQL 18.6 macOS ARM64 and Intel archives each contain these 46 SQL extensions, including PL/pgSQL: amcheck, autoinc, bloom, btree_gin, btree_gist, citext, cube, dblink, dict_int, dict_xsyn, earthdistance, file_fdw, fuzzystrmatch, hstore, insert_username, intagg, intarray, isn, lo, ltree, moddatetime, pageinspect, pg_buffercache, pg_freespacemap, pg_logicalinspect, pg_prewarm, pg_stat_statements, pg_surgery, pg_trgm, pg_visibility, pg_walinspect, pgcrypto, pgrowlocks, pgstattuple, plpgsql, postgres_fdw, refint, seg, sslinfo, tablefunc, tcn, tsm_system_rows, tsm_system_time, unaccent, uuid-ossp and xml2. The available set is determined from the selected PostgreSQL source and build options for each target; verification compares that set with the packaged controls and exercises each extension.

## Basis for the selection

The enabled libraries supply the selected schema and database capabilities. The disabled host integrations and additional procedural languages avoid runtime dependencies outside the distribution's intended use. The current macOS recipes use these explicit options and build the available `contrib` set; Linux and Windows recipes must apply the same capability decisions with the options available on their targets.

[PostgreSQL 18 configure options](https://www.postgresql.org/docs/18/install-make.html) define the build switches. The [column-compression documentation](https://www.postgresql.org/docs/18/sql-createtable.html) and [WAL settings](https://www.postgresql.org/docs/18/runtime-config-wal.html) distinguish the compression capabilities.
