# address_standardizer

`address_standardizer` is the PAGC-derived address parser maintained with PostGIS
and now in a [standalone repository](https://github.com/postgis/address_standardizer).
Its source uses MIT-X terms; retain the selected source's `COPYING` and notices.

## Versions and compatibility

Discover bundled versions through [PostGIS releases](https://postgis.net/development/source_code/)
and standalone versions through [releases](https://github.com/postgis/address_standardizer/releases)
and [NEWS](https://github.com/postgis/address_standardizer/blob/main/NEWS.md).
Standalone 3.7.0 is dated 2026-07-10; 4.0.0dev is ineligible.

Bundled 3.6 has the expected PostgreSQL 15–18 range described under
[PostGIS](postgis.md). Standalone compatibility needs separate research.
Bundled and standalone releases are alternative sources of the same SQL extension;
record their identities and prevent conflicting definitions in one installation.
Apply the [shared build rules](../README.md).

The 3.7 standalone notes change country handling and parser output. Inspect
return types, signatures and update SQL across this transition: output changes
can matter even when the SQL interface remains unchanged.

## Dependencies and resources

The parser requires no PostGIS SQL extension or preload. Bundle its applicable
PCRE/PCRE2 runtime; the [standalone build instructions](https://github.com/postgis/address_standardizer#build-and-install)
require PCRE2. Standardization uses lexicon, gazetteer and rule tables.
[`address_standardizer_data_us`](address_standardizer_data_us.md) provides the
upstream US defaults; callers may supply their own tables. Bulk address corpora
and application imports are excluded.

## Evidence and remaining tests

The Linux pilot created bundled 3.6.4 and standardized a US address using the US
data extension. Standalone 3.7.0 remains unverified. See
[pilot evidence and common gaps](../README.md#pilot-evidence).

Test parser types, signatures and output changes across bundled and standalone
releases, including normalization with the matching US rules. Measure PCRE's
runtime contribution separately.
