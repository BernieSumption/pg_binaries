# Extension support

Extension release selection follows the [functional specification's shared version support rule](../specs/functional.md#determining-postgres-and-extension-versions-to-support). The versions currently pinned in `support.json` are from a previous selection and remain pending refresh under that rule; this policy does not treat those pins as current release findings. Refresh the metadata, builders and tests through [the migration backlog](../GOAL_BACKLOG.md#version-policy-migration).

## Built-in extensions

Upstream: [PostgreSQL](https://www.postgresql.org/). We support the extensions bundled with each selected PostgreSQL build. The inventory must derive the actual list from build output; optional build dependencies can make that list differ by platform. In particular, the [PostgreSQL option policy](postgres-options.md#platform-limited-option) omits `uuid-ossp` on Windows.

The October 2026 research identified these names across PostgreSQL 15–18; they are not all present in every major, and are present here only for reference to identify built-in extensions easily. The authoritative source for whether an extension is built-in to a given version is inventory.json:

`adminpack`, `amcheck`, `autoinc`, `bloom`, `bool_plperl`, `bool_plperlu`, `btree_gin`, `btree_gist`, `citext`, `cube`, `dblink`, `dict_int`, `dict_xsyn`, `earthdistance`, `file_fdw`, `fuzzystrmatch`, `hstore`, `hstore_plperl`, `hstore_plperlu`, `hstore_plpython3u`, `insert_username`, `intagg`, `intarray`, `isn`, `jsonb_plperl`, `jsonb_plperlu`, `jsonb_plpython3u`, `lo`, `ltree`, `ltree_plpython3u`, `moddatetime`, `old_snapshot`, `pageinspect`, `pg_buffercache`, `pg_freespacemap`, `pg_logicalinspect`, `pg_prewarm`, `pg_stat_statements`, `pg_surgery`, `pg_trgm`, `pg_visibility`, `pg_walinspect`, `pgcrypto`, `pgrowlocks`, `pgstattuple`, `plperl`, `plperlu`, `plpgsql`, `plpython3u`, `pltcl`, `pltclu`, `postgres_fdw`, `refint`, `seg`, `sslinfo`, `tablefunc`, `tcn`, `tsm_system_rows`, `tsm_system_time`, `unaccent`, `uuid-ossp`, `xml2`.

## pgvector — include

Description: [pgvector](https://github.com/pgvector/pgvector) adds vector types, distance operations and indexes. Its SQL extension name is `vector`.

For inclusion: It is maintained, widely adopted and offered by several major PostgreSQL hosts. Vector columns and indexes occur directly in application DDL. The upstream PostgreSQL Licence permits redistribution.

Against inclusion: Native code must be built and checked against each claimed PostgreSQL and platform range. No external runtime data or service is required.

Version policy: Apply the shared version support rule to compatible pgvector releases.

Target support: PostgreSQL 15 and later on Linux and macOS for x86-64 and arm64, and Windows for x86-64, subject to upstream's documented PostgreSQL support and verified archive results. Upstream currently documents PostgreSQL 13+ and Linux, macOS and Windows build procedures; its Windows instructions cover x64.

Sources: [upstream build and usage guide](https://github.com/pgvector/pgvector), [changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md), [licence](https://github.com/pgvector/pgvector/blob/master/LICENSE), [Supabase extension catalogue](https://supabase.com/docs/guides/database/extensions), [Neon extension catalogue](https://neon.com/docs/extensions/pg-extensions).

## PostGIS — include

Description: [PostGIS](https://postgis.net/) adds spatial types, indexes and functions. Its SQL extension names are `postgis`, `postgis_raster`, `postgis_sfcgal` and `postgis_topology`. `postgis_legacy` is a compatibility SQL script, not an extension selected with `CREATE EXTENSION`.

For inclusion: PostGIS is mature, maintained and offered by major PostgreSQL hosts. Spatial columns, indexes, constraints and functions are used directly in application schemas. Include all four PostGIS SQL extensions at the project level, including SFCGAL.

Against inclusion: GEOS, PROJ and LibXML2 add native dependencies; raster support adds GDAL, and SFCGAL adds a substantial C++ dependency stack. Required runtime libraries and redistributable coordinate-system data must be bundled with their licences and source obligations. The Linux pilot packages the selected SQL modules and their runtime closure; it omits upstream's optional import, export and administration programs because the specified schema operations do not require them and their host interpreters or C library would break the kernel-only support claim. This pilot does not establish all-platform portability or complete redistribution evidence.

Version policy: Apply the shared version support rule to releases compatible with each PostgreSQL version. Use upstream PostgreSQL compatibility information to select the release for each core.

Target support: On the five required OS and architecture targets, aim to support PostgreSQL versions within each line's documented compatibility. Upstream's current compatibility data describes PostgreSQL 12–17 for 3.4 and 12–18 for 3.5 and 3.6; intersect those ranges with this repository's PostgreSQL 15+ requirement. A selected release/core combination missing on a required platform remains unmet; a build failure alone does not remove that target. The archive exposes all four PostGIS SQL names declared in `support.json`. [Address Standardizer](https://github.com/postgis/address_standardizer) and [PostGIS TIGER Geocoder](https://gitea.osgeo.org/postgis/postgis_tiger_geocoder) have separate upstream projects and inclusion decisions; their files may occur in a PostGIS source build but this PostGIS decision does not include them. Verify the selected PostgreSQL combinations and native dependency closure before advertising any archive.

Sources: [PostGIS compatibility data](https://www.postgis.net/development/compatibility/), [versioning and maintenance policy](https://postgis.net/development/versions_eol/), [installation guide](https://postgis.net/docs/manual-3.6/en/postgis_installation.html), [licensing inventory](https://github.com/postgis/postgis/blob/master/LICENSE.TXT), [Google Cloud SQL extension catalogue](https://docs.cloud.google.com/sql/docs/postgres/extensions).

## PostGIS TIGER Geocoder — include

Description: [PostGIS TIGER Geocoder](https://postgis.net/2026/08/PostGIS-Tiger-Geocoder-2025.2/) provides address normalization, geocoding, reverse geocoding and Census-data loader functions. Its SQL extension name is `postgis_tiger_geocoder`.

For inclusion: Schema DDL can use its functions and the `tiger` schema. `CREATE EXTENSION` installs the schema and empty reference tables without downloading Census data; the loader downloads data only when a user chooses to populate them. The separately released extension is PL/pgSQL-only, so its SQL files can be tested across the required OS and architecture targets without a native build for each target.

Against inclusion: Actual geocoding needs US Census TIGER data loaded by the user. The archive must not bundle that dataset or claim to geocode addresses before loading it. The extension requires PostGIS and the built-in `fuzzystrmatch`; GPLv2 redistribution requires its licence and an appropriate source link or offer in the archive. SQL-only packaging still needs installation and DDL tests in the environments required by [the testing policy](testing.md).

Version policy: Apply the shared version support rule to compatible releases. Treat upstream data-year majors according to the shared two-year rule; verify the selected package with its declared PostgreSQL and PostGIS prerequisites.

Target support: PostgreSQL 16–18 on Linux and macOS x86-64 and arm64 and Windows x86-64, with PostGIS 3.6 or later and `fuzzystrmatch` installed. The 2025.2 release declares PostgreSQL 16+ and PostGIS 3.6+; PostgreSQL 15 is outside its declared range. This is intended support, not verified archive coverage.

Sources: [2025.2 announcement](https://postgis.net/2026/08/PostGIS-Tiger-Geocoder-2025.2/), [upstream 2025.2 source archive](https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz) (`README.md`, `META.json` and `COPYING`), [PostGIS installation guide](https://postgis.net/docs/postgis_installation.html).

## Address Standardizer — support selection pending

Description: [Address Standardizer](https://github.com/postgis/address_standardizer) provides address parsing and rule-based standardization. Its SQL extension names are `address_standardizer` and `address_standardizer_data_us`.

For inclusion: Its parsing functions can appear in schema DDL, and major PostgreSQL hosts offer both SQL extensions. The upstream repository contains the USPS-derived city file used to generate `parseaddress-stcities.h` and states an MIT-style licence in `COPYING`. No separate terms were identified for that US file. Under the [repository-data licence assumption](releases.md#redistribution-review-before-publication), the city file and compiled output use the repository licence; do not investigate whether upstream had authority to license the earlier USPS source.

Against inclusion: The native library needs PCRE2, which must be bundled on platforms where it is not universal. Upstream moved the project out of PostGIS after the 3.6 line, so release selection, documented PostgreSQL support and platform builds need research before intended support can be declared. Any newer data file with explicit separate terms needs its own review.

Version policy: Apply the shared version support rule after establishing how the bundled and standalone releases map to this project. A source-repository split does not by itself require retaining both packages.

Target support: Not yet declared in `support.json`. Research each selected release's PostgreSQL and OS support, then add both SQL names at the project level for the supported targets. The resolved US-data assumption alone is not build, compatibility or publication evidence.

Sources: [upstream project and data-generation description](https://github.com/postgis/address_standardizer), [repository licence](https://github.com/postgis/address_standardizer/blob/main/COPYING), [PostGIS 3.6 build rules](https://github.com/postgis/postgis/blob/stable-3.6/extensions/address_standardizer/Makefile.in), [PostGIS installation guide](https://postgis.net/docs/postgis_installation.html).

## oracle_fdw — exclude

Description: [oracle_fdw](https://github.com/laurenz/oracle_fdw) exposes Oracle tables through PostgreSQL foreign tables. Its SQL extension name is `oracle_fdw`.

For inclusion: The project is maintained and offered by major PostgreSQL hosts. Foreign tables can occur in schema DDL.

Against inclusion: The upstream build and runtime requirements include Oracle client libraries. Oracle's Instant Client distribution terms require an executed licence agreement and end-user records for each recipient. That process is incompatible with this project's anonymous public downloads and common copy installation. No alternative redistributable client has been established. The required runtime dependency therefore cannot currently be bundled under the functional specification.

Version policy: None while excluded. Reconsider only if a client-library path compatible with anonymous public downloads is established.

Target support: None while excluded.

Sources: [upstream requirements](https://github.com/laurenz/oracle_fdw/blob/master/README.oracle_fdw), [Oracle Instant Client distribution terms](https://www.oracle.com/downloads/licenses/instant-client-lic.html), [Azure extension catalogue](https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-versions).

## aws_commons — exclude

Description: [aws_commons](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL-Lambda.html) supplies helper composite values and functions used by AWS PostgreSQL integrations; its SQL extension name is `aws_commons`.

For inclusion: It is listed by Amazon RDS, and AWS documents it as a dependency of `aws_lambda` and as a helper for S3 operations.

Against inclusion: The documented role is to construct AWS-specific values consumed by other AWS extensions, rather than provide standalone PostgreSQL functionality. The reviewed provider documentation describes installation in RDS but does not provide source, a redistribution licence, or a build path for independent distributions. This makes cross-platform support cost and feasibility unclear.

Version policy: No independently distributable upstream release line was identified; exclude pending evidence of source and redistribution rights.

Target support: None while excluded. AWS documents the extension as part of RDS for PostgreSQL.

Sources: [AWS Lambda extension installation and aws_commons dependency](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL-Lambda.html), [AWS S3 function reference](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PostgreSQL.S3Import.Reference.html), [RDS extension catalogue](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html).

## aws_lambda — exclude

Description: [aws_lambda](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL-Lambda.html) lets SQL invoke AWS Lambda functions. Its SQL extension name is `aws_lambda`.

For inclusion: Amazon RDS supports it, and calling serverless functions from SQL is a useful integration for AWS-backed applications.

Against inclusion: Its purpose depends on AWS Lambda and AWS IAM configuration on an RDS instance. The reviewed provider documentation gives the managed-service procedure but no source, redistribution licence, or independent build instructions. It therefore has little portable utility and lacks an established buildable upstream for this project.

Version policy: No independently distributable upstream release line was identified; exclude pending evidence of source and redistribution rights.

Target support: None while excluded. AWS documents it for RDS for PostgreSQL.

Sources: [AWS procedure and IAM requirements](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL-Lambda.html), [RDS extension catalogue](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html).

## aws_s3 — exclude

Description: [aws_s3](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PostgreSQL.S3Import.html) provides SQL functions to import data from Amazon S3 into RDS for PostgreSQL. Its SQL extension name is `aws_s3`.

For inclusion: Amazon RDS supports it and documents S3 data import, a useful integration for AWS applications.

Against inclusion: The documented function operates with Amazon S3 and RDS identity/permissions. AWS's instructions are specific to RDS, and the reviewed materials provide no source, redistribution licence, or independent build route. That leaves no supported basis for building a portable distribution.

Version policy: No independently distributable upstream release line was identified; exclude pending evidence of source and redistribution rights.

Target support: None while excluded. AWS documents the feature for RDS for PostgreSQL 10.7 and later; that service compatibility does not establish compatibility for our artifacts.

Sources: [AWS S3 import and service requirements](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PostgreSQL.S3Import.html), [AWS function reference](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PostgreSQL.S3Import.Reference.html), [RDS extension catalogue](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html).

## azure_ai — exclude

Description: [azure_ai](https://learn.microsoft.com/en-us/azure/postgresql/azure-ai/generative-ai-azure-overview) adds SQL functions for calling Azure AI, Azure OpenAI, Cognitive Services and Azure Machine Learning. Its SQL extension name is `azure_ai`.

For inclusion: Microsoft lists it for Azure Database for PostgreSQL and documents AI inference and embedding use cases.

Against inclusion: The extension is designed to call Azure-hosted services and requires endpoint and authentication configuration. The reviewed provider documentation provides deployment guidance but no source, redistribution licence, or build instructions for an independently maintained distribution. Its preview AI functions also signal a changing interface.

Version policy: No independently distributable upstream release line was identified; exclude pending evidence of source and redistribution rights and a stable production interface.

Target support: None while excluded. Azure's catalogue lists it for its managed PostgreSQL service; that does not establish cross-OS or independent PostgreSQL compatibility.

Sources: [Microsoft overview, configuration and preview capabilities](https://learn.microsoft.com/en-us/azure/postgresql/azure-ai/generative-ai-azure-overview), [Azure extension version catalogue](https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-by-engine).

## azure_storage — exclude

Description: [azure_storage](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-storage-extension) moves data between PostgreSQL and Azure Storage using SQL and COPY-related functions. Its SQL extension name is `azure_storage`.

For inclusion: Microsoft offers it for Azure Database for PostgreSQL, with blob import/export functions and several supported file formats.

Against inclusion: It is tied to Azure Storage authentication, network access and Azure-managed identity or keys. Microsoft documents allowlisting and service-specific configuration, but the reviewed sources do not provide extension source, redistribution terms, or an independent build route. The service integration has little value without Azure Storage.

Version policy: No independently distributable upstream release line was identified; exclude pending evidence of source and redistribution rights.

Target support: None while excluded. Azure documents versions for Flexible Server and requires its server library to be enabled; those facts do not establish portability to our targets.

Sources: [Microsoft feature and authentication overview](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-storage-extension), [Azure extension version catalogue](https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-by-engine), [Microsoft troubleshooting and required storage permissions](https://learn.microsoft.com/en-us/azure/postgresql/troubleshoot/troubleshoot-azure-storage-extension).

## google_ml_integration — exclude

Description: [google_ml_integration](https://cloud.google.com/sql/docs/postgres/integrate-cloud-sql-with-vertex-ai) provides SQL functions to call Vertex AI and other model endpoints from Cloud SQL for PostgreSQL. Its SQL extension name is `google_ml_integration`.

For inclusion: Google Cloud supports it, and SQL-accessible model predictions and embeddings are useful for applications that use Google Cloud AI.

Against inclusion: The documented implementation requires Cloud SQL instance integration flags and Google service identity or Secret Manager configuration. The reviewed Google documentation describes only the managed-service implementation and does not provide extension source, redistribution terms, or an independent build route. Model endpoint management features are explicitly marked Preview.

Version policy: No independently distributable upstream release line was identified; exclude pending evidence of source and redistribution rights and stable production status.

Target support: None while excluded. Google documents Cloud SQL support for PostgreSQL 12 and later; those managed-service limits do not establish independent OS or PostgreSQL compatibility.

Sources: [Google Cloud setup and instance requirements](https://cloud.google.com/sql/docs/postgres/integrate-cloud-sql-with-vertex-ai), [extension catalogue and supported version](https://cloud.google.com/sql/docs/postgres/extensions), [preview model endpoint management](https://cloud.google.com/sql/docs/postgres/model-endpoint-overview).

## google_read_only_session — exclude

Description: [google_read_only_session](https://cloud.google.com/sql/docs/postgres/read-only-sessions) applies predefined security labels to functions allowed in Cloud SQL read-only sessions. Its SQL extension name is `google_read_only_session`.

For inclusion: It supports a useful database security mode, and Google Cloud documents its use with Cloud SQL read-only sessions.

Against inclusion: The extension depends on Cloud SQL's `cloudsql_session_read_only` behavior and associated security-label handling. Its documented use is specific to Cloud SQL, and the reviewed provider documentation provides no source, redistribution terms, or independent build route. The underlying capability is therefore not established as portable to ordinary PostgreSQL installations.

Version policy: No independently distributable upstream release line was identified; exclude pending source, redistribution and compatibility evidence.

Target support: None while excluded. Google documents use only with Cloud SQL for PostgreSQL; no broader PostgreSQL or OS support is claimed.

Sources: [Google Cloud read-only session behavior and extension instructions](https://cloud.google.com/sql/docs/postgres/read-only-sessions), [Cloud SQL extension catalogue](https://cloud.google.com/sql/docs/postgres/extensions).

## HypoPG — include

Description: [HypoPG](https://github.com/HypoPG/hypopg) lets PostgreSQL's planner evaluate hypothetical indexes without creating physical indexes. Its SQL extension name is `hypopg`.

For inclusion: It is a mature query-tuning tool offered by Supabase and Crunchy Bridge. Upstream documents PostgreSQL 9.2 and later, and Crunchy lists it for PostgreSQL 13–18.

Against inclusion: None identified. Hypothetical indexes are session-local and do not store persistent table data. The 1.4.3 source archive contains SQL upgrade scripts from 1.3.1 through 1.4.3, although its README still recommends dropping and recreating the extension and says it has no upgrade scripts. Test an upgrade path before promising one; this project's selected support currently includes only 1.4.3.

Version policy: Apply the shared version support rule to compatible releases.

Target support: PostgreSQL 15 and later stable releases, currently 15–18. Build and test each supported project platform and architecture before claiming verified coverage. Reassess compatibility when a new PostgreSQL major becomes stable.

Sources: [upstream releases and compatibility notes](https://github.com/HypoPG/hypopg/releases), [upstream installation notes](https://github.com/HypoPG/hypopg), [Crunchy extension compatibility](https://access.crunchydata.com/documentation/postgres-operator/latest/references/components), [Crunchy Bridge extension list](https://docs.crunchybridge.com/extensions-and-languages), [Supabase HypoPG guide](https://supabase.com/docs/guides/database/extensions/hypopg).

## collection — include

Description: [pgcollection](https://github.com/aws/pgcollection) provides associative-array types for PL/pgSQL. Its SQL extension name is `collection`.

For inclusion: It supports Oracle PL/SQL associative-array migration. AWS maintains public source under Apache-2.0, and upstream documents PostgreSQL 14 and later.

Against inclusion: Adoption evidence is limited beyond AWS RDS. The extension is a native C build, with no external runtime or data-file dependency identified.

Version policy: Select 2.1.3 and 1.1.1 for each compatible PostgreSQL build under the shared rule. PGXN dates major 1 to 2025-04-03 and major 2 to 2026-03-20; both fall within the two-year window as of 2026-10-17. Refresh those selections when the inventory is next prepared.

Target support: PostgreSQL 15 and later stable releases, currently 15–18. Build and test each supported project platform and architecture before claiming verified coverage; upstream does not specify OS or architecture guarantees. Reassess compatibility when a new PostgreSQL major becomes stable.

Sources: [upstream source, PostgreSQL requirement and license](https://github.com/aws/pgcollection), [release history](https://github.com/aws/pgcollection/releases), [PGXN 1.0.0 and 2.0.0 release dates](https://pgxn.org/dist/pgcollection/1.0.0/), [AWS RDS extension catalogue](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html).

## pg_background — exclude

Description: [pg_background](https://github.com/vibhorkum/pg_background) runs SQL asynchronously in PostgreSQL background worker processes. Its SQL extension name is `pg_background`.

For inclusion: It supports independent transactions and asynchronous SQL execution from server-side code.

Against inclusion: Background execution is an operational capability for application code, not a feature required to define or inspect schema objects. PostgreSQL already exposes its background worker API to extensions. Its latest 2.0 release also changes the SQL API and removes pre-1.8 upgrade support, adding version-specific migration considerations without meeting a required schema use case.

Version policy: Exclude. Reassess if a schema-level requirement depends on this extension.

Target support: None while excluded. Upstream reports PostgreSQL 14–18 fully tested and PostgreSQL 19 beta validated.

Sources: [upstream project, PostgreSQL compatibility and license](https://github.com/vibhorkum/pg_background), [release history and 2.0 migration notes](https://github.com/vibhorkum/pg_background/releases).

## pg_cron — include

Description: [pg_cron](https://github.com/citusdata/pg_cron) runs scheduled SQL jobs inside PostgreSQL as a background worker. Its SQL extension name is `pg_cron`.

For inclusion: It is maintained by Citus, widely deployed and offered by AWS, Azure, Google Cloud, Neon and Supabase. It is PostgreSQL-licensed and has no separate runtime dependency.

Against inclusion: It requires `shared_preload_libraries = 'pg_cron'`, a restart and `CREATE EXTENSION`. By default, job execution opens local libpq connections that must be permitted by `pg_hba.conf`; document these configuration requirements. Upstream provides Windows build instructions, but all target platforms and architectures require verification.

Version policy: Apply the shared version support rule to compatible releases. Upstream supports PostgreSQL 10 and later; the release history documents PostgreSQL 18 support.

Target support: PostgreSQL 15 and later stable releases, currently 15–18. Build and test each supported project platform and architecture before claiming verified coverage. Reassess compatibility when a new PostgreSQL major becomes stable. The extension can be installed in only one database per cluster.

Sources: [upstream README, requirements and provider list](https://github.com/citusdata/pg_cron), [release history and PostgreSQL compatibility](https://github.com/citusdata/pg_cron/releases), [Supabase extension catalogue](https://github.com/supabase/postgres).

## pg_duckdb — exclude

Description: [pg_duckdb](https://github.com/duckdb/pg_duckdb) integrates DuckDB's query engine with PostgreSQL and supports analytics and data-lake access. Its SQL extension name is `pg_duckdb`.

For inclusion: It can run analytical queries over PostgreSQL tables and query external Parquet, CSV, JSON and lakehouse data.

Against inclusion: These are query execution and data-lake capabilities, not requirements for defining or inspecting PostgreSQL schemas. The project would also need to redistribute DuckDB and support community DuckDB extensions and cloud integrations. Upstream currently documents Ubuntu and macOS only, which does not establish the required platform matrix.

Version policy: Exclude while the project has no required analytics or data-lake use case.

Target support: None while excluded. Upstream lists PostgreSQL 14–18 and Ubuntu 22.04–24.04 and macOS.

Sources: [upstream project, supported systems and license](https://github.com/duckdb/pg_duckdb), [upstream releases](https://github.com/duckdb/pg_duckdb/releases).

## pg_hint_plan — exclude

Description: [pg_hint_plan](https://github.com/ossc-db/pg_hint_plan) lets SQL comments or a hint table direct PostgreSQL's query planner. Its SQL extension name is `pg_hint_plan`.

For inclusion: It provides query plan control through SQL comments and stored hints.

Against inclusion: Planner tuning affects query execution plans, not schema creation or inspection. Its supported release is PostgreSQL-major-specific and requires its own build for every supported major, without serving a functional requirement in this project.

Version policy: Exclude while planner control is outside the project use case.

Target support: None while excluded. Upstream publishes separate lines for individual PostgreSQL majors; release 1.8.0 supports PostgreSQL 18 only.

Sources: [upstream project and hint features](https://github.com/ossc-db/pg_hint_plan), [release history and PostgreSQL-major-specific releases](https://github.com/ossc-db/pg_hint_plan/releases).

## pg_ivm — include

Description: [pg_ivm](https://github.com/sraoss/pg_ivm) adds incremental maintenance for materialized views, applying changes from base tables without recomputing the full view. Its SQL extension name is `pg_ivm`.

For inclusion: Materialized views are schema objects used by applications, and incremental maintenance changes their behavior when base tables change. Supporting their definitions and use falls within the project's schema functionality. Upstream is maintained, PostgreSQL-licensed and documents PostgreSQL 13–19 support.

Against inclusion: The extension must be loaded through `shared_preload_libraries` or `session_preload_libraries` for correct maintenance. This requires documenting basic PostgreSQL configuration and a restart when using shared preload. Version 1.15 added a utility for restoring view-maintenance metadata after `pg_dump` or `pg_upgrade`; packaging must include it. Its native code and platform coverage require build verification.

Version policy: Apply the shared version support rule to compatible releases.

Target support: PostgreSQL 15–18 initially, intersecting upstream's declared 13–19 range with the project's stable targets. Build and test all required OS and architecture targets before claiming coverage.

Sources: [upstream description, compatibility and configuration](https://github.com/sraoss/pg_ivm), [release history and 1.16 fixes](https://github.com/sraoss/pg_ivm/releases), [upstream license](https://github.com/sraoss/pg_ivm/blob/main/LICENSE).

## pgaudit — include

Description: [pgAudit](https://github.com/pgaudit/pgaudit) adds session and object audit logging through the `pgaudit` SQL extension and PostgreSQL's normal logs.

For inclusion: It is maintained, offered by Amazon RDS and Google Cloud SQL, and provides application and compliance audit records. Its PostgreSQL License allows redistribution, and it has no external runtime data.

Against inclusion: It requires `shared_preload_libraries` and a restart; full DDL audit detail also depends on creating the SQL extension before setting its log classes. Logging is best-effort rather than transactional. Upstream describes builds for most Unix-like systems and does not document native Windows support. The preload and log behavior must be represented in package metadata and tests.

Version policy: Apply the shared version support rule using the upstream branch mapped to each PostgreSQL major. Upstream maintains separate stable branches for server majors; select compatible releases from those branches.

Target support: PostgreSQL 15–18 on Linux and macOS, x86-64 and arm64, with each pgAudit line restricted to its matching PostgreSQL major. Both architectures require build and test evidence. No Windows target is declared without documented support or a demonstrated port.

Sources: [upstream compatibility, build and preload guidance](https://github.com/pgaudit/pgaudit#postgresql-version-compatibility), [release history](https://github.com/pgaudit/pgaudit/releases), [licence](https://github.com/pgaudit/pgaudit/blob/main/LICENSE), [logging caveats](https://github.com/pgaudit/pgaudit#caveats), [Amazon RDS guide](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.pgaudit.html), [Google Cloud SQL catalogue](https://docs.cloud.google.com/sql/docs/postgres/extensions).

## pgtap — include

Description: [pgTAP](https://github.com/theory/pgtap) adds database assertion functions for testing SQL schemas and migrations. Its SQL extension names are `pgtap`, `pgtap-core` and `pgtap-schema`.

For inclusion: Database-level tests are a common application development need. The project is maintained and available in Debian packages. Its installed functions use SQL and PL/pgSQL, so they add no independent native library or architecture-specific runtime. The PostgreSQL License permits redistribution.

Against inclusion: The upstream source build uses Perl to generate installation SQL, and the optional `pg_prove` harness has a separate Perl dependency. Neither is required to execute the installed SQL functions. Packaging must keep all three SQL extension identities and their upgrade files consistent; each requires a representative schema test.

Version policy: Apply the shared version support rule to published compatible releases; exclude unreleased changelog entries.

Target support: PostgreSQL 15–18 on Linux and macOS for x86-64 and arm64, and Windows for x86-64. Upstream reports testing through PostgreSQL 18. The installed SQL payload is architecture-independent, but archive assembly and behavior still require checks on each target before publication.

Sources: [PGXN release and metadata](https://pgxn.org/dist/pgtap/), [1.3.4 source, release notes and compatibility](https://api.pgxn.org/src/pgtap/pgtap-1.3.4/), [upstream build and release process](https://github.com/theory/pgtap), [Debian package](https://packages.debian.org/sid/source/pgtap).

## pg_jsonschema — include

Description: [pg_jsonschema](https://github.com/supabase/pg_jsonschema) validates `json` and `jsonb` against JSON Schema through SQL functions. Its SQL extension name is `pg_jsonschema`.

For inclusion: Applications can use its functions in CHECK constraints to enforce JSON document shapes. Supabase maintains and offers it, and upstream publishes PostgreSQL 18 and Linux arm64 builds. Its Apache-2.0 licence permits redistribution with applicable notices.

Against inclusion: The Rust/pgrx toolchain adds native build and dependency cost for each PostgreSQL major. Upstream's release workflow builds Linux packages; the source uses pgrx 0.16.1, whose documentation lists tested Linux x86-64/arm64, macOS arm64 and Windows x86-64 targets. macOS x86-64 is not listed as tested, so it needs an early source-build feasibility check. No external data or service is required for schema use.

Version policy: Apply the shared version support rule to published compatible releases.

Target support: PostgreSQL 15–18 on all five project platforms. The Linux-only upstream release workflow does not declare source incompatibility elsewhere; none was identified in the selected source. All combinations remain intended, not verified. If an upstream source limitation prevents a target build, document the evidence and narrow its support rather than patching the dependency.

Sources: [upstream releases](https://github.com/supabase/pg_jsonschema/releases), [0.3.4 source and release workflow](https://github.com/supabase/pg_jsonschema/tree/v0.3.4), [0.3.4 Cargo features and pgrx dependency](https://raw.githubusercontent.com/supabase/pg_jsonschema/v0.3.4/Cargo.toml), [pgrx 0.16.1 platform guidance](https://raw.githubusercontent.com/pgcentralfoundation/pgrx/v0.16.1/README.md), [Supabase documentation](https://supabase.com/docs/guides/database/extensions/pg_jsonschema), [licence](https://github.com/supabase/pg_jsonschema/blob/master/LICENSE).

## lakebase_text — exclude

Description: [lakebase_text](https://docs.databricks.com/aws/en/oltp/projects/lakebase-text) adds BM25 ranking and the `lakebase_bm25` index access method; its SQL extension name is `lakebase_text`.

For inclusion: Databricks supports it in Lakebase Search alongside its tokenizer and vector extensions. It provides BM25 ranking, compatible with PostgreSQL `tsvector` and query operators, and offers a useful full-text search capability.

Against inclusion: The current primary material reviewed describes enabling and installing it only in Databricks Lakebase. It identifies no source repository, independent release artifacts, license or redistribution terms, or build route. This is missing evidence, not evidence that redistribution is legally prohibited. Standard PostgreSQL full-text search is an available alternative, though it does not supply the same BM25 index behavior.

Version policy: No independently buildable release line is established. Exclude unless upstream source and redistribution/build evidence become available; Databricks's Lakebase versions (0.1.3 as listed 2026-09-30) do not establish portable release artifacts.

Target support: None while excluded. Databricks lists Lakebase PostgreSQL 16–18 only; those managed service claims establish no independent OS, architecture or general PostgreSQL support.

Sources: [Databricks extension catalogue](https://docs.databricks.com/aws/en/oltp/projects/extensions), [lakebase_text reference](https://docs.databricks.com/aws/en/oltp/projects/lakebase-text), [Lakebase Search overview](https://docs.databricks.com/aws/en/oltp/projects/lakebase-search).

## lakebase_tokenizer — exclude

Description: [lakebase_tokenizer](https://docs.databricks.com/aws/en/oltp/projects/lakebase-tokenizer) adds a configurable whole-word text-search dictionary template, `tokenizer_wholeword`; its SQL extension name is `lakebase_tokenizer`.

For inclusion: Databricks supports it in Lakebase Search. It exposes configurable normalization, accent removal, stemming, stop words and synonyms through PostgreSQL's text-search interfaces, and can feed both standard GIN and Lakebase BM25 indexes.

Against inclusion: Reviewed primary material documents it as a Lakebase feature and supplies no source repository, independent package, license/redistribution terms or build instructions. The Snowball stemmer is identified as bundled, but its presence does not clarify the extension's source or redistribution rights. Evidence is unavailable; redistribution is not established to be legally impossible.

Version policy: No independently buildable release line is established. Exclude pending source, redistribution and independent build evidence; Lakebase's listed version 0.1.1 is a managed-service version, not a portable release line.

Target support: None while excluded. Databricks lists Lakebase PostgreSQL 16–18 only and makes no independent OS or architecture compatibility claim.

Sources: [Databricks extension catalogue](https://docs.databricks.com/aws/en/oltp/projects/extensions), [lakebase_tokenizer reference](https://docs.databricks.com/aws/en/oltp/projects/lakebase-tokenizer), [Lakebase Search overview](https://docs.databricks.com/aws/en/oltp/projects/lakebase-search).

## lakebase_vector — exclude

Description: [lakebase_vector](https://docs.databricks.com/aws/en/oltp/projects/lakebase-vector) adds approximate nearest-neighbor search through the `lakebase_ann` index type; its SQL extension name is `lakebase_vector`. It depends on `pgvector` for its vector types and query interface.

For inclusion: Databricks supports it in Lakebase Search. It provides ANN search as a companion to pgvector and could provide a useful search capability to PostgreSQL users.

Against inclusion: The reviewed primary material documents only the Databricks Lakebase implementation and exposes no source repository, independent package, license/redistribution terms or build route. The dependency on pgvector does not establish that the separate Lakebase extension can be redistributed. These are evidence gaps, not proof of a legal prohibition. Standalone pgvector remains an independently available alternative but does not establish equivalent `lakebase_ann` behavior.

Version policy: No independently buildable release line is established. Exclude pending upstream source and redistribution/build evidence; Lakebase's listed version 1.1.1 is not evidence of a portable release.

Target support: None while excluded. Databricks lists Lakebase PostgreSQL 16–18 only; no independent OS or architecture support is documented.

Sources: [Databricks extension catalogue](https://docs.databricks.com/aws/en/oltp/projects/extensions), [lakebase_vector reference](https://docs.databricks.com/aws/en/oltp/projects/lakebase-vector), [Lakebase Search overview](https://docs.databricks.com/aws/en/oltp/projects/lakebase-search).

## neon — exclude

Description: [neon](https://neon.com/docs/extensions/neon) provides views and functions for inspecting Neon compute-specific facilities, including local file cache statistics. Its SQL extension name is `neon`.

For inclusion: Neon documents the extension for monitoring its Local File Cache, and the Neon platform makes it available to customers.

Against inclusion: The documented behavior reports Neon-specific compute state and has no equivalent meaning on ordinary PostgreSQL. Neon documentation reviewed provides usage and API details but no independently distributable extension source, package, license/redistribution terms or standalone build instructions. That leaves source and redistribution evidence unavailable; it does not prove redistribution is legally forbidden. Its core functionality is also specific to Neon's compute/storage implementation, limiting usefulness in this distribution.

Version policy: No independently buildable release line is identified. Exclude unless portable source and redistribution/build evidence is published; Neon service availability is not a portable release policy.

Target support: None while excluded. Neon documents this for its managed Neon Postgres service; no generic PostgreSQL, OS or architecture compatibility claim is established.

Sources: [Neon extension reference](https://neon.com/docs/extensions/neon), [Neon compute management and Local File Cache](https://neon.com/docs/manage/endpoints/), [Neon extension catalogue](https://neon.com/docs/extensions).

## neon_utils — exclude

Description: [neon_utils](https://neon.com/docs/extensions/neon-utils) exposes `num_cpus()` to inspect compute allocation for Neon autoscaling. Its SQL extension name is `neon_utils`.

For inclusion: Neon documents it for observing autoscaling resource allocation, a practical operational question for Neon users.

Against inclusion: The documented function reports Neon-managed compute allocation and is tied to Neon's autoscaling service. It has no comparable meaning on a general PostgreSQL installation. The reviewed Neon documentation establishes service availability but not a public source repository, independent package, redistribution terms or standalone build path. This is unavailable evidence, not a finding that the law prohibits redistribution.

Version policy: No independently buildable release line is identified. Exclude pending public source and redistribution/build evidence; service-side versions cannot support this project's release policy.

Target support: None while excluded. Neon documents the capability for Neon Postgres only; no generic PostgreSQL, OS or architecture support is established.

Sources: [Neon neon_utils reference](https://neon.com/docs/extensions/neon-utils), [Neon autoscaling guide](https://neon.com/docs/guides/autoscaling-guide), [Neon extension catalogue](https://neon.com/docs/extensions).

## pg_analytics — exclude

Description: [pg_analytics](https://github.com/paradedb/pg_analytics) embeds DuckDB in PostgreSQL to query object stores and table formats through foreign data wrappers and query pushdown. Its SQL extension name is `pg_analytics`.

For inclusion: It addressed a useful analytics use case by querying S3, Parquet, Iceberg and Delta Lake from PostgreSQL. Its public code is under the PostgreSQL License, and its repository had substantial community interest (538 stars when checked).

Against inclusion: Upstream explicitly discontinued and archived the project on 2025-03-19, stating that it is no longer maintained and directing users to its primary `pg_search` project. It embeds DuckDB, requires Rust/pgrx and substantial native dependencies, and explicitly does not support Windows because pgrx does not support it. The functional spec permits an explicitly bounded platform subset, but the maintenance and build burden weigh against adding an archived, broad-dependency extension when the project targets all platforms.

Version policy: None while excluded. Upstream says the project is discontinued and provides no forward-maintained release line.

Target support: None while excluded. Upstream documents PostgreSQL 13+ and prebuilt Linux/macOS artifacts, but explicitly excludes Windows; no complete target OS/architecture matrix is claimed.

Sources: [upstream repository and discontinuation notice](https://github.com/paradedb/pg_analytics), [upstream installation and platform notes](https://github.com/paradedb/pg_analytics#installation), [release history](https://github.com/paradedb/pg_analytics/releases), [PGXN release record](https://pgxn.org/dist/pg_analytics/).

## pg_embedding — exclude

Description: [pg_embedding](https://github.com/neondatabase/pg_embedding) provided HNSW vector similarity search for PostgreSQL; its SQL extension name is `embedding`.

For inclusion: It was a public Apache-2.0 project with a useful vector search feature and a documented PostgreSQL extension interface.

Against inclusion: Neon explicitly stopped committing to the project in September 2023 and recommended migration to pgvector; the repository was archived on 2024-11-21. The project is therefore abandoned, and pgvector is the maintained alternative for this use case.

Version policy: None while excluded. Upstream has ended maintenance; pgvector is the maintained alternative for this use case.

Target support: None while excluded. The archived project does not establish current compatibility across PostgreSQL 15+ or the project's OS and architecture targets.

Sources: [upstream repository, archive notice and migration recommendation](https://github.com/neondatabase/pg_embedding), [Neon's sunset announcement](https://neon.com/blog/sunset-pgembedding), [archived 0.3.6 build metadata](https://github.com/neondatabase/pg_embedding/blob/main/Makefile).

## pg_jobmon — exclude

Description: [pg_jobmon](https://github.com/omniti-labs/pg_jobmon) provides persistent, non-transactional logging for PostgreSQL transactions and functions. Its SQL extension name is `pg_jobmon`.

For inclusion: It supplies durable job and function progress/error logs that survive transaction rollback, and the PostgreSQL License permits redistribution. Its upstream README documents PostgreSQL 9.2+ and integration with `dblink`; `pg_partman` documents it as an optional way to audit and monitor partition maintenance.

Against inclusion: PGXN's latest stable release is 1.4.1 from 2021-08-09, and no recent upstream maintenance or current major-host support was identified. Although upstream documents PostgreSQL 9.2+, current test evidence is absent. The extension also requires `dblink` and a local connection path; non-superuser setup stores credentials in an extension table and requires `pg_hba.conf` configuration. This is a meaningful setup and security cost for a narrow logging utility.

Version policy: None while excluded. Reconsider if maintenance and current compatibility evidence improve enough to offset its setup and security costs.

Target support: None while excluded. Upstream declares PostgreSQL 9.2+, which includes the project's PostgreSQL range, but current test evidence is absent; upstream documents no OS or architecture matrix. `dblink` must also be available.

Sources: [upstream README, requirements, setup and license](https://github.com/omniti-labs/pg_jobmon), [PGXN release record](https://pgxn.org/dist/pg_jobmon/), [pg_partman documentation describing optional integration](https://github.com/pgpartman/pg_partman), [AWS extension support overview](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.FeatureSupport.Extensions.html), [Supabase extension catalogue](https://supabase.com/docs/guides/database/extensions).

## lantern — exclude

Description: [Lantern](https://github.com/lanterndata/lantern) provides vector indexing and search for PostgreSQL. Its SQL extension name is `lantern`.

For inclusion: It offers a distinct HNSW index implementation that can use PostgreSQL's `vector` type, and upstream has an associated managed service and a visible user community.

Against inclusion: Lantern overlaps with pgvector's vector-search use case. On 2026-10-17, its latest listed release remained v0.5.0 from November 2024; the installation guide documented PostgreSQL through 17 and Linux x86-64 and Intel macOS paths, without PostgreSQL 18, Windows or arm64 support. Its native implementation adds substantial build and testing work for a narrow additional use case. The AGPL-3.0 licence permits redistribution subject to its source and licence obligations; it does not prohibit redistribution. The documented compatibility limits, overlap and support cost outweigh the case for adding this extension; age alone is not the exclusion rule.

Version policy: None while excluded. Re-review the current upstream compatibility and adoption evidence when reconsidering inclusion.

Target support: None while excluded. Upstream documents PostgreSQL through 17 and Linux and Intel macOS build paths; it does not establish the required cross-platform support.

Sources: [upstream repository and licence](https://github.com/lanterndata/lantern), [release history](https://github.com/lanterndata/lantern/releases), [installation and compatibility](https://lantern.dev/docs/lantern-hnsw/install), [pgvector migration guide](https://lantern.dev/docs/migrate/pgvector-self).

## lantern_extras — exclude

Description: [Lantern Extras](https://github.com/lanterndata/lantern_extras) provides the SQL extension `lantern_extras` and companion tools for generating, downloading, parsing and importing embeddings and vector benchmark data.

For inclusion: The functions can support applications using Lantern, and SQL objects can appear in application schemas.

Against inclusion: The standalone repository's latest tagged release is 0.3.0 from October 2024. Lantern's 0.4.0 release notes say the extras code moved into the main Lantern repository, so the separate project is inactive and superseded, not abandoned. The feature set downloads models and datasets, can perform CPU-intensive inference, and depends on ONNX Runtime; this adds substantial runtime, data and supply-chain work. Its BSL 1.1 licence permits redistribution but imposes production-use conditions; this is not a redistribution prohibition.

Version policy: None for the separate project while excluded. Reconsider if it becomes independently maintained and has a practical self-contained runtime and data closure.

Target support: None while excluded.

Sources: [repository and release history](https://github.com/lanterndata/lantern_extras), [0.3.0 release](https://github.com/lanterndata/lantern_extras/releases), [Lantern 0.4.0 release notes](https://github.com/lanterndata/lantern/releases), [licence](https://github.com/lanterndata/lantern_extras/blob/main/LICENSE).

## login_hook — exclude

Description: [login_hook](https://github.com/splendiddata/login_hook) invokes a user-defined function when a client logs in. Its SQL extension name is `login_hook`.

For inclusion: It provides login-time behavior that application schemas and administration functions may rely on. Upstream says it works with PostgreSQL 13–17.

Against inclusion: Upstream recommends PostgreSQL's native login event trigger starting with PostgreSQL 17 and says maintenance will be discontinued after PostgreSQL 19. The project remains available; this is planned end of maintenance, not abandonment. It must be loaded through `session_preload_libraries`, and an error in the login function can prevent ordinary users from logging in. The native replacement covers the use case from PostgreSQL 17 onward; the remaining PostgreSQL 15–16 use case does not outweigh the maintenance horizon and operational risk.

Version policy: None while excluded. The maintenance horizon and native replacement do not justify adding the extension.

Target support: None while excluded.

Sources: [upstream compatibility, maintenance and operational notes](https://github.com/splendiddata/login_hook), [PostgreSQL 17 native login event trigger example](https://www.postgresql.org/docs/17/event-trigger-database-login-example.html).

## pg-strom — exclude

Description: [PG-Strom](https://github.com/heterodb/pg-strom) accelerates analytical workloads using PostgreSQL with GPUs, NVMe and Apache Arrow. Its SQL extension name is `pg_strom`.

For inclusion: It is actively maintained, PostgreSQL-licensed, has substantial upstream adoption, and current upstream documentation supports PostgreSQL 15 and later. It provides a differentiated GPU query execution path.

Against inclusion: Upstream requires Linux on x86-64, an NVIDIA GPU of a specified compute capability, and a compatible CUDA toolkit and driver; some features also need additional drivers and licensed HeteroDB components. These hardware and runtime prerequisites conflict with the project's self-contained archives and exclude macOS, Windows and arm64. The exclusion is based on target and runtime constraints, not redistribution rights.

Version policy: None while excluded. Reconsider only if a useful supported mode can run within the project's platform and self-contained runtime requirements.

Target support: None while excluded.

Sources: [upstream project and licence](https://github.com/heterodb/pg-strom), [installation requirements](https://github.com/heterodb/pg-strom/blob/master/man/install.md), [release history](https://github.com/heterodb/pg-strom/releases).

## pg_transport — exclude

Description: AWS's [pg_transport](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.TransportableDB.Setup.html) extension physically transports PostgreSQL database files between instances. Its SQL extension name is `pg_transport`.

For inclusion: It provides a fast database migration workflow for Amazon RDS users.

Against inclusion: AWS explicitly limits transportable databases to RDS for PostgreSQL and says the capability cannot be used with on-premises or EC2-hosted PostgreSQL. Its function depends on RDS-specific instance coordination and setup, so it has no established use in this standalone distribution. The reviewed sources do not establish that redistribution is prohibited.

Version policy: None while excluded. Reconsider if AWS documents independent use or another maintained project provides a portable implementation.

Target support: None while excluded.

Sources: [AWS transport limitations](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.TransportableDB.html), [AWS setup instructions](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.TransportableDB.Setup.html).

## rds_tools — exclude

Description: [Amazon RDS for PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL_rds_tools-functions-reference.html) provides `rds_tools` functions for inspecting RDS instance information and operational state. Its SQL extension name is `rds_tools`.

For inclusion: AWS documents functions that can be useful to applications and administrators running on RDS for PostgreSQL.

Against inclusion: The functions expose RDS-specific instance metadata and operational state, so their behavior depends on AWS's managed service. The reviewed primary sources do not establish independent source, portable behavior or use outside RDS. This service coupling makes it unsuitable for a cross-platform standalone distribution; it is not a finding that redistribution is prohibited.

Version policy: None while excluded. Reconsider if AWS publishes an independently buildable implementation with behavior useful outside its managed service.

Target support: None while excluded. AWS service availability does not establish independent OS or PostgreSQL compatibility.

Sources: [AWS rds_tools function reference](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL_rds_tools-functions-reference.html), [AWS extension catalogue](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html).

## MobilityDB — exclude

Description: [MobilityDB](https://github.com/MobilityDB/MobilityDB) adds temporal and spatial trajectory types and operations to PostgreSQL and PostGIS. Its SQL extension name is `mobilitydb`.

For inclusion: It is maintained, has an OSGeo community, and provides schema types for a real but specialized moving-object use case. The September 2026 releases include security fixes.

Against inclusion: The October 2026 AWS RDS, Azure Flexible Server and Google Cloud SQL extension catalogues do not list it, and available adoption evidence does not establish wide use. Its documented target is Linux and PostgreSQL 16–19; building and running it also requires PostGIS, GEOS, PROJ and JSON-C, with a PostGIS preload and increased lock setting. This is a substantial support cost for a project without either established inclusion signal in the specification.

Version policy: None while excluded. Reassess the 1.2 and 1.3 lines if adoption or hosting support changes; the upstream 1.2-to-1.3 data-format change requires backup and restore.

Target support: None while excluded. Current upstream documentation limits the build to PostgreSQL 16–19 and tests Linux; those facts do not establish a portable archive for this project.

Sources: [upstream build and installation requirements](https://github.com/MobilityDB/MobilityDB), [releases](https://github.com/MobilityDB/MobilityDB/releases), [AWS RDS catalogue](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html), [Azure Flexible Server catalogue](https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-versions), [Google Cloud SQL catalogue](https://docs.cloud.google.com/sql/docs/postgres/extensions), [upstream Docker image](https://hub.docker.com/r/mobilitydb/mobilitydb).

## online_advisor — exclude

Description: [online_advisor](https://github.com/knizhnik/online_advisor) observes query execution and proposes index and extended-statistics DDL. Its SQL extension name is `online_advisor`.

For inclusion: [Neon offers it on PostgreSQL 17](https://neon.com/blog/easier-postgres-fine-tuning-with-online_advisor), and its advice can help tune application queries.

Against inclusion: Its adoption evidence is limited, its executor-hook integration creates version-sensitive maintenance work, and upstream has not documented support across this project's OS and architecture targets. PostgreSQL 14–16 require preloading it, and PostgreSQL 18 compatibility is not established by the reviewed sources. These costs outweigh the present case for inclusion.

Version policy: None while excluded. Reconsider if upstream establishes a maintained compatibility range and broader adoption justifies the cross-platform build and verification cost.

Target support: None while excluded; `online_advisor` must not appear in intended support or the public inventory.

Sources: [upstream project and installation notes](https://github.com/knizhnik/online_advisor), [Neon announcement](https://neon.com/blog/easier-postgres-fine-tuning-with-online_advisor).

## Unreviewed projects

Candidates extracted from the October 2026 research. No inclusion decision is implied. Names in the second column are SQL extension names used by `CREATE EXTENSION`. Provider documentation is linked where the research did not identify an upstream source project.

| Project | SQL extension names | Upstream URL |
| --- | --- | --- |
| age | `age` | [Upstream](https://github.com/apache/age) |
| aiven-extras | `aiven_extras` | [Upstream](https://github.com/aiven/aiven-extras) |
| Azure pg_diskann | `pg_diskann` | [Upstream](https://learn.microsoft.com/azure/postgresql/extensions/concepts-extensions-by-engine) |
| citus | `citus`, `citus_columnar` | [Upstream](https://github.com/citusdata/citus) |
| credcheck | `credcheck` | [Upstream](https://github.com/HexaCluster/credcheck) |
| emaj | `emaj` | [Upstream](https://github.com/dalibo/emaj) |
| h3-pg | `h3`, `h3_postgis` | [Upstream](https://github.com/postgis/h3-pg) |
| index_advisor | `index_advisor` | [Upstream](https://github.com/supabase/index_advisor) |
| ip4r | `ip4r` | [Upstream](https://github.com/RhodiumToad/ip4r) |
| mysql_fdw | `mysql_fdw` | [Upstream](https://github.com/EnterpriseDB/mysql_fdw) |
| orafce | `orafce` | [Upstream](https://github.com/orafce/orafce) |
| paradedb | `pg_search` | [Upstream](https://github.com/paradedb/paradedb) |
| pg-semver | `semver` | [Upstream](https://github.com/theory/pg-semver) |
| pg_bigm | `pg_bigm` | [Upstream](https://github.com/pgbigm/pg_bigm) |
| pg_failover_slots | `pg_failover_slots` | [Upstream](https://github.com/EnterpriseDB/pg_failover_slots) |
| pg_graphql | `pg_graphql` | [Upstream](https://github.com/supabase/pg_graphql) |
| pg_hashids | `pg_hashids` | [Upstream](https://github.com/iCyberon/pg_hashids) |
| pg_mooncake | `pg_mooncake` | [Upstream](https://github.com/Mooncake-Labs/pg_mooncake) |
| pg_net | `pg_net` | [Upstream](https://github.com/supabase/pg_net) |
| pg_partman | `pg_partman` | [Upstream](https://github.com/pgpartman/pg_partman) |
| pg_pathman | `pg_pathman` | [Upstream](https://github.com/postgrespro/pg_pathman) |
| pg_proctab | `pg_proctab` | [Upstream](https://gitlab.com/pg_proctab/pg_proctab) |
| pg_qualstats | `pg_qualstats` | [Upstream](https://github.com/powa-team/pg_qualstats) |
| pg_repack | `pg_repack` | [Upstream](https://github.com/reorg/pg_repack) |
| pg_roaringbitmap | `roaringbitmap` | [Upstream](https://github.com/BrandwatchLtd/pg_roaringbitmap) |
| pg_session_jwt | `pg_session_jwt` | [Upstream](https://github.com/neondatabase/pg_session_jwt) |
| pg_similarity | `pg_similarity` | [Upstream](https://github.com/eulerto/pg_similarity) |
| pg_squeeze | `pg_squeeze` | [Upstream](https://github.com/cybertec-postgresql/pg_squeeze) |
| pg_stat_kcache | `pg_stat_kcache` | [Upstream](https://github.com/powa-team/pg_stat_kcache) |
| pg_stat_monitor | `pg_stat_monitor` | [Upstream](https://github.com/percona/pg_stat_monitor) |
| pg_textsearch | `pg_textsearch` | [Upstream](https://github.com/timescale/pg_textsearch) |
| pg_tiktoken | `pg_tiktoken` | [Upstream](https://github.com/kelvich/pg_tiktoken) |
| pg_tle | `pg_tle` | [Upstream](https://github.com/aws/pg_tle) |
| pg_track_settings | `pg_track_settings` | [Upstream](https://github.com/rjuju/pg_track_settings) |
| pg_uuidv7 | `pg_uuidv7` | [Upstream](https://github.com/fboulnois/pg_uuidv7) |
| pg_wait_sampling | `pg_wait_sampling` | [Upstream](https://github.com/postgrespro/pg_wait_sampling) |
| pgactive | `pgactive` | [Upstream](https://github.com/aws/pgactive) |
| pgagent | `pgagent` | [Upstream](https://github.com/pgadmin-org/pgagent) |
| pgfincore | `pgfincore` | [Upstream](https://github.com/klando/pgfincore) |
| pgjwt | `pgjwt` | [Upstream](https://github.com/michelp/pgjwt) |
| pglogical | `pglogical` | [Upstream](https://github.com/2ndQuadrant/pglogical) |
| pgmq | `pgmq` | [Upstream](https://github.com/pgmq/pgmq) |
| pgpointcloud | `pointcloud`, `pointcloud_postgis` | [Upstream](https://github.com/pgpointcloud/pointcloud) |
| pgrag | `rag` | [Upstream](https://github.com/neondatabase/pgrag) |
| pgroonga | `pgroonga`, `pgroonga_database` | [Upstream](https://github.com/pgroonga/pgroonga) |
| pgrouting | `pgrouting` | [Upstream](https://github.com/pgRouting/pgrouting) |
| pgsodium | `pgsodium` | [Upstream](https://github.com/michelp/pgsodium) |
| pgsql-http | `http` | [Upstream](https://github.com/pramsey/pgsql-http) |
| pgtt | `pgtt` | [Upstream](https://github.com/darold/pgtt) |
| pgvecto.rs | `vectors` | [Upstream](https://github.com/tensorchord/pgvecto.rs) |
| pgvectorscale | `vectorscale` | [Upstream](https://github.com/timescale/pgvectorscale) |
| pgx_ulid | `pgx_ulid`, `ulid` | [Upstream](https://github.com/pksunkara/pgx_ulid) |
| pljava | `pljava` | [Upstream](https://github.com/tada/pljava) |
| plpgsql_check | `plpgsql_check` | [Upstream](https://github.com/okbob/plpgsql_check) |
| plprofiler | `plprofiler` | [Upstream](https://github.com/bigsql/plprofiler) |
| plproxy | `plproxy` | [Upstream](https://github.com/plproxy/plproxy) |
| plrust | `plrust` | [Upstream](https://github.com/pgcentralfoundation/plrust) |
| plv8 | `plcoffee`, `plls`, `plv8` | [Upstream](https://github.com/plv8/plv8) |
| postgres-protobuf | `postgres_protobuf` | [Upstream](https://github.com/mpartel/postgres-protobuf) |
| postgresql-hll | `hll` | [Upstream](https://github.com/citusdata/postgresql-hll) |
| postgresql-logfdw | `log_fdw` | [Upstream](https://github.com/aws/postgresql-logfdw) |
| postgresql-topn | `topn` | [Upstream](https://github.com/citusdata/postgresql-topn) |
| postgresql-unit | `unit` | [Upstream](https://github.com/df7cb/postgresql-unit) |
| postgresql_anonymizer | `anon` | [Upstream](https://github.com/dalibo/postgresql_anonymizer) |
| powa-archivist | `powa` | [Upstream](https://github.com/powa-team/powa-archivist) |
| prefix | `prefix` | [Upstream](https://github.com/dimitri/prefix) |
| rdkit | `rdkit` | [Upstream](https://github.com/rdkit/rdkit) |
| rds_casts | `rds_casts` | [Upstream](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.CustomCasts.html) |
| rum | `rum` | [Upstream](https://github.com/postgrespro/rum) |
| session_variable | `session_variable` | [Upstream](https://github.com/splendiddata/session_variable) |
| tdigest | `tdigest` | [Upstream](https://github.com/tvondra/tdigest) |
| tds_fdw | `tds_fdw` | [Upstream](https://github.com/tds-fdw/tds_fdw) |
| temporal_tables | `temporal_tables` | [Upstream](https://github.com/nearform/temporal_tables) |
| timescaledb | `timescaledb` | [Upstream](https://github.com/timescale/timescaledb) |
| timescaledb-toolkit | `timescaledb_toolkit` | [Upstream](https://github.com/timescale/timescaledb-toolkit) |
| vault | `supabase_vault` | [Upstream](https://github.com/supabase/vault) |
| VectorChord | `vchord` | [Upstream](https://github.com/tensorchord/VectorChord) |
| wrappers | `wrappers` | [Upstream](https://github.com/supabase/wrappers) |
| zombodb | `zombodb` | [Upstream](https://github.com/zombodb/zombodb) |

## Extensions listed by major hosting providers

**Fetched in October 2026.** These are the names captured from the linked provider catalogues, and may be useful when determining how widely supported a extension is. Listings can cover older PostgreSQL versions, deprecated extensions or restricted installations; consult the provider for version-specific support. Project labels have been normalized to SQL extension names.

### Supabase

[Provider catalogue](https://supabase.com/docs/guides/database/extensions). Scope: official preconfigured extension table.

`address_standardizer`, `address_standardizer_data_us`, `autoinc`, `bloom`, `btree_gin`, `btree_gist`, `citext`, `cube`, `dblink`, `dict_int`, `dict_xsyn`, `earthdistance`, `fuzzystrmatch`, `hstore`, `http`, `hypopg`, `index_advisor`, `insert_username`, `intarray`, `isn`, `lo`, `ltree`, `moddatetime`, `old_snapshot`, `pg_cron`, `pg_graphql`, `pg_hashids`, `pg_jsonschema`, `pg_net`, `pg_partman`, `pg_prewarm`, `pg_repack`, `pg_stat_statements`, `pg_trgm`, `pg_walinspect`, `pgaudit`, `pgcrypto`, `pgjwt`, `pgroonga`, `pgroonga_database`, `pgrouting`, `pgrowlocks`, `pgsodium`, `pgstattuple`, `pgtap`, `plcoffee`, `pljava`, `plls`, `plpgsql`, `plpgsql_check`, `plv8`, `postgis`, `postgres_fdw`, `refint`, `rum`, `seg`, `sslinfo`, `tablefunc`, `tcn`, `timescaledb`, `tsm_system_rows`, `tsm_system_time`, `unaccent`, `uuid-ossp`, `vector`, `wrappers`.

### Neon

[Provider catalogue](https://neon.com/docs/extensions/pg-extensions). Scope: official PostgreSQL 14–18 version table.

`address_standardizer`, `address_standardizer_data_us`, `anon`, `autoinc`, `bloom`, `btree_gin`, `btree_gist`, `citext`, `cube`, `dblink`, `dict_int`, `earthdistance`, `fuzzystrmatch`, `h3`, `h3_postgis`, `hll`, `hstore`, `hypopg`, `insert_username`, `intagg`, `intarray`, `ip4r`, `lo`, `ltree`, `moddatetime`, `neon`, `neon_utils`, `online_advisor`, `pg_cron`, `pg_graphql`, `pg_hashids`, `pg_hint_plan`, `pg_ivm`, `pg_jsonschema`, `pg_mooncake`, `pg_partman`, `pg_prewarm`, `pg_repack`, `pg_session_jwt`, `pg_stat_statements`, `pg_tiktoken`, `pg_trgm`, `pg_uuidv7`, `pgcrypto`, `pgjwt`, `pgrouting`, `pgrowlocks`, `pgstattuple`, `pgtap`, `pgx_ulid`, `plcoffee`, `plls`, `plpgsql`, `plpgsql_check`, `plv8`, `postgis`, `postgis_raster`, `postgis_sfcgal`, `postgis_tiger_geocoder`, `postgis_topology`, `postgres_fdw`, `prefix`, `rag`, `rdkit`, `refint`, `roaringbitmap`, `rum`, `seg`, `semver`, `tablefunc`, `tcn`, `timescaledb`, `tsm_system_rows`, `tsm_system_time`, `ulid`, `unaccent`, `unit`, `uuid-ossp`, `vector`, `xml2`.

### Azure Database for PostgreSQL Flexible Server

[Provider catalogue](https://learn.microsoft.com/en-us/azure/postgresql/extensions/concepts-extensions-versions). Scope: all official extension/module name sections, PostgreSQL 11–18 version matrix.

`address_standardizer`, `address_standardizer_data_us`, `age`, `amcheck`, `anon`, `azure_ai`, `azure_storage`, `bloom`, `btree_gin`, `btree_gist`, `citext`, `credcheck`, `cube`, `dblink`, `dict_int`, `dict_xsyn`, `earthdistance`, `fuzzystrmatch`, `hll`, `hstore`, `hypopg`, `intagg`, `intarray`, `ip4r`, `isn`, `lo`, `login_hook`, `ltree`, `oracle_fdw`, `orafce`, `pageinspect`, `pg_buffercache`, `pg_cron`, `pg_diskann`, `pg_failover_slots`, `pg_freespacemap`, `pg_hint_plan`, `pg_ivm`, `pg_partman`, `pg_prewarm`, `pg_repack`, `pg_squeeze`, `pg_stat_statements`, `pg_trgm`, `pg_visibility`, `pgaudit`, `pgcrypto`, `pglogical`, `pgrouting`, `pgrowlocks`, `pgstattuple`, `plpgsql`, `plpgsql_check`, `plv8`, `pointcloud`, `postgis`, `postgis_raster`, `postgis_sfcgal`, `postgis_tiger_geocoder`, `postgis_topology`, `postgres_fdw`, `postgres_protobuf`, `rdkit`, `semver`, `session_variable`, `sslinfo`, `tablefunc`, `tdigest`, `tds_fdw`, `temporal_tables`, `timescaledb`, `topn`, `tsm_system_rows`, `tsm_system_time`, `unaccent`, `uuid-ossp`, `vector`.

### Google Cloud SQL

[Provider catalogue](https://cloud.google.com/sql/docs/postgres/extensions). Scope: all four official support categories: PostGIS, data type, language, miscellaneous.

`address_standardizer`, `address_standardizer_data_us`, `amcheck`, `anon`, `autoinc`, `bloom`, `btree_gin`, `btree_gist`, `chkpass`, `citext`, `cube`, `dblink`, `dict_int`, `earthdistance`, `fuzzystrmatch`, `google_ml_integration`, `google_read_only_session`, `hll`, `hstore`, `insert_username`, `intagg`, `intarray`, `ip4r`, `isn`, `lo`, `ltree`, `moddatetime`, `oracle_fdw`, `orafce`, `pageinspect`, `pg_background`, `pg_bigm`, `pg_buffercache`, `pg_cron`, `pg_freespacemap`, `pg_hint_plan`, `pg_ivm`, `pg_partman`, `pg_prewarm`, `pg_proctab`, `pg_qualstats`, `pg_repack`, `pg_similarity`, `pg_squeeze`, `pg_stat_statements`, `pg_textsearch`, `pg_trgm`, `pg_visibility`, `pg_wait_sampling`, `pgaudit`, `pgcrypto`, `pgfincore`, `pglogical`, `pgrouting`, `pgrowlocks`, `pgstattuple`, `pgtap`, `pgtt`, `plpgsql`, `plpgsql_check`, `plproxy`, `plv8`, `postgis`, `postgis_raster`, `postgis_sfcgal`, `postgis_tiger_geocoder`, `postgis_topology`, `postgres_fdw`, `prefix`, `rdkit`, `refint`, `roaringbitmap`, `sslinfo`, `tablefunc`, `tcn`, `tds_fdw`, `temporal_tables`, `tsm_system_rows`, `tsm_system_time`, `unaccent`, `uuid-ossp`, `vector`.

### Amazon RDS for PostgreSQL

[Provider catalogue](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html). Scope: stable PostgreSQL 15–18 tables; preview columns excluded from the union.

`address_standardizer`, `address_standardizer_data_us`, `amcheck`, `autoinc`, `aws_commons`, `aws_lambda`, `aws_s3`, `bloom`, `bool_plperl`, `btree_gin`, `btree_gist`, `citext`, `collection`, `cube`, `dblink`, `dict_int`, `dict_xsyn`, `earthdistance`, `fuzzystrmatch`, `hll`, `hstore`, `hstore_plperl`, `hypopg`, `insert_username`, `intagg`, `intarray`, `ip4r`, `isn`, `jsonb_plperl`, `lo`, `log_fdw`, `ltree`, `moddatetime`, `mysql_fdw`, `old_snapshot`, `oracle_fdw`, `orafce`, `pageinspect`, `pg_bigm`, `pg_buffercache`, `pg_cron`, `pg_freespacemap`, `pg_hint_plan`, `pg_logicalinspect`, `pg_partman`, `pg_prewarm`, `pg_proctab`, `pg_repack`, `pg_similarity`, `pg_stat_monitor`, `pg_stat_statements`, `pg_tle`, `pg_transport`, `pg_trgm`, `pg_visibility`, `pg_walinspect`, `pgactive`, `pgaudit`, `pgcrypto`, `pglogical`, `pgrouting`, `pgrowlocks`, `pgstattuple`, `pgtap`, `plcoffee`, `plls`, `plperl`, `plpgsql`, `plprofiler`, `plrust`, `pltcl`, `plv8`, `postgis`, `postgis_raster`, `postgis_tiger_geocoder`, `postgis_topology`, `postgres_fdw`, `prefix`, `rdkit`, `rds_tools`, `refint`, `roaringbitmap`, `seg`, `sslinfo`, `tablefunc`, `tcn`, `tds_fdw`, `tsm_system_rows`, `tsm_system_time`, `unaccent`, `uuid-ossp`, `vector`.

### Aiven

[Provider catalogue](https://aiven.io/docs/products/postgresql/reference/list-of-extensions). Scope: all official supported-extension categories.

`address_standardizer`, `address_standardizer_data_us`, `aiven_extras`, `anon`, `bloom`, `bool_plperl`, `btree_gin`, `btree_gist`, `citext`, `cube`, `dblink`, `dict_int`, `earthdistance`, `fuzzystrmatch`, `h3`, `h3_postgis`, `hll`, `hstore`, `intagg`, `intarray`, `ip4r`, `isn`, `jsonb_plperl`, `lo`, `ltree`, `pageinspect`, `pg_buffercache`, `pg_cron`, `pg_partman`, `pg_prewarm`, `pg_repack`, `pg_similarity`, `pg_stat_statements`, `pg_trgm`, `pgaudit`, `pgcrypto`, `pgrouting`, `pgrowlocks`, `pgstattuple`, `plperl`, `plpgsql`, `postgis`, `postgis_legacy`, `postgis_raster`, `postgis_sfcgal`, `postgis_tiger_geocoder`, `postgis_topology`, `postgres_fdw`, `rum`, `seg`, `sslinfo`, `tablefunc`, `tcn`, `timescaledb`, `tsm_system_rows`, `tsm_system_time`, `unaccent`, `unit`, `uuid-ossp`, `vector`, `vectorscale`.
