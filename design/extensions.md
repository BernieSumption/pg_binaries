# Extension selection

Application schemas use SQL extension objects for types, indexes, constraints, functions, auditing and related behaviour. This distribution selects extension projects whose installed files can be combined with its PostgreSQL archive and used on the supported target. One project archive may provide several SQL extension names.

## Selection criteria

Select an extension when its schema use and adoption justify the build, packaging and verification cost. Maintenance, availability from major PostgreSQL hosts, and documented PostgreSQL and platform compatibility support inclusion. Weak maintenance, experimental status, large or fragile dependencies, and limited platform support weigh against inclusion. An extension can support a subset of the distribution's targets when that subset is explicit.

Apply [dependency-licenses.md](dependency-licenses.md) to every selected project and redistributed dependency. Use upstream releases and upstream or distribution-maintained patches; this repository does not develop project-specific source patches to make a selected extension build. Binary loader-path changes and archive layout changes do not modify upstream source. If the selected release cannot be built for a required target under these rules, record the unmet target and seek a human decision rather than silently removing the project.

For each selected project, use its latest stable release compatible with the selected PostgreSQL release and supported target. Check upstream’s stated compatibility as well as the built archive’s test results. A missing macOS build guide or CI job does not establish incompatibility: inspect the source and try the selected target locally. An explicit upstream incompatibility with the selected PostgreSQL version or target requires investigation and a human decision before inclusion. Record the exact selected release, source URL and checksum in `support.json`. Select one release per project for the PostgreSQL release.

