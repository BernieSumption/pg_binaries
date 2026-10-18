# pgTAP macOS arm64 selected-target trial

Created 18 October 2026 to consolidate the four fixed PostgreSQL target publication workflows into one selected-target workflow on `spike`. The workflow validates the requested pgTAP and PostgreSQL releases, loads the existing PostgreSQL pin for that release, and preserves the current native build, archive checks, and publication evidence import.

The inputs are the exact PostgreSQL release in `target.json` for the scoped push request, or the PostgreSQL and optional pgTAP releases supplied to a manual dispatch. `extension_archive_plan.py` must accept the selected tuple and the existing macOS arm64 pin must match it. All four currently pinned PostgreSQL releases passed with archive-bound evidence retained under `support/`. The scoped request file remains in use while this workflow is available only on `spike`; remove the experiment when planner-driven dispatch can select and retry targets without this push request.
