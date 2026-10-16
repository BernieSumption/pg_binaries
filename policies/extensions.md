# Extension support

## Built-in extensions

Upstream: [PostgreSQL](https://www.postgresql.org/). We support the extensions bundled with each selected PostgreSQL release. The inventory must derive the actual list from build output.

The October 2026 research identified these names across PostgreSQL 15–18; they are not all present in every major, and are present here only for reference to identify built-in extensions easily. The authoritative source for whether an extension is built-in to a given version is inventory.json:

`adminpack`, `amcheck`, `autoinc`, `bloom`, `bool_plperl`, `bool_plperlu`, `btree_gin`, `btree_gist`, `citext`, `cube`, `dblink`, `dict_int`, `dict_xsyn`, `earthdistance`, `file_fdw`, `fuzzystrmatch`, `hstore`, `hstore_plperl`, `hstore_plperlu`, `hstore_plpython3u`, `insert_username`, `intagg`, `intarray`, `isn`, `jsonb_plperl`, `jsonb_plperlu`, `jsonb_plpython3u`, `lo`, `ltree`, `ltree_plpython3u`, `moddatetime`, `old_snapshot`, `pageinspect`, `pg_buffercache`, `pg_freespacemap`, `pg_logicalinspect`, `pg_prewarm`, `pg_stat_statements`, `pg_surgery`, `pg_trgm`, `pg_visibility`, `pg_walinspect`, `pgcrypto`, `pgrowlocks`, `pgstattuple`, `plperl`, `plperlu`, `plpgsql`, `plpython3u`, `pltcl`, `pltclu`, `postgres_fdw`, `refint`, `seg`, `sslinfo`, `tablefunc`, `tcn`, `tsm_system_rows`, `tsm_system_time`, `unaccent`, `uuid-ossp`, `xml2`.

## pgvector — include

Description: [pgvector](https://github.com/pgvector/pgvector) adds vector types, distance operations and indexes. Its SQL extension name is `vector`.

For inclusion: It is maintained, widely adopted and offered by several major PostgreSQL hosts. Vector columns and indexes occur directly in application DDL. The upstream PostgreSQL Licence permits redistribution.

Against inclusion: Native code must be built and checked against each claimed PostgreSQL and platform range. No external runtime data or service is required.

Version policy: Support the latest patch release of the 0.8 line, currently 0.8.7. Upstream's changelog records additions and fixes in that line, with no documented DDL break. Retain the latest release before any future documented compatibility break and assume a future major-version transition breaks compatibility. Releases before the September 2025 cutoff are not selected without a specific reason.

Target support: PostgreSQL 15 and later on Linux, macOS and Windows, x86-64 and arm64, subject to upstream's documented PostgreSQL support and verified archive results. Upstream currently documents PostgreSQL 13+ and Linux, macOS and Windows build procedures; its Windows instructions are for x64, so arm64 needs separate build and test evidence before any inventory claim.

Sources: [upstream build and usage guide](https://github.com/pgvector/pgvector), [changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md), [licence](https://github.com/pgvector/pgvector/blob/master/LICENSE), [Supabase extension catalogue](https://supabase.com/docs/guides/database/extensions), [Neon extension catalogue](https://neon.com/docs/extensions/pg-extensions).

## PostGIS — include

Description: [PostGIS](https://postgis.net/) adds spatial types, indexes and functions. Its SQL extension names include `postgis`, `postgis_raster`, `postgis_sfcgal` and `postgis_topology`. `postgis_legacy` is a compatibility SQL script, not an extension selected with `CREATE EXTENSION`.

For inclusion: PostGIS is mature, maintained and offered by major PostgreSQL hosts. Spatial columns, indexes, constraints and functions are used directly in application schemas. Include the project's optional SQL extensions at the project level, including SFCGAL, so the policy does not silently split one source project.

Against inclusion: GEOS, PROJ and LibXML2 add native dependencies; raster support adds GDAL, and SFCGAL adds a substantial C++ dependency stack. Required runtime libraries and redistributable coordinate-system data must be bundled with their licences and source obligations. The Linux pilot demonstrates one build path, but does not establish all-platform portability or complete redistribution evidence.

Version policy: Support the latest stable patch in each maintained 3.4, 3.5 and 3.6 line. PostGIS releases minor lines about annually, so this repository's compatibility rule treats each minor transition as a DDL break despite upstream's general expectation of additive minor releases. Keep the last release of each line for clients intending that line. Review older lines and new stable lines against the release cutoff and upstream maintenance status rather than carrying unsupported historical versions indefinitely.

Target support: On the six required OS and architecture targets, aim to support PostgreSQL versions within each line's documented compatibility. Upstream's current compatibility data describes PostgreSQL 12–17 for 3.4 and 12–18 for 3.5 and 3.6; intersect those ranges with this repository's PostgreSQL 15+ requirement. A supported line's absence on a required target remains unmet until upstream restrictions or tested evidence justify narrowing it. Verify the exact PostgreSQL endpoints and native dependency closure before advertising any archive.

Sources: [PostGIS compatibility data](https://www.postgis.net/development/compatibility/), [versioning and maintenance policy](https://postgis.net/development/versions_eol/), [installation guide](https://postgis.net/docs/manual-3.6/en/postgis_installation.html), [licensing inventory](https://github.com/postgis/postgis/blob/master/LICENSE.TXT), [Google Cloud SQL extension catalogue](https://docs.cloud.google.com/sql/docs/postgres/extensions).

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

## Unreviewed projects

Candidates extracted from the October 2026 research. No inclusion decision is implied. Names in the second column are SQL extension names used by `CREATE EXTENSION`. Provider documentation is linked where the research did not identify an upstream source project.

| Project | SQL extension names | Upstream URL |
| --- | --- | --- |
| Address Standardizer | `address_standardizer`, `address_standardizer_data_us` | [Upstream](https://github.com/postgis/address_standardizer) |
| age | `age` | [Upstream](https://github.com/apache/age) |
| aiven-extras | `aiven_extras` | [Upstream](https://github.com/aiven/aiven-extras) |
| Azure pg_diskann | `pg_diskann` | [Upstream](https://learn.microsoft.com/azure/postgresql/extensions/concepts-extensions-by-engine) |
| citus | `citus`, `citus_columnar` | [Upstream](https://github.com/citusdata/citus) |
| collection | `collection` | [Upstream](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-versions.html) |
| credcheck | `credcheck` | [Upstream](https://github.com/HexaCluster/credcheck) |
| emaj | `emaj` | [Upstream](https://github.com/dalibo/emaj) |
| h3-pg | `h3`, `h3_postgis` | [Upstream](https://github.com/postgis/h3-pg) |
| hypopg | `hypopg` | [Upstream](https://github.com/HypoPG/hypopg) |
| index_advisor | `index_advisor` | [Upstream](https://github.com/supabase/index_advisor) |
| ip4r | `ip4r` | [Upstream](https://github.com/RhodiumToad/ip4r) |
| lakebase_text | `lakebase_text` | [Upstream](https://docs.databricks.com/aws/en/oltp/projects/extensions) |
| lakebase_tokenizer | `lakebase_tokenizer` | [Upstream](https://docs.databricks.com/aws/en/oltp/projects/extensions) |
| lakebase_vector | `lakebase_vector` | [Upstream](https://docs.databricks.com/aws/en/oltp/projects/extensions) |
| lantern | `lantern` | [Upstream](https://github.com/lanterndata/lantern) |
| lantern_extras | `lantern_extras` | [Upstream](https://github.com/lanterndata/lantern_extras) |
| login_hook | `login_hook` | [Upstream](https://github.com/splendiddata/login_hook) |
| MobilityDB | `mobilitydb` | [Upstream](https://github.com/MobilityDB/MobilityDB) |
| mysql_fdw | `mysql_fdw` | [Upstream](https://github.com/EnterpriseDB/mysql_fdw) |
| neon | `neon` | [Upstream](https://neon.com/docs/manage/endpoints/) |
| neon_utils | `neon_utils` | [Upstream](https://neon.com/docs/extensions/pg-extensions) |
| online_advisor | `online_advisor` | [Upstream](https://github.com/knizhnik/online_advisor) |
| orafce | `orafce` | [Upstream](https://github.com/orafce/orafce) |
| paradedb | `pg_search` | [Upstream](https://github.com/paradedb/paradedb) |
| pg-semver | `semver` | [Upstream](https://github.com/theory/pg-semver) |
| pg-strom | `pg_strom` | [Upstream](https://github.com/heterodb/pg-strom) |
| pg_analytics | `pg_analytics` | [Upstream](https://github.com/paradedb/pg_analytics) |
| pg_background | `pg_background` | [Upstream](https://github.com/vibhorkum/pg_background) |
| pg_bigm | `pg_bigm` | [Upstream](https://github.com/pgbigm/pg_bigm) |
| pg_cron | `pg_cron` | [Upstream](https://github.com/citusdata/pg_cron) |
| pg_duckdb | `pg_duckdb` | [Upstream](https://github.com/duckdb/pg_duckdb) |
| pg_embedding | `embedding` | [Upstream](https://github.com/neondatabase/pg_embedding) |
| pg_failover_slots | `pg_failover_slots` | [Upstream](https://github.com/EnterpriseDB/pg_failover_slots) |
| pg_graphql | `pg_graphql` | [Upstream](https://github.com/supabase/pg_graphql) |
| pg_hashids | `pg_hashids` | [Upstream](https://github.com/iCyberon/pg_hashids) |
| pg_hint_plan | `pg_hint_plan` | [Upstream](https://github.com/ossc-db/pg_hint_plan) |
| pg_ivm | `pg_ivm` | [Upstream](https://github.com/sraoss/pg_ivm) |
| pg_jobmon | `pg_jobmon` | [Upstream](https://github.com/omniti-labs/pg_jobmon) |
| pg_jsonschema | `pg_jsonschema` | [Upstream](https://github.com/supabase/pg_jsonschema) |
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
| pg_transport | `pg_transport` | [Upstream](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.TransportableDB.Setup.html) |
| pg_uuidv7 | `pg_uuidv7` | [Upstream](https://github.com/fboulnois/pg_uuidv7) |
| pg_wait_sampling | `pg_wait_sampling` | [Upstream](https://github.com/postgrespro/pg_wait_sampling) |
| pgactive | `pgactive` | [Upstream](https://github.com/aws/pgactive) |
| pgagent | `pgagent` | [Upstream](https://github.com/pgadmin-org/pgagent) |
| pgaudit | `pgaudit` | [Upstream](https://github.com/pgaudit/pgaudit) |
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
| pgtap | `pgtap` | [Upstream](https://github.com/theory/pgtap) |
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
| PostGIS TIGER Geocoder | `postgis_tiger_geocoder` | [Upstream](https://gitea.osgeo.org/postgis/postgis_tiger_geocoder) |
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
| rds_tools | `rds_tools` | [Upstream](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL_rds_tools-functions-reference.html) |
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
