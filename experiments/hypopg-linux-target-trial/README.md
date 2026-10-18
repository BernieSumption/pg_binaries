# Linux HypoPG selected-target trial

Created 18 October 2026 to exercise one selected HypoPG target through the standalone Linux publication workflow on `spike`. The trial checks whether shared target selection, the existing Linux build scripts, Alpine verification, and the publication evidence importer work together without building unrelated extensions.

The workflow reads the exact PostgreSQL minor from `target.json` for the scoped `spike` push trigger. A manual dispatch may provide a PostgreSQL minor and optional HypoPG version. `extension_archive_plan.py` must select the requested `linux-x86_64` target from `support.json` and the retained PostgreSQL release snapshot before a runner starts building.

The workflow retains build and verification outcomes even when a step fails or is skipped. When both final archives and a verifier image identity are available, it creates a checksum-bound receipt and record, imports them into the checkout, and uploads the archives and imported evidence as a short-lived Actions artifact.

After the selected target has passed and the trial can be dispatched normally, remove this experiment and its scoped push trigger. Keep useful results under `support/evidence/`.
