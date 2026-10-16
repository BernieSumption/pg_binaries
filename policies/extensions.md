# Extension support

## Built-in extensions

Upstream: [PostgreSQL](https://www.postgresql.org/). We support the extensions bundled with each selected PostgreSQL release. The inventory must derive the actual list from build output.

The October 2026 research identified these names across PostgreSQL 15–18; they are not all present in every major, and are present here only for reference to identify built-in extensions easily. The authoritative source for whether an extension is built-in to a given version is inventory.json:

`adminpack`, `amcheck`, `autoinc`, `bloom`, `bool_plperl`, `bool_plperlu`, `btree_gin`, `btree_gist`, `citext`, `cube`, `dblink`, `dict_int`, `dict_xsyn`, `earthdistance`, `file_fdw`, `fuzzystrmatch`, `hstore`, `hstore_plperl`, `hstore_plperlu`, `hstore_plpython3u`, `insert_username`, `intagg`, `intarray`, `isn`, `jsonb_plperl`, `jsonb_plperlu`, `jsonb_plpython3u`, `lo`, `ltree`, `ltree_plpython3u`, `moddatetime`, `old_snapshot`, `pageinspect`, `pg_buffercache`, `pg_freespacemap`, `pg_logicalinspect`, `pg_prewarm`, `pg_stat_statements`, `pg_surgery`, `pg_trgm`, `pg_visibility`, `pg_walinspect`, `pgcrypto`, `pgrowlocks`, `pgstattuple`, `plperl`, `plperlu`, `plpgsql`, `plpython3u`, `pltcl`, `pltclu`, `postgres_fdw`, `refint`, `seg`, `sslinfo`, `tablefunc`, `tcn`, `tsm_system_rows`, `tsm_system_time`, `unaccent`, `uuid-ossp`, `xml2`.

## Unreviewed projects

Candidates extracted from the October 2026 research. No inclusion decision is implied. Names in the second column are SQL extension names used by `CREATE EXTENSION`. Provider documentation is linked where the research did not identify an upstream source project.

| Project | SQL extension names | Upstream URL |
| --- | --- | --- |
| Address Standardizer | `address_standardizer`, `address_standardizer_data_us` | [Upstream](https://github.com/postgis/address_standardizer) |
| age | `age` | [Upstream](https://github.com/apache/age) |
| aiven-extras | `aiven_extras` | [Upstream](https://github.com/aiven/aiven-extras) |
| aws_commons | `aws_commons` | [Upstream](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.FeatureSupport.Extensions.html) |
| aws_lambda | `aws_lambda` | [Upstream](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL-Lambda.html) |
| aws_s3 | `aws_s3` | [Upstream](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PostgreSQL.S3Import.InstallExtension.html) |
| Azure pg_diskann | `pg_diskann` | [Upstream](https://learn.microsoft.com/azure/postgresql/extensions/concepts-extensions-by-engine) |
| azure_ai | `azure_ai` | [Upstream](https://learn.microsoft.com/en-us/azure/postgresql/azure-ai/generative-ai-azure-overview) |
| azure_storage | `azure_storage` | [Upstream](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/concepts-storage-extension) |
| citus | `citus`, `citus_columnar` | [Upstream](https://github.com/citusdata/citus) |
| collection | `collection` | [Upstream](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-versions.html) |
| credcheck | `credcheck` | [Upstream](https://github.com/HexaCluster/credcheck) |
| emaj | `emaj` | [Upstream](https://github.com/dalibo/emaj) |
| google_ml_integration | `google_ml_integration` | [Upstream](https://docs.cloud.google.com/sql/docs/postgres/extensions) |
| google_read_only_session | `google_read_only_session` | [Upstream](https://docs.cloud.google.com/sql/docs/postgres/read-only-sessions) |
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
| oracle_fdw | `oracle_fdw` | [Upstream](https://github.com/laurenz/oracle_fdw) |
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
| pgvector | `vector` | [Upstream](https://github.com/pgvector/pgvector) |
| pgvectorscale | `vectorscale` | [Upstream](https://github.com/timescale/pgvectorscale) |
| pgx_ulid | `pgx_ulid`, `ulid` | [Upstream](https://github.com/pksunkara/pgx_ulid) |
| pljava | `pljava` | [Upstream](https://github.com/tada/pljava) |
| plpgsql_check | `plpgsql_check` | [Upstream](https://github.com/okbob/plpgsql_check) |
| plprofiler | `plprofiler` | [Upstream](https://github.com/bigsql/plprofiler) |
| plproxy | `plproxy` | [Upstream](https://github.com/plproxy/plproxy) |
| plrust | `plrust` | [Upstream](https://github.com/pgcentralfoundation/plrust) |
| plv8 | `plcoffee`, `plls`, `plv8` | [Upstream](https://github.com/plv8/plv8) |
| PostGIS | `postgis`, `postgis_legacy`, `postgis_raster`, `postgis_sfcgal`, `postgis_topology` | [Upstream](https://postgis.net/) |
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
