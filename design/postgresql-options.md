# PostgreSQL build options

This document selects PostgreSQL features for creating and inspecting application schemas. The build uses the latest stable release recorded in `support.json`. Compiler optimisation, installation paths and library search paths are implementation details governed by the distribution’s packaging requirements.

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

The exact disable switches for the grouped platform-specific options are included in the implementation review below. Optional features must not be selected by the presence of libraries on the build machine.

## Draft decisions requiring implementation and human review

### Additional procedural languages

PL/Perl, PL/Python and PL/Tcl remain undecided. They support application-defined functions, but require packaging and relocating their interpreters and support files. The Spike 1 selection disabled them; it does not settle their inclusion here. Until reviewed, disable them explicitly with `--without-perl`, `--without-python` and `--without-tcl`.

### Bundled extension selection

Include `fuzzystrmatch` for TIGER Geocoder and `uuid-ossp` as specified above. The complete list of bundled SQL extensions to include and exclude still needs enumeration. The Spike 1 macOS and Linux recipes built the `contrib` directory as a whole, so they do not supply an explicit reviewed list.

### Review of the implemented options

During implementation, add an item to `HUMAN_REVIEW_QUEUE.md` with the selected PostgreSQL version, actual feature options and values for each target, the complete bundled-extension list, and any differences from this document. Check explicitly disabled options and features otherwise controlled by dependency detection. Resolve the procedural-language selection in that review and replace these draft sections with the agreed choices.

## Basis for the selection

These decisions carry forward the Spike 1 PostgreSQL options policy. Inspection of its macOS, Linux and Windows recipes confirms explicit ICU, LZ4, Zstandard, zlib, OpenSSL, libxml2 and libxslt selections and disabled Readline. The Windows recipe also explicitly disables the three additional procedural languages. The recipes do not explicitly disable every feature excluded by the policy, so the implementation review must check the resulting option set rather than copying the command lines unchanged.

[PostgreSQL 18 configure options](https://www.postgresql.org/docs/18/install-make.html) define the build switches. The [column-compression documentation](https://www.postgresql.org/docs/18/sql-createtable.html) and [WAL settings](https://www.postgresql.org/docs/18/runtime-config-wal.html) distinguish the compression capabilities.
