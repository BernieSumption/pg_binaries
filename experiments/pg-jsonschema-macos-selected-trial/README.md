# pg_jsonschema selected macOS path trial

Created 19 October 2026 to test whether one target-driven workflow can build pg_jsonschema and verify its final archive with PostgreSQL on a separate macOS runner. The existing eight publication workflows duplicate the build and test sequence and run both phases in one job. A scoped push request is needed because GitHub cannot dispatch a new workflow by filename on `spike` while it is absent from the default branch.

`target.json` identifies one declared PostgreSQL release, pg_jsonschema release and native macOS architecture. The new workflow validates it against the support work queue and target configuration, builds the extension against the checked core artifact, transfers the final archives, then tests and imports evidence on a fresh runner. The first trial uses PostgreSQL 18.6 on arm64; the older workflow's profile run for this target was cancelled before building, so the selected trial avoids repeating that work.

Finish when the selected path passes on representative architectures and PostgreSQL versions, its exact artifact evidence is independently imported, and it can replace the eight release-specific workflows. Remove this experiment request and push trigger after the permanent planner can dispatch the selected target.
