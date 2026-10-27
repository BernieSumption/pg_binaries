# Licences

This file identifies the declared terms for PostgreSQL, the selected extension projects and dependencies copied into the distribution. Source archives and checksums for the selected project releases are recorded in `support.json`. Dependencies added to packaged archives are added here when their recipes are implemented.

## PostgreSQL and extension projects

- PostgreSQL — PostgreSQL License. [Source and `COPYRIGHT`](https://github.com/postgres/postgres/blob/REL_18_6/COPYRIGHT).
- pgvector — PostgreSQL License. [Source and `LICENSE`](https://github.com/pgvector/pgvector/blob/v0.8.7/LICENSE).
- PostGIS — GPL-2.0-or-later. [Source and `COPYING`](https://github.com/postgis/postgis/blob/3.6.4/COPYING).
- PostGIS TIGER Geocoder — GPL-2.0, declared in `META.json` and `COPYING` in the [2025.2 source archive](https://download.osgeo.org/postgis/source/postgis_tiger_geocoder/postgis_tiger_geocoder-2025.2.tar.gz).
- Address Standardizer — MIT-style terms. [Source and `COPYING`](https://github.com/postgis/address_standardizer/blob/v3.7.0/COPYING). Its US data files have no separate declared terms in this release.
- HypoPG — PostgreSQL License. [Source and `LICENSE`](https://github.com/HypoPG/hypopg/blob/1.4.4/LICENSE).
- pgcollection — Apache-2.0. [Source and `LICENSE`](https://github.com/aws/pgcollection/blob/v2.1.3/LICENSE); the source also contains a [`NOTICE`](https://github.com/aws/pgcollection/blob/v2.1.3/NOTICE).
- pg_ivm — PostgreSQL-style licence. [Source and `LICENSE`](https://github.com/sraoss/pg_ivm/blob/v1.17/LICENSE).
- pgAudit — PostgreSQL licence. [Source and `LICENSE`](https://github.com/pgaudit/pgaudit/blob/18.0/LICENSE).
- pgTAP — PostgreSQL-style permissive terms. [Source and licence declaration](https://github.com/theory/pgtap/blob/v1.3.4/README.md#copyright-and-license).
- pg_jsonschema — Apache-2.0. [Source and `LICENSE`](https://github.com/supabase/pg_jsonschema/blob/v0.3.4/LICENSE).

## PostgreSQL build dependencies

- OpenSSL — Apache-2.0. [Source and `LICENSE.txt`](https://github.com/openssl/openssl/blob/openssl-3.5.8/LICENSE.txt).
- ICU4C — Unicode License v3. [Source and `LICENSE`](https://github.com/unicode-org/icu/blob/release-78.3/LICENSE).
- LZ4 — BSD-2-Clause. [Source and `lib/LICENSE`](https://github.com/lz4/lz4/blob/v1.10.0/lib/LICENSE).
- Zstandard — BSD-3-Clause for the bundled library. [Source and `LICENSE`](https://github.com/facebook/zstd/blob/v1.5.7/LICENSE).
- libxml2 — terms declared in its `Copyright` file. [Source and `Copyright`](https://gitlab.gnome.org/GNOME/libxml2/-/blob/master/Copyright).
- libxslt — terms declared in its `Copyright` file. [Source and `Copyright`](https://gitlab.gnome.org/GNOME/libxslt/-/blob/master/Copyright).

## Extension build dependencies

- PCRE2 — BSD-3-Clause with the PCRE2 exception. [Source and `LICENCE.md`](https://github.com/PCRE2Project/pcre2/blob/pcre2-10.48/LICENCE.md).
