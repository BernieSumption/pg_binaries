# Coverage and evidence checks

Check that discovery, test results and downloads account for the entire intended
inventory. These checks establish F01, F02, F08, F11 and F13 and expose remaining
requirements. Follow the [metadata contract](../../../functional/functional-inventory-format.md) and shared
[verification record rules](../../testing-policy.md#t02--verification-records).

## Discovery

Retain the inventory revision, UTC assessment date, upstream sources, exact
release/tag identities and publication evidence for each discovery snapshot.
Build success cannot determine which releases are discovered. Apply the fixed,
inclusive 2025-09-25 cutoff and PostgreSQL floor of 15, without an upper bound. Dates must come from
release evidence, rather than commits, version years or predicted schedules.

Metadata fixtures must cover:

- Inclusion on the cutoff and exclusion before it; exclusion of prereleases,
  PostgreSQL 14 and earlier. Include future majors once stable releases exist;
  extension compatibility for those majors requires its own evidence.
- Missing/conflicting dates, unknown tag schemes and failed source queries:
  preserve the evidence and report unresolved research.
- Actual release enumeration, including eligible maintenance releases of older
  lines. Do not invent absent minors or discard releases lacking a compatibility rule.
- Declared source-version ordering and exact SQL version strings. Unknown
  fields/enums and incompatible overlapping rules fail validation.
- Module moves between source projects: preserve source identities and require
  evidence for upstream module absence.
- SQL dependency names copied from applicable upstream control files; optional
  usage notes must not introduce inferred edges or version-selection rules.
- Exact tested SQL dependency versions retained as evidence, without generating
  cross-extension compatibility ranges.
- Empty OS ranges and null ABI/CPU minima: report unresolved support, never an
  unrestricted or passing range.

These fixtures need no compilation. Live discovery must also retain fetched
evidence and source errors.

## Targets and progress

Expand one core target per eligible PostgreSQL release/platform. Extension
targets additionally specify source release and directly installable SQL version.
Attach required OS/capability checks and the concrete dependency versions tested
to each target. Do not expand targets across SQL dependency-version combinations
or unrelated extension pairs.

Use `research_required`, `pending`, `build_failed`, `verification_failed`,
`verified_unpublished` and `available`, retaining attempts, reasons and test
results. `not_applicable` requires evidence of upstream incompatibility. A
missing port, build failure, unavailable runner or unknown dependency remains
incomplete work.

Report core and extension progress separately as available targets divided by
resolved applicable targets, alongside research counts and snapshot date. Mark
progress provisional while discovery or applicability is unresolved. Unknown
compatibility, a failed source query or zero denominator cannot yield 100%.
Filtered views must label their denominator and retain access to full totals.

Completion requires all applicable targets available, all required OS/capability
checks passed, and no unresolved scope, discovery, compatibility or licence
items. Availability additionally requires a current public download check.
A local pass can establish only `verified_unpublished`.

## Reuse and support ranges

Keep exact build-against PostgreSQL versions separate from verified runtime
releases. Every advertised minor needs a passing result for the same extension
archive hash, including reused SQL/data packages. New minors start unverified.

Test range rendering with a failed minor between passes: split the range or list
exact passing releases. Expand ranges against the dated discovery snapshot so
new releases cannot inherit earlier results.

OS records must include the dated four-year assessment, claimed releases,
current/oldest tests and evidence for intermediate support. Narrowing must
record affected releases, reason and evidence. Windows Server with a CRT cannot
establish stock desktop support; unresolved Linux ABI and Intel macOS support
remain visible.

## Metadata completeness and retention

Check structured ranges, platforms, dependencies, activation and capabilities,
with notes scoped to the objects they explain. Machine-actionable requirements
expressed only in prose fail this check. Label intended policy, discovery, coverage and availability with their
own revisions/dates; expose unresolved rows without inventing a preferred version.

Retain verification records and replacement-build relationships for diagnosis.
Temporary archives may expire and superseded rebuilds need not remain public.
An expired artifact cannot remain `available`; its current replacement requires
matching metadata, bytes, tests and public download evidence for the same
requested upstream versions.

## Completion

Implement these checks under [T01–T05](../../testing-policy.md), connect them to the pipeline and retain verification records. See the [requirement map](../../testing-notes.md#requirement-map) for the guarantees they establish.
