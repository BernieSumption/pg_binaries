# pg_jsonschema selected Linux trial

Created 2026-10-19. This trial checks whether the selected-target workflow can build and verify one declared `pg_jsonschema` Linux target while reusing the shared PostgreSQL core candidate resolver.

The workflow derives the extension release from `support.json` and the retained PostgreSQL release snapshot. Its default PostgreSQL version and architecture come from `target.json`; manual inputs can select another supported Linux target.

The trial uses the existing Linux pg_jsonschema recipe, Alpine verifier, publication evidence emitter and importer. It is complete when a selected target produces a validated publication attempt and artifact in GitHub Actions. Move the workflow into the shared publication workflow set or remove this trial when its result is reviewed.
