# Metadata-only archive repack experiment

Created 2026-10-22. This one-off experiment checks whether 22 built first-release extension archives with known metadata omissions can be corrected without changing any packaged behavior. It adds `postgresql_version` to the 13 pgvector archives, or explicit empty `configuration_prerequisites` and `runtime_prerequisites` arrays to four HypoPG Windows archives, four pg_jsonschema Windows archives, and one pg_jsonschema macOS arm64 archive.

Inputs are one exact extension `.tar.gz` archive and the matching PostgreSQL archive basename recorded as `core_archive.basename`. The patcher accepts only those named project and platform cases. It validates PostgreSQL version, platform, and architecture against both basenames, requires root `metadata.json`, and refuses conflicting metadata values. It writes a separate output archive and checks that all other member paths, contents, types, modes, and link targets remain identical.

Run one archive at a time:

```sh
python3 experiments/metadata_repack/repack.py INPUT.tar.gz postgresql-17.11-linux-x86_64.tar.gz OUTPUT.tar.gz
```

Run the focused fixture test with:

```sh
python3 -m unittest experiments.metadata_repack.test_repack
```

Run the batch trial with:

```sh
python3 experiments/metadata_repack/batch.py
```

It reads `dist/first-release/candidate/proposed-entries.json` and `dist/first-release/archives`, and writes patched archives, one compact member proof per archive, a report, and current-profile derived verification records under the separate ignored directory `dist/first-release/metadata-repack-batch/`. It requires exactly 22 matching known defects and candidate checksums that match the input archive bytes. Stale verification records are listed in `report.json` and omitted from derived records. The focused batch fixture tests run with `python3 -m unittest experiments.metadata_repack.test_batch`.

The scripts never modify their source archives. The first batch retained 21 corrected archives with current-profile evidence in [the checked repack record](../../support/evidence/metadata-repack-2026-10-22/README.md); the pg_jsonschema macOS arm64 record was stale and needs a fresh run. Remove this experiment and its ignored outputs once the first-release candidate accepts the corrected archives. If metadata repacking becomes a recurring production operation, replace this one-off code with a reviewed production tool.
