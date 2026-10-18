# Windows pg_jsonschema candidate, run 39114804478

PostgreSQL 18.6 `pg_jsonschema` 0.3.4 passed the archive-suite and static-analysis gates on `windows-2022` (Windows 10.0.20348, image `win22/20261012.333.1`). The extension archive SHA-256 is `dd150f16b0f201ee65365833bc3cd2057592ffe9eb328979c675710d754d61c1`.

The record binds to PostgreSQL core archive SHA-256 `acba200dc61234fce48f75b0dd57b6e4392ca0c56ffe59448b8d1fe8b5d21b27`, pinned by core run 39095293644 (`github-39095293644-1`). This is archive-bound extension evidence for that exact core. Windows core run 39114737055 is rebuilding against the refreshed shared profile; once it passes, repin and rerun pg_jsonschema if the core archive bytes differ. This candidate does not satisfy the separate requirement for a passed current core verification record.

Source and test revision: `bbc22fa958fc544ce0e4410f1c6848d1dd2d0058`. Release eligibility remains false.
