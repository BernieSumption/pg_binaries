# pg_cron macOS selected publication trial

Created 2026-10-19 to exercise the selected macOS publication path for pg_cron 1.6.8 with PostgreSQL 18.6.

The question is whether the selected workflow can resolve a checked core archive, build pg_cron on a native macOS runner, and verify the resulting archives on a fresh native runner for both architectures. The trial starts with arm64 because it is the existing publication target; manual dispatch can select x86_64 after registration. This runner separation cannot be established by the existing same-run feasibility script, so the selected workflow is needed to test it.

`target.json` selects project `pg_cron`, version 1.6.8, PostgreSQL 18.6, and `macos-arm64`. It does not pin a core archive hash or run ID. The checked core resolver writes those values to its temporary `target.json` after it reuses or builds an eligible core archive.

Retire this trial request and its push trigger after the arm64 run completes and the shared selected-extension dispatcher routes pg_cron macOS requests to this workflow. Keep the selected workflow and its target configuration in their owning locations.
