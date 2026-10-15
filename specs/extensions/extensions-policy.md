# Extensions policy

This board covers independently selectable SQL extensions. The [inventory](../functional/functional-inventory.json) contains the selected portfolio and version selectors. Extension items record the source-specific decisions and research.

## E01 — Selection and version scope

Follow [F01](../functional/functional-policy.md#f01--version-coverage-remains-visible) for the fixed release cutoff, PostgreSQL floor and platform coverage. Include eligible maintenance releases from selected projects. Do not treat a failed build or missing port as evidence that a release is out of scope.

The existing portfolio is explicitly selected. Selection of further extensions requires release-specific compatibility research, a dependency/licence inventory, package sizes and clean-host DDL/query tests on the target platforms. Broader portfolio priorities remain an open question in notes.

## E02 — SQL module boundaries

Apply [F03](../functional/functional-policy.md#f03--sql-extensions-can-be-obtained-separately): independently selectable SQL modules have separate downloads, with declared ownership of shared native files. Record source project, SQL version and binary build identity separately.

## E03 — Declared dependency names

Copy dependency names from the applicable upstream control files. Clients choose dependency versions and handling. Record the exact versions tested as evidence; do not recommend dependency versions or research cross-extension compatibility ranges. Optional usage may be explained in prose without inventing dependency edges.

## E04 — PostgreSQL compatibility and reuse

Follow [F08](../functional/functional-policy.md#f08--each-advertised-extension-combination-works). Record the exact build target separately from tested runtime minors. Reuse identical archive bytes only after verification on each advertised minor. Test each directly installable SQL version with the packaged library. Broader version ranges require evidence.

The build strategy is an implementation choice documented in [the build-reuse item](../functional/items/planned/extension-build-reuse.md).

## E05 — Packages and resources

Include upstream control files, installation/update SQL, native modules, applicable licences and required runtime resources. Apply [F09](../functional/functional-policy.md#f09--resource-scope-follows-the-schema-task) to retain small defaults and exclude large external application/admin datasets. Identify affected operations and loading procedures. Removing a default requires a reason, measured saving and behaviour tests.

## E06 — Item content and completion

Use this order in an extension item:

1. SQL name, purpose, source and licence; reason for selection or deferral.
2. Release sources, expected PostgreSQL ranges and departures from shared build rules. Distinguish source versions, SQL versions and verified combinations.
3. Declared SQL dependencies, libraries, activation settings, resources and data-loading procedures.
4. Schema/API transitions, with examples explaining why a migration might require an exact version.
5. Verification evidence, limits, extension-specific tests and unresolved choices.

Cite tagged sources where possible and identify moving documentation. Update structured constraints when research changes machine decisions; keep exact results in verification records.

Completion requires working recipes and independently usable packages for the item's stated scope, with exact versions, obligations and successful [build, artifact and consumer verification](../testing/testing-policy.md). Keep release-by-release results in coverage records. A pilot pass on one combination does not complete an item covering the full intended offering.

Follow [the writing guide](../../style.md). If an item is based on specific policies, cite them.
