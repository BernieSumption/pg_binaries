# Release layout and publication

Clients obtain `inventory.json` from `https://github.com/BernieSumption/pg_binaries/releases/latest/download/inventory.json`. It lists public archives and their SHA-256 values in the format defined by [the functional specification](../specs/functional.md). A release becomes current only after every URL in its inventory is available.

## Names and immutable downloads

Each published release receives a new tag of the form `catalog-YYYYMMDD-N`, where `N` increases for multiple releases on one date. Archive names identify component, component version, PostgreSQL build version or verified support range, operating system and architecture, and end in `.tar.gz`. A release URL includes its tag and archive name. The SHA-256 in the inventory identifies the exact bytes. A corrected archive must receive a new URL; never replace or rename an asset at an existing URL.

The current inventory in the repository root is the source-controlled record of public availability. An unpublished candidate inventory must be kept separately and must not claim that temporary CI artifacts are public downloads. Each new release contains `inventory.json` and only the binary archives added or changed in that release. Unchanged inventory entries retain URLs on older tags; their assets must remain publicly available while referenced. A release tag or asset referenced by the current inventory must not be deleted or edited.

## Publication order

Generate a candidate inventory from intended support, verified archive bytes, and the existing public inventory. Check its schema, coverage claims, URLs, checksums, installation metadata, licences, and retained references. Upload new immutable archives and the candidate inventory to a new draft release. Check the uploaded assets and checksums while the draft is not the latest public release. Publish the draft as the latest release only after every referenced new and old archive is available. If an upload or check fails, leave the previous latest release intact; retry on a new tag if a published URL would otherwise change bytes.

Immediately after publication, run the anonymous download verification in [testing.md](testing.md) against the public `latest` inventory, including archives on older tags. Record the result and repair any failure with a new release and new URLs. A local dry run can test generation, ordering, retained references and failure handling, but it cannot establish public accessibility.

The existing workflows upload short-lived GitHub Actions artifacts and do not publish releases. No current pilot archive is therefore advertised by a root `inventory.json`. The local preflight validates candidate references, staged bytes and each new PostgreSQL archive's built-in extension declaration before any release operation; it is only one part of the publication checks above.
