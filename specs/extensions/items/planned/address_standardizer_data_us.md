# address_standardizer_data_us

`address_standardizer_data_us` supplies the US lexicon, gazetteer and rules for
address normalization. It shares the [parser's source releases](address_standardizer.md)
and MIT-X licence; retain any additional data notices. It is independently
downloadable.

## Versions and compatibility

Bundled 3.6 has an expected PostgreSQL 15–18 range. Standalone 3.7.0, dated
2026-07-10, needs separate compatibility checks; development 4.0.0 is excluded.
Use the [shared build rules](../../extensions-policy.md), recording the PostgreSQL tooling
used to generate/install this SQL/data package. It has no native module of its own.

Rule revisions can change normalized output without changing table shape.
Inspect table definitions and update scripts across the source transition;
an explicitly requested older version must retain its associated rules.

## Dependencies and resources

Include the upstream tables' DDL and seed content. These small defaults are
essential to the package's purpose. Census corpora, customer address lists and
administrative imports are excluded. The [extras documentation](https://postgis.net/docs/Extras.html)
explains the relationship between lexicon, gazetteer and rules.

The parser is required to use these tables for normalization. Creation
requirements depend on the selected release: the
[current standalone control file](https://github.com/postgis/address_standardizer/blob/main/address_standardizer_data_us.control)
has no `requires` entry, but each tagged file needs checking. No preload,
external service or additional native library is expected from this package.

## Evidence and remaining tests

The Linux pilot created bundled 3.6.4 and used it with `address_standardizer`.
See [pilot evidence and common gaps](../../extensions-notes.md#pilot-evidence).

Verify independent creation, paired normalization, table/update differences
and the size of the preserved default data.

## Completion

Meet the [extension packaging and verification criteria](../../extensions-policy.md#e06--item-content-and-completion) for this item's inventory scope, including the tests above. Keep exact release/platform results in coverage records.
