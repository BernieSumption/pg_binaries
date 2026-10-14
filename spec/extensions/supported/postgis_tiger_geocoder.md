# postgis_tiger_geocoder

`postgis_tiger_geocoder` supplies TIGER schemas, address normalization and
geocoding functions. Its code came from PostGIS through 3.6 and now has a
[standalone repository](https://gitea.osgeo.org/postgis/postgis_tiger_geocoder).
Retain the exact source's GPL licence and component notices; Census data has
separate terms.

## Versions and compatibility

Discover bundled versions through [PostGIS releases](https://postgis.net/development/source_code/).
Standalone [2025.1](https://postgis.net/2026/06/PostGIS-Tiger-Geocoder-2025.1/)
was published 2026-06-22 and [2025.2](https://postgis.net/2026/08/PostGIS-Tiger-Geocoder-2025.2/)
on 2026-08-23. Their year identifies Census vintage. PostGIS 3.7 no longer
includes this module, so standalone versions need their own source identity.

Standalone TIGER requires PostgreSQL 16+, giving a project range of 16–18;
eligible bundled versions may still support 15. Apply the
[shared build rules](../README.md) to this PL/pgSQL package and its generated SQL.

Standalone 2025.1 removes automatic database search-path changes and PostgreSQL
support below 16. Its notes describe update paths, including an `ANY`
intermediate where needed. Test any advertised path with existing schema objects.

## Dependencies and data

The [bundled 3.6.4 control file](https://github.com/postgis/postgis/blob/3.6.4/extensions/postgis_tiger_geocoder/postgis_tiger_geocoder.control.in)
requires `postgis` and PostgreSQL's `fuzzystrmatch`, using schema `tiger`.
Check standalone control files separately. PL/pgSQL must be available; no preload
is expected. Optional PAGC normalization uses `address_standardizer` and its rules.

Include the schema and small default lookups and loader configuration. The large
Census corpus populates geocoding tables and is unnecessary for `CREATE EXTENSION`
or basic normalization; locating real addresses requires that external content.
See the [extras documentation](https://postgis.net/docs/Extras.html).

Users who need Census content configure loaders, generate shell scripts with
[`loader_generate_nation_script`](https://postgis.net/docs/Loader_Generate_Nation_Script.html)
and [`loader_generate_script`](https://postgis.net/docs/Loader_Generate_Script.html),
then run them to download/import selected geography into database tables. That
administrative table-population workflow is outside this project's downloads.

## Evidence and remaining tests

The Linux pilot passed bundled 3.6.4 creation and address normalization;
`tiger.state` remained empty. Real Census geocoding and standalone releases
remain unverified. See [pilot evidence and common gaps](../README.md#pilot-evidence).

Inspect standalone licence/control files and test schema creation, normalization
without Census data, search-path behaviour and relevant update paths.
