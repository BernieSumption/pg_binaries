# pg_jsonschema selected Linux trial

Created 2026-10-19. This trial checks whether the selected-target workflow can build one declared `pg_jsonschema` Linux target and verify the final archive bytes on a fresh runner.

The workflow derives the extension release from `support.json` and the retained PostgreSQL release snapshot. Its default PostgreSQL version and architecture come from `target.json`; manual inputs can select another supported Linux target.

The trial uses the existing Linux pg_jsonschema recipe, Alpine verifier, publication evidence emitter and importer. Its resolver checks available PostgreSQL core archives against source and builder inputs, or builds a new core when none match. The build transfers the exact core archive and a provenance record to the fresh verifier. [Fallback and checked-reuse runs](../../support/evidence/pg-jsonschema-linux-dynamic-core-2026-10-19.md) passed for PostgreSQL 17.11 x86-64. After the other selected Linux targets pass, move the workflow to its permanent location or retire this trial entry point.