Each project decision below records its purpose, the reasons for and against inclusion, package scope, required setup and supporting sources. Exact build commands and project probes belong in implementation; [the common probe requirements](build-and-test.md#extension-probes) define their coverage. Source versions and upstream compatibility are checked when `support.json` is populated and at each refresh. Linked release-specific evidence records the previous review; it is not a claim that those versions remain the latest or that another release has the same compatibility. Built-in PostgreSQL extensions are selected with PostgreSQL in [postgresql-options.md](postgresql-options.md).

## Selected projects

### pgvector

[pgvector](https://github.com/pgvector/pgvector) supplies the SQL extension `vector`, including vector types and indexes that application schemas can use. It is widely adopted and has no separate runtime service or dataset. Its archive supplies the native module and SQL files. Native compilation and platform verification are its main support costs.

Sources: [upstream build and usage guide](https://github.com/pgvector/pgvector), [changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md), [licence](https://github.com/pgvector/pgvector/blob/master/LICENSE), [Supabase extension catalogue](https://supabase.com/docs/guides/database/extensions), [Neon extension catalogue](https://neon.com/docs/extensions/pg-extensions).

### PostGIS

[PostGIS](https://postgis.net/) supplies `postgis`, `postgis_raster`, `postgis_sfcgal` and `postgis_topology`. Spatial types, functions and indexes justify including all four SQL names in one project archive. Its native dependency tree includes GEOS, PROJ and libxml2, GDAL for raster support, and a substantial C++ stack for SFCGAL. Its archive includes the runtime libraries and redistributable data used by all four modules.

Optional upstream import, export and administration programs are excluded from the package because they are outside the selected schema use and can add interpreters or host dependencies. `postgis_legacy` is a compatibility script, not another selected SQL extension name. Address Standardizer and TIGER Geocoder are separate projects, even if a PostGIS source tree also contains related files.

Sources: [PostGIS compatibility data](https://www.postgis.net/development/compatibility/), [versioning and maintenance policy](https://postgis.net/development/versions_eol/), [installation guide](https://postgis.net/docs/manual-3.6/en/postgis_installation.html), [licensing inventory](https://github.com/postgis/postgis/blob/master/LICENSE.TXT), [Google Cloud SQL extension catalogue](https://docs.cloud.google.com/sql/docs/postgres/extensions).

### PostGIS TIGER Geocoder

[PostGIS TIGER Geocoder](https://postgis.net/) supplies `postgis_tiger_geocoder`. Its installed SQL defines schema objects used for address normalization and geocoding. The package requires PostGIS and PostgreSQL's built-in `fuzzystrmatch`; `support.json` and `inventory.json` name those prerequisites so clients install them in the required order. The separately released project supplies SQL and PL/pgSQL rather than a native module. Creating the extension needs no downloaded Census data. The package does not include US Census TIGER data or claim usable address geocoding before a user loads that data.

Sources: [2025.2 announcement](https://postgis.net/2026/08/PostGIS-Tiger-Geocoder-2025.2/), [upstream 2025.2 source archive](https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz) (`README.md`, `META.json` and `COPYING`), [PostGIS installation guide](https://postgis.net/docs/postgis_installation.html).

### Address Standardizer

[Address Standardizer](https://github.com/postgis/address_standardizer) supplies `address_standardizer` and `address_standardizer_data_us` for address parsing and rule-based standardization. Treat it as its own upstream project, not as a PostGIS prerequisite. Package its PCRE2 runtime dependency where the selected target does not guarantee the required version, and review the selected release’s data files and terms before redistribution.

The old review of standalone 3.7.0 accepted its USPS-derived city file and compiled output under the repository’s MIT-style declaration because no separate data terms were present. This applies the [declared-project licence rule](dependency-licenses.md#declared-project-licences); it does not require investigating upstream’s authority over the earlier USPS source. Separately declared data terms, including those found on later development-branch Brazil data, require their own review.

The old Windows build attempts failed on tagged source constructs; this evidence remains relevant when considering that target, without establishing anything about a newly selected release.

Sources: [v3.7.0 release](https://github.com/postgis/address_standardizer/releases/tag/v3.7.0), [tagged build instructions](https://github.com/postgis/address_standardizer/blob/v3.7.0/README.md), [tagged PostgreSQL CI matrix](https://github.com/postgis/address_standardizer/blob/v3.7.0/.github/workflows/ci.yml), [tagged repository licence](https://github.com/postgis/address_standardizer/blob/v3.7.0/COPYING), [later Brazil data terms](https://github.com/postgis/address_standardizer/blob/main/README.md#open-data-provenance-for-brazil-dataset-address_standardizer_data_br), [PostGIS 3.6 build rules](https://github.com/postgis/postgis/blob/stable-3.6/extensions/address_standardizer/Makefile.in).

### HypoPG

[HypoPG](https://github.com/HypoPG/hypopg) supplies `hypopg`, which lets a session evaluate hypothetical indexes without creating physical indexes. Its hypothetical indexes are session-local and add no persistent table data. Hosted availability and its established query-tuning use support inclusion. The archive contains its native module and SQL files. The distribution does not promise extension upgrade paths that it has not tested.

Sources: [upstream releases and compatibility notes](https://github.com/HypoPG/hypopg/releases), [upstream installation notes](https://github.com/HypoPG/hypopg), [Crunchy extension compatibility](https://access.crunchydata.com/documentation/postgres-operator/latest/references/components), [Crunchy Bridge extension list](https://docs.crunchybridge.com/extensions-and-languages), [Supabase HypoPG guide](https://supabase.com/docs/guides/database/extensions/hypopg).

### collection

[pgcollection](https://github.com/aws/pgcollection) supplies `collection`, associative-array types used by PL/pgSQL schemas and migration work. It supports migration of Oracle associative-array code. AWS supplies maintained public source, but the previous selection review found limited adoption evidence beyond AWS RDS. Native compilation adds a support cost; no external service or runtime dataset was identified. The archive contains the native module and upstream installation files.

Sources: [upstream source](https://github.com/aws/pgcollection), [release history](https://github.com/aws/pgcollection/releases), [PGXN 1.0.0 and 2.0.0 release dates](https://pgxn.org/dist/pgcollection/1.0.0/), [AWS RDS extension catalogue](https://docs.aws.amazon.com/AmazonRDS/latest/PostgreSQLReleaseNotes/postgresql-extensions.html).

### pg_cron

[pg_cron](https://github.com/citusdata/pg_cron) supplies `pg_cron` for scheduled SQL jobs. `support.json` and `inventory.json` state the required `shared_preload_libraries` setting, restart and local connection configuration. Its background worker normally opens local libpq connections, so the documented setup includes the required `pg_hba.conf` access. It is installed in one database per cluster. Broad hosting support and maintained upstream source justify the configuration cost; it adds no separate runtime service.

Sources: [upstream README, requirements and provider list](https://github.com/citusdata/pg_cron), [release history and PostgreSQL compatibility](https://github.com/citusdata/pg_cron/releases), [Supabase extension catalogue](https://github.com/supabase/postgres).

### pg_ivm

[pg_ivm](https://github.com/sraoss/pg_ivm) supplies `pg_ivm` for incrementally maintained materialized views. `support.json` and `inventory.json` state its preload or session-load requirement. Package any upstream utility required to restore maintenance metadata, so dump/restore does not lose the ability to maintain those views. Native code and required preload configuration are the principal support costs. Incremental maintenance of application schema objects justifies inclusion.

Sources: [upstream description, compatibility and configuration](https://github.com/sraoss/pg_ivm), [release history and 1.16 fixes](https://github.com/sraoss/pg_ivm/releases), [upstream license](https://github.com/sraoss/pg_ivm/blob/main/LICENSE).

### pgaudit

[pgAudit](https://github.com/pgaudit/pgaudit) supplies `pgaudit` for PostgreSQL audit logging. Select the latest stable release from the upstream branch compatible with the selected PostgreSQL major. `support.json` and `inventory.json` state its `shared_preload_libraries` and restart requirements. Creating the SQL extension precedes enabling log classes when full DDL audit detail is required. Audit logging is best-effort rather than transactional. Its maintained upstream and hosted use support inclusion despite preload and configuration requirements.

Sources: [upstream compatibility, build and preload guidance](https://github.com/pgaudit/pgaudit#postgresql-version-compatibility), [release history](https://github.com/pgaudit/pgaudit/releases), [licence](https://github.com/pgaudit/pgaudit/blob/main/LICENSE), [logging caveats](https://github.com/pgaudit/pgaudit#caveats), [Amazon RDS guide](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.pgaudit.html), [Google Cloud SQL catalogue](https://docs.cloud.google.com/sql/docs/postgres/extensions).

### pgtap

[pgTAP](https://github.com/theory/pgtap) supplies `pgtap`, SQL assertion functions used to test database schemas. Package the installed SQL and upgrade files. The upstream build may use Perl to generate them; the archive excludes the optional Perl-based `pg_prove` harness. Its installed SQL and PL/pgSQL functions need no additional language runtime. Files such as `pgtap-core` or `pgtap-schema` are not additional SQL extension identities unless the selected upstream release supplies corresponding control files.

Sources: [PGXN release and metadata](https://pgxn.org/dist/pgtap/), [1.3.4 source, release notes and compatibility](https://api.pgxn.org/src/pgtap/pgtap-1.3.4/), [upstream build and release process](https://github.com/theory/pgtap), [Debian package](https://packages.debian.org/sid/source/pgtap).

### pg_jsonschema

[pg_jsonschema](https://github.com/supabase/pg_jsonschema) supplies `pg_jsonschema`, JSON Schema validation functions usable in application constraints. Its archive contains the native module and SQL files; compilation uses Rust and pgrx. Supabase maintains and offers the project. Rust/pgrx adds build cost, and upstream Linux binaries do not establish that our macOS archive works. The selected toolchain’s platform support needs inspection during the local build; no external data or service is required for schema use.

Sources: [upstream releases](https://github.com/supabase/pg_jsonschema/releases), [0.3.4 source and release workflow](https://github.com/supabase/pg_jsonschema/tree/v0.3.4), [0.3.4 Cargo features and pgrx dependency](https://raw.githubusercontent.com/supabase/pg_jsonschema/v0.3.4/Cargo.toml), [pgrx 0.16.1 platform guidance](https://raw.githubusercontent.com/pgcentralfoundation/pgrx/v0.16.1/README.md), [Supabase documentation](https://supabase.com/docs/guides/database/extensions/pg_jsonschema), [licence](https://github.com/supabase/pg_jsonschema/blob/master/LICENSE).
