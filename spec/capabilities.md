# PostgreSQL capabilities

This document explains which optional PostgreSQL features matter to applying and inspecting schemas. The [inventory](inventory.json) records inclusion decisions; its `profiles` entries link to the sections below. Apply the [inclusion policy](functional.md#f07--capability-inclusion-follows-schema-requirements) to determine inclusion. Unresolved entries need technical evidence or a documented policy exception, rather than a separate preference decision for each feature. Version differences below cover researched PostgreSQL majors 15–18; later majors require an option audit.

Each section records the decision and reason, affected functionality, version/platform differences, dependencies and delivery, size considerations, verification and sources. Omit fields that do not apply. SQL modules activated by `CREATE EXTENSION` belong in the [extension profiles](extensions/README.md); their build dependencies are identified here where they affect core choices.

**Size considerations use existing evidence or inexpensive, labelled estimates. “Not measured” is sufficient. There is no requirement to build with and without every option. Propose a targeted experiment only when its result could change a packaging or inclusion decision, and agree that work separately.** Size notes are internal reasoning, not required download metadata. Distribution package sizes below indicate scale; they are not measurements of our archive overhead or complete dependency sets.

Verification descriptions identify the behaviour to observe. Included capabilities use the [artifact test procedure](testing/artifact.md#core-capabilities), including relocation and schema dump/restore where applicable. Tests for unresolved capabilities are conditional on selection. Exact build switches and platform mechanics belong in recipes and the [technical audit](research/postgresql-capabilities.md).

## ICU collations

**Decision:** Include (`collation.icu`), as required by F06. Schema DDL can declare ICU collations and use them in indexes and expressions.

**Dependencies and delivery:** Compile ICU support into PostgreSQL and bundle its libraries and locale data. Separately packaging a linked ICU library does not make its download optional before server startup. Locale options and catalogue fields vary by PostgreSQL major; ICU versions can change sorting results.

**Size considerations:** Not measured. Ubuntu's ICU 70 package is about 10.3 MB compressed, indicating a material dependency. [Package figures](https://packages.ubuntu.com/jammy/amd64/libicu70).

**Verification:** Create and use an ICU collation, including an index; record ICU identity and exercise version-appropriate options. [PostgreSQL collations](https://www.postgresql.org/docs/18/collation.html).

## Libc collations

**Decision:** Include (`collation.libc`), as required by F06. Schemas also use the operating system's collation provider.

**Dependencies and delivery:** Use the target OS facilities. Available locale names and sorting behaviour differ across hosts; this requirement does not promise a universal locale inventory.

**Size considerations:** No separate locale bundle is specified. Bundled non-OS runtime overhead remains platform-dependent and unmeasured.

**Verification:** Discover an available host locale, create and use its collation, and distinguish an unavailable locale from absent provider support. [PostgreSQL collations](https://www.postgresql.org/docs/18/collation.html).

## XML

**Decision:** Include (`sql.xml`) under F07 rule 1. XML values and expressions can appear in defaults, constraints, views and indexes.

**Functionality:** XML input/output, SQL/XML, XPath and `XMLTABLE`. PostgreSQL declares XML catalogue objects even without libxml2, but input and most operations then fail. Declaring an `xml` column alone is insufficient evidence.

**Dependencies and delivery:** Compile with libxml2 support and bundle non-OS dependencies. Adding libxml2 later cannot enable support compiled out of the server. The `xml2` extension is a separate selection.

**Size considerations:** Not measured; shared dependencies such as ICU and zlib must be counted only once.

**Verification:** Apply XML-bearing DDL, evaluate XML expressions and inspect restored definitions. [XML documentation](https://www.postgresql.org/docs/18/datatype-xml.html), [implementation](https://github.com/postgres/postgres/blob/REL_18_0/src/backend/utils/adt/xml.c#L16-L23).

## Zlib compression

**Decision:** Include (`compression.zlib`) under F07's existing compression scope. It supports compressed dumps and optional PGP compression in `pgcrypto`; PostgreSQL's built-in TOAST method `pglz` is independent of zlib.

**Dependencies and delivery:** Compile support into the affected tools/modules and bundle zlib where linked. PostgreSQL 15–18 support gzip-compressed plain dumps and compressed custom/directory archives. Tar-format dumps have no internal compression. Backup tools have operation-specific restrictions.

**Size considerations:** Not measured; several components may share zlib.

**Verification:** Produce compressed dumps, restore with the appropriate tool and inspect results. Test PGP compression if `pgcrypto` is selected. [PG15 dump options](https://github.com/postgres/postgres/blob/REL_15_0/doc/src/sgml/ref/pg_dump.sgml), [pgcrypto](https://www.postgresql.org/docs/18/pgcrypto.html).

## LZ4 compression

**Decision:** Include (`compression.lz4`). `COMPRESSION lz4` is part of column DDL; F07 also requires applicable tool and WAL operations.

**Dependencies and delivery:** Compile into PostgreSQL/tools and bundle the linked library. In PostgreSQL 15–18, LZ4 supports TOAST, WAL compression, base backups and `pg_receivewal`; LZ4 dump/restore begins in 16. Backup format/location restrictions still apply.

**Size considerations:** Not measured. Ubuntu's LZ4 library package is about 0.056 MB compressed. [Package figures](https://packages.ubuntu.com/jammy/amd64/liblz4-1).

**Verification:** Create a column using LZ4, observe compression on suitable data and read it back. Exercise each advertised WAL/tool operation. [TOAST](https://www.postgresql.org/docs/18/storage-toast.html), [PG16 dump options](https://github.com/postgres/postgres/blob/REL_16_0/doc/src/sgml/ref/pg_dump.sgml), [receivewal](https://www.postgresql.org/docs/18/app-pgreceivewal.html).

## Zstandard compression

**Decision:** Include (`compression.zstd`) under F07's existing compression scope.

**Dependencies and delivery:** Compile support into affected binaries and bundle the linked library. PostgreSQL 15–18 support Zstandard WAL and base-backup compression; dump/restore support begins in 16. These majors do not offer Zstandard as a TOAST method or `pg_receivewal` compression format.

**Size considerations:** Not measured. Ubuntu's Zstandard library package is about 0.316 MB compressed. [Package figures](https://packages.ubuntu.com/jammy/amd64/libzstd1).

**Verification:** Exercise applicable WAL and tool operations, checking the resulting format and restored data. Record absent upstream operations as `not_applicable`. [WAL settings](https://www.postgresql.org/docs/18/runtime-config-wal.html), [PG16 dump options](https://github.com/postgres/postgres/blob/REL_16_0/doc/src/sgml/ref/pg_dump.sgml), [basebackup](https://www.postgresql.org/docs/18/app-pgbasebackup.html).

## TLS and OpenSSL

**Decision:** Include compiled OpenSSL/TLS support (`connection.tls`) under F07 rules 1–2. OpenSSL enables `pgcrypto` functions usable in schema expressions, and upstream couples it to TLS support. Clients choose whether to activate TLS.

**Dependencies and delivery:** OpenSSL becomes a dependency of affected executables/libpq. `pgcrypto` and `sslinfo` remain independently selectable SQL modules. Foreign-server definitions can store TLS options; actually connecting needs the appropriate remote service and credentials.

**Size considerations:** Not measured. Ubuntu's combined libssl/libcrypto package is about 1.86 MB compressed; this is not a TLS-only saving estimate. [Package figures](https://packages.ubuntu.com/jammy-updates/amd64/libssl3).

**Verification:** Use a certificate-verified TLS connection and reject a wrong trust certificate. If `pgcrypto` is selected, exercise its functions with incoming TLS disabled. [TLS configuration](https://www.postgresql.org/docs/18/ssl-tcp.html), [pgcrypto requirements](https://www.postgresql.org/docs/18/pgcrypto.html).

## Timezone data

**Decision:** Include (`datetime.timezones`) as a resource required by F09. Named zones can occur in schema expressions and defaults.

**Dependencies and delivery:** Retain PostgreSQL's bundled timezone files and resolve them within the relocated installation. A builder's absolute system timezone directory would create an external dependency. Record the timezone-data version with build inputs.

**Size considerations:** Not measured. Retaining upstream data requires no size experiment.

**Verification:** Evaluate representative named-zone expressions before and after relocation, with no access to builder resources. [Date/time behaviour](https://www.postgresql.org/docs/18/datatype-datetime.html).

## GSSAPI authentication and encryption

**Decision:** Research required (`connection.gssapi`): establish which promised schema operations require it under F07. Local authentication does not require Kerberos, but foreign connections and delegated credentials make the schema boundary significant.

**Dependencies and delivery:** Core/libpq build support requires Kerberos libraries; functioning authentication also needs external credentials and services. Packaging libraries cannot provide those services.

**Size considerations:** Not measured.

**Verification if selected:** Distinguish storing foreign-server options from connecting or executing `IMPORT FOREIGN SCHEMA`; test advertised operations against a controlled service. First decide whether those remote operations belong in scope. [Foreign-server authentication](https://www.postgresql.org/docs/18/postgres-fdw.html).

## LDAP service integration

**Decision:** Research required (`connection.ldap`): establish whether promised remote schema operations require LDAP service lookup under F07. LDAP supports server authentication and libpq service lookup, which foreign connections may reference.

**Dependencies and delivery:** Compile support and bundle linked LDAP libraries if selected. Directory services and their contents remain external.

**Size considerations:** Not measured.

**Verification if selected:** Test advertised authentication or service lookup against a controlled directory. Merely storing a service name in DDL does not test lookup. [LDAP lookup](https://www.postgresql.org/docs/18/libpq-ldap.html).

## PAM and BSD authentication

**Decision:** Exclude (`connection.pam_bsd`) under F07 rule 3. These authenticate OS identities and add no schema objects needed for local schema inspection.

**Dependencies and delivery:** Platform-specific compiled support also requires host authentication configuration. Downloaded libraries cannot supply that configuration. Windows SSPI is a distinct OS facility and must be recorded separately in platform build facts.

**Size considerations:** Not measured.

**Verification:** Check the chosen build configuration. Core connection tests must work without provisioning these authentication services. [Authentication methods](https://www.postgresql.org/docs/18/client-authentication.html).

## OAuth client flow

**Decision:** Research required (`connection.oauth`): apply F07 to the remote-DDL boundary noted under GSSAPI.

**Dependencies and delivery:** PostgreSQL 18 introduces the built-in libpq OAuth flow. On supported Unix shared builds its loadable module and curl dependencies can be separate downloads. The built-in flow is unsupported on Windows. Server OAuth validator modules are separate components.

**Size considerations:** Not measured; curl's TLS dependencies may overlap existing packages.

**Verification if selected:** Exercise the flow against a controlled provider and verify module loading after relocation. PostgreSQL 15–17 lack this capability. [OAuth client flow](https://www.postgresql.org/docs/18/libpq-oauth.html).

## LLVM JIT

**Decision:** Exclude (`execution.jit`) under F07 rule 3. JIT accelerates expression evaluation without adding schema syntax or objects.

**Dependencies and delivery:** Requires a JIT-enabled build, provider, LLVM and associated bitcode. A separately downloaded provider would need tested fallback behaviour when absent.

**Size considerations:** Not measured. Ubuntu's LLVM 14 package alone is about 23.4 MB compressed, before other dependencies and PostgreSQL bitcode. [Package figures](https://packages.ubuntu.com/jammy/amd64/libllvm14).

**Verification:** Check build configuration and run the ordinary expression/DDL corpus without JIT. Inclusion would require evidence that the provider actually executes after relocation. [JIT](https://www.postgresql.org/docs/18/jit.html).

## Translated diagnostics

**Decision:** Exclude (`diagnostics.translations`) under F07 rule 3. Message translation does not implement SQL Unicode handling or collation support.

**Dependencies and delivery:** Compile gettext support and package message catalogues if selected. Catalogues could be separate only with tested fallback behaviour.

**Size considerations:** Not measured; cost depends on languages and runtime dependencies.

**Verification:** Check the selected build configuration and useful diagnostics on SQL errors. Inclusion requires testing the advertised translations after relocation. [Localization](https://www.postgresql.org/docs/18/locale.html).

## Interactive psql editing

**Decision:** Exclude optional readline/libedit support (`client.line_editing`) under F07 rule 3. Interactive `psql` remains required, including entering SQL and exiting; command history and enhanced line editing are not required schema-tool functions.

**Dependencies and delivery:** Line editing and history require tool build support. A dynamically linked editing library must be present before `psql` starts. Batch SQL and server DDL do not require editing support.

**Size considerations:** Not measured.

**Verification:** Test interactive input and exit under the consumer procedure. If editing is selected, also test history and editing; batch execution alone is insufficient. [psql editing](https://www.postgresql.org/docs/18/app-psql.html#APP-PSQL-READLINE).

## Service discovery and notification

**Decision:** Exclude Bonjour discovery and systemd readiness integration (`service.integration`) under F07 rule 3. The client starts and monitors an ordinary process using standard tools.

**Dependencies and delivery:** Platform-specific compiled support depends on OS services. It adds no schema objects.

**Size considerations:** Not measured.

**Verification:** Check build configuration and start/stop using packaged `pg_ctl` without service registration. [Server startup](https://www.postgresql.org/docs/18/server-start.html).

## io_uring

**Decision:** Exclude (`execution.io_uring`) under F07 rule 3. This PostgreSQL 18 Linux I/O option changes execution mechanics without adding schema functionality.

**Dependencies and delivery:** Requires compiled liburing support and suitable kernel permissions. Worker or synchronous I/O alternatives remain available. PostgreSQL 15–17 lack this option.

**Size considerations:** Not measured.

**Verification:** Check the chosen build/configuration and execute the DDL corpus with the supported I/O method. Inclusion would require actually exercising io_uring on claimed kernels. [I/O settings](https://www.postgresql.org/docs/18/runtime-config-resource.html#RUNTIME-CONFIG-RESOURCE-ASYNC-BEHAVIOR).

## NUMA inspection

**Decision:** Policy exception unresolved (`inspection.numa`). Its SQL function qualifies under F07 rule 1, but execution depends on OS/kernel support that cannot be supplied by a portable archive. Review the guarantee or exclusion under rule 5. PostgreSQL 18's `pg_buffercache_numa_pages()` exposes NUMA mappings and can be referenced by a view.

**Dependencies and delivery:** Working inspection requires core NUMA support, the `pg_buffercache` extension and appropriate OS/kernel behaviour. It cannot be guaranteed by bundling a library alone. The extension's other functions need their own profile.

**Size considerations:** Not measured.

**Verification if selected:** Execute the function and inspect the result on supported hosts. Confirm the documented failure on unsupported configurations rather than claiming that function presence proves working support. [Implementation](https://github.com/postgres/postgres/blob/REL_18_0/contrib/pg_buffercache/pg_buffercache_pages.c#L305-L330).
