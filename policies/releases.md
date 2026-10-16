# Release layout and publication

Clients obtain `inventory.json` from `https://github.com/BernieSumption/pg_binaries/releases/latest/download/inventory.json`. It lists public archives and their SHA-256 values in the format defined by [the functional specification](../specs/functional.md). A release becomes current only after every URL in its inventory is available.

## Names and immutable downloads

Each published release receives a new tag of the form `catalog-YYYYMMDD-N`, where `N` increases for multiple releases on one date. Archive names identify component, component version, PostgreSQL build version or verified support range, operating system and architecture, and end in `.tar.gz`. A release URL includes its tag and archive name. The SHA-256 in the inventory identifies the exact bytes. A corrected archive must receive a new URL; never replace or rename an asset at an existing URL.

The current inventory in the repository root is the source-controlled record of public availability. An unpublished candidate inventory must be kept separately and must not claim that temporary CI artifacts are public downloads. `tools/candidate_inventory.py` generates a structural draft from explicit base inventory, proposal, intended-support, and release-snapshot files; its output is not a publication claim. Each new release contains `inventory.json` and only the binary archives added or changed in that release. Unchanged inventory entries retain URLs on older tags; their assets must remain publicly available while referenced. A release tag or asset referenced by the current inventory must not be deleted or edited.

## Publication order

Generate a candidate inventory from intended support, verified archive bytes, and the existing public inventory. Check its schema, coverage claims, URLs, checksums, installation metadata, licences, and retained references. Upload new immutable archives and the candidate inventory to a new draft release. Check the uploaded assets and checksums while the draft is not the latest public release. Publish the draft as the latest release only after every referenced new and old archive is available. If an upload or check fails, leave the previous latest release intact; retry on a new tag if a published URL would otherwise change bytes.

Immediately after publication, run the anonymous download verification in [testing.md](testing.md) against the public `latest` inventory, including archives on older tags. Record the result and repair any failure with a new release and new URLs. A local dry run can test generation, ordering, retained references and failure handling, but it cannot establish public accessibility.

The existing workflows upload short-lived GitHub Actions artifacts and do not publish releases. No current pilot archive is therefore advertised by a root `inventory.json`. The local preflight validates candidate references, staged bytes and each new PostgreSQL archive's built-in extension declaration before any release operation; it is only one part of the publication checks above.

## Redistribution review before publication

Every new staged archive must include `<root>/LICENSES/inventory.json` with `schema_version: 1` and a non-empty `components` list. Each component must identify `component`, `version`, non-empty archive-relative `payload_paths`, and `license_file`; `additional_license_files` may list further required texts and notices. Licence paths are relative to `LICENSES`, or may start with `LICENSES/`. Declared evidence must be included as non-empty regular files. Payload paths must identify an archive member or a directory containing members. The gate reads archive members without extracting them and rejects duplicate members and unsafe paths.

Each component must have `redistribution_review` with `status: resolved`, a non-empty `basis` describing the reviewed terms and their application to this distribution, and one explicit `source_obligation`:

- `none`: the review found no source-delivery obligation for this distribution.
- `source-links`: `source_links` must list public HTTPS URLs for the source required by the reviewed terms, including applicable modifications and build material.
- `source-offer`: `source_offer_file` must identify an included non-empty offer text under `LICENSES`.

A pending, blocked or absent review fails preflight. Existing provenance fields such as `source_url`, `source_urls` and `license_source` do not establish a resolved review or satisfy the explicit source-link declaration. Reviewers must determine which texts, notices, source material or offers the terms require and record the disposition; adding a URL alone does not resolve those obligations.

`tools/publication_preflight.py` accepts paths to the base and candidate inventories, intended support, release snapshot, and staged-assets manifest; it checks these declarations and local evidence against the staged archive bytes. Its `redistribution_review_status: declarations-checked` result establishes structural completeness only. It does not determine whether a licence interpretation is correct, whether every redistributed component has been identified, whether a source offer is legally sufficient, or whether a source URL is available and supplies all required material. Those remain publication checks under the publication order above. Retained archive references are not re-reviewed by this local gate.

Current pilot licence inventories use several formats and generally omit explicit redistribution reviews; some archives have only licence texts. They must be normalized and reviewed before passing this gate. Their existing provenance and passing runtime tests do not establish publication eligibility.
