# PostgreSQL capabilities

The PostgreSQL archive for each selected target supplies the server and command-line tools used to create, execute and inspect application schemas. Its build options preserve schema-visible PostgreSQL features needed by those schemas and by the selected extensions. The build uses the latest stable PostgreSQL release recorded in `support.json`.

## Included capabilities

Enable ICU so schemas can define ICU collations and use them in indexes and queries. Enable LZ4 and Zstandard where the selected PostgreSQL release supports their documented compression uses. Enable zlib for compressed dumps used by `pg_dump` and `pg_restore`. Package the corresponding runtime libraries.

Enable OpenSSL for TLS, `pgcrypto` and other PostgreSQL facilities supplied by that build option. Enable libxml2 for SQL/XML, and libxslt for the `xml2` module's XSL transformations. Package their required runtime libraries and support data. Verify the resulting SQL features rather than inferring them from configure flags.

Build contrib extensions supplied by the selected PostgreSQL source when their required options are enabled, including `fuzzystrmatch` for TIGER Geocoder. On macOS, include `uuid-ossp` for schemas that use its functions in defaults. Derive the built-in SQL extension names from control files in each final PostgreSQL archive. Record that list with the build result; publication maps those SQL names to the `postgresql` package in `inventory.json`.

## Excluded capabilities

Do not enable Readline or libedit solely for interactive `psql` history. Do not add libcurl OAuth support, GSSAPI, LDAP, PAM or Bonjour integration; they add host integration or runtime dependencies without enabling the selected schema use. Do not enable PL/Perl, PL/Python or PL/Tcl because the selected extension set does not require those language runtimes. PL/pgSQL remains available. Avoid enabling optional features merely because their libraries happen to be installed in the builder.

## Build and support checks

The build targets the minimum operating-system version selected in `support.json`. On macOS, it sets a deployment target at or below that version. A feature is included only when its required runtime files can be packaged or are guaranteed by the selected operating-system version. Build scripts choose the supported option names for the selected PostgreSQL source; these capability decisions are authoritative over a particular configure or Meson flag spelling.

The implementation records the expected built-in SQL extension set from the selected PostgreSQL source and enabled capabilities independently of the packaged output. The final-archive verifier compares that expectation with packaged control files to detect missing or unexpected extensions. It checks each included capability and built-in extension as described in [the capability tests](build-and-test.md#postgresql-capabilities-and-built-in-extensions); publication checks the SQL-name mappings for the `postgresql` package against the verified result. An option that cannot meet the selected runtime and minimum-version contract is a design issue for human review before the archive is advertised.
