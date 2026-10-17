# PostgreSQL build options

These decisions apply to PostgreSQL majors 15 and later on supported platforms. They select optional PostgreSQL build features that affect schema behaviour, supported extensions, standard tools, or portability. Compiler and path options remain implementation details. The functional and testing requirements are defined in [the functional specification](../specs/functional.md) and [testing specification](../specs/testing.md).

## Include

| Feature | Decision and reason | Platform notes |
| --- | --- | --- |
| ICU (`--with-icu`, Meson `-Dicu=enabled`) | Include. Applications may define collations with ICU locales and use ICU-backed sorting and case behaviour in indexes, constraints and queries. Omitting ICU would make otherwise valid schemas fail or behave differently. | Requires ICU at runtime. Bundle the matching runtime libraries and test ICU collation creation and use on each target. |
| LZ4 (`--with-lz4`, Meson `-Dlz4=enabled`) | Include. It enables table-column compression and WAL compression, both of which affect database storage and operation. | Requires the LZ4 runtime library. PostgreSQL 15+ supports these options; verify that each advertised capability is actually present in each major. |
| Zstandard (`--with-zstd`, Meson `-Dzstd=enabled`) | Include. It enables Zstandard for WAL compression and compressed dump archives used by the supplied tools. | Requires the Zstandard runtime library. PostgreSQL 18 permits `pglz` and `lz4`, but not Zstandard, for table-column compression. |
| zlib (`--with-zlib`, Meson `-Dzlib=enabled`) | Include. `pg_dump` and `pg_restore` use zlib for compressed archives; these are required standard tools. | PostgreSQL enables zlib by default when available in the Autoconf build. Make it explicit in Meson builds so the tool capability does not depend on autodetection. |
| OpenSSL (`--with-ssl=openssl`, Meson `-Dssl=openssl`) | Include. TLS connections are a common PostgreSQL deployment requirement and OpenSSL is also used by supported PostgreSQL functionality such as `pgcrypto`. Keeping this standard feature avoids making the distribution unsuitable for secure client connections or extension builds. | OpenSSL is a runtime dependency and must be bundled with its redistribution notices. Windows and macOS builds must use the same feature decision even though their dependency packaging differs. |
| libxml2 (`--with-libxml`, Meson `-Dlibxml=enabled`) | Include. It provides the SQL/XML implementation and the `xml` type's parsing and query operations. Those types and functions can appear in application schemas. | Bundle the runtime library and its transitive dependencies. |
| libxslt (`--with-libxslt`, Meson `-Dlibxslt=enabled`) | Include. It extends PostgreSQL's `xml2` module with XSL transformations, a schema-visible function set, at low incremental cost once libxml2 is present. | Requires libxml2 and libxslt. |

## Platform-limited option

Build `uuid-ossp` on Linux and macOS with the upstream-supported e2fs UUID library because applications can use its functions in schema defaults. Omit it on Windows: PostgreSQL's native Windows build requires OSSP UUID, and the available Windows port would require this project to maintain changes to that dependency, contrary to [the upstream-only requirement](../specs/functional.md#never-patch-or-modify-extensions-or-dependencies). PostgreSQL's core UUID type and generators remain available on Windows. Derive the built-in extension list for each archive from its actual controls; no Windows inventory entry may claim `uuid-ossp` unless a maintained, unmodified upstream dependency and build path are established and verified. [PostgreSQL's Windows build notes](https://www.postgresql.org/docs/18/installation-platform-notes.html) identify the OSSP requirement; [its extension documentation](https://www.postgresql.org/docs/18/uuid-ossp.html) describes the library's maintenance and portability limits.

## Exclude

| Feature | Decision and reason | Platform notes |
| --- | --- | --- |
| Readline or libedit (`--with-readline`, Meson `-Dreadline`) | Exclude. It adds interactive command editing and history to `psql`, but does not affect SQL execution, schema creation or inspection, and the standard tool remains usable without it. Avoid an extra runtime dependency and differing license choices. | Linux and macOS use `--without-readline`; Windows selects `-Dreadline=disabled`. |
| libcurl (`--with-libcurl`) | Exclude. It adds libcurl support for OAuth client flows, a connection-authentication feature rather than schema functionality or a required standard-tool capability. The added runtime dependency is not justified by the current supported use case. | Available in PostgreSQL 18's build system; confirm option availability before applying this decision to any earlier supported major. |
| GSSAPI/Kerberos, LDAP, PAM and Bonjour support | Exclude. These options integrate server authentication or service discovery with host infrastructure. They require platform-specific libraries or operating-system configuration and do not enable schema operations. | Availability and names vary by platform and build system. Do not enable implicitly through builder dependencies. |
| NUMA and io_uring (`--with-libnuma`, `--with-liburing`) | Exclude. These are host-specific runtime performance integrations, not schema capabilities; io_uring also varies with Linux kernel support. | Linux-only or platform-limited. |
| PL/Perl, PL/Python and PL/Tcl | Exclude. They add language runtimes and runtime dependencies. No currently supported extension or required schema feature needs them; users can define SQL and PL/pgSQL routines with the standard build. | Ensure optional language support is not enabled by incidental builder packages. |
| SELinux `sepgsql` | Exclude. It requires SELinux-specific server integration and is not part of the supported extension set. | Requires SELinux support in both build and host environment. |

## Version and implementation limits

PostgreSQL's configure options and Meson option names evolve. The decisions above describe capabilities, not a promise that an identical switch exists in every major. Build scripts must use the option supported by each major's source and verify the resulting capability. PostgreSQL 15 is the minimum supported major; PostgreSQL 18 documentation is the current source for Meson option names and newer facilities.

The current pilot scripts request ICU, LZ4, Zstandard, OpenSSL, libxml2, libxslt and zlib on all three operating systems. All three explicitly disable readline. The Windows Meson build also explicitly disables PL/Perl, PL/Python and PL/Tcl; an earlier pilot archive inherited PL/Perl and PL/Python from its runner because Meson defaults those options to `auto`. Linux and macOS select e2fs UUID support; Windows deliberately selects none under the platform-limited decision above. Linux and macOS have native arm64 pilot results.

## Sources

- [PostgreSQL 18 source installation and configure options](https://www.postgresql.org/docs/18/install-make.html) describes optional features, defaults, anti-features and their effects.
- [PostgreSQL 18 build requirements](https://www.postgresql.org/docs/18/install-requirements.html) describes Readline's role in `psql` and optional library requirements.
- [PostgreSQL 18 XML type](https://www.postgresql.org/docs/18/datatype-xml.html) states that the XML type requires a build with libxml2.
- [PostgreSQL 18 `CREATE TABLE`](https://www.postgresql.org/docs/18/sql-createtable.html) lists the supported column-compression methods.
- [PostgreSQL 18 WAL settings](https://www.postgresql.org/docs/18/runtime-config-wal.html) lists Zstandard as a conditional WAL-compression method.
- [PostgreSQL 18 platform notes](https://www.postgresql.org/docs/18/installation-platform-notes.html) documents dependencies including OpenSSL, libxml2/libxslt, LZ4, Zstandard and zlib on Windows.
- [PostgreSQL 15 source installation](https://www.postgresql.org/docs/15/install-procedure.html) is the baseline-major reference; consult the matching major's build documentation when translating decisions into flags.
