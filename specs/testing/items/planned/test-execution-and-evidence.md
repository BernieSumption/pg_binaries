# Test execution and evidence

Implement the records required by [TEST05](../../testing-policy.md#test05--keep-a-record-of-what-passed-and-failed) and the repeatable checks required by [TEST08](../../testing-policy.md#test08--make-the-checks-repeatable). These shared details apply to build, archive, consumer and coverage tests.

## Test records

For each build or test of an archive, record:

- The inventory and release-discovery revisions, test revision and timestamps.
- Build IDs, recipe revision, source identities, and archive/dependency SHA-256 values.
- Exact PostgreSQL, SQL extension and native-library versions.
- OS release, edition and patch level; architecture and CPU capabilities; libc
  version on Linux; locale inventory and relevant preinstalled runtimes.
- Commands, results and retained diagnostic logs, including failures.

For tests of metadata alone, record input and fixture revisions, timestamps,
commands and results. Omit binary and runtime fields.

Build records additionally identify source URLs and hashes, patches, toolchains,
SDKs, dependency inputs and effective build options. Consumer records include
the request and catalogue revision. [Metadata fields](../../../functional/functional-inventory-format.md)
connect these records to the downloadable bytes.

## Feature and extension fixtures

Test each SQL extension with explicitly selected prerequisite versions, recording
the exact combination. Optional operation fixtures may select additional modules.
These results establish no compatibility with other dependency versions; no
dependency-version matrix or general resolver is required.

[Build items](../../../build/items/) identify the observations required for
each feature. Build checks establish its configuration and dependencies; artifact
tests establish behaviour after relocation. Tests proposed for unresolved features
apply only if those features are selected. Unmeasured sizes do not fail acceptance,
and no capability requires paired builds solely to measure its size.

## Running the checks

Run all local compilation and tests of compiled binaries inside Docker. The host
may inspect files and validate metadata. Use standard free GitHub-hosted runners
for native macOS and Windows tests. If available runners cannot demonstrate a
required OS or runtime condition, record the evidence gap.

Set explicit job timeouts, scope expensive jobs to affected targets, and retain
compact logs and verification records. Give temporary archives short, explicit
retention. Repeat tests to address changed inputs, failures, unresolved risks or
required acceptance checks.

## Completion

Connect record collection to the repository test commands and CI jobs. Demonstrate that successful and failed runs retain the required inputs, commands and results, and that records identify the exact tested archives. Verify that metadata-only runs omit inapplicable binary fields.
