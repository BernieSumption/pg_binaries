# pg_jsonschema selected Linux trial

Created 2026-10-19. This trial checks whether the selected-target workflow can build one declared `pg_jsonschema` Linux target and verify the final archive bytes on a fresh runner.

The workflow derives the extension release from `support.json` and the retained PostgreSQL release snapshot. Its default PostgreSQL version and architecture come from `target.json`; manual inputs can select another supported Linux target.

The trial uses the existing Linux pg_jsonschema recipe, Alpine verifier, publication evidence emitter and importer. Its core archive comes from the existing pinned run and hash in those evidence tools. Dynamic checked core selection remains a separate migration step. The trial is complete when a selected target produces a validated publication attempt and artifact in GitHub Actions. Move the workflow into the shared publication workflow set or remove it when the result is reviewed.
