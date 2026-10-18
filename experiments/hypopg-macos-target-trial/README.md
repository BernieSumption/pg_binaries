# HypoPG macOS arm64 selected-target trial

Created 18 October 2026 to exercise one selected HypoPG target through a parameterized macOS arm64 publication workflow on `spike`. The trial checks selected-target planning, exact PostgreSQL core pin retrieval, final archive construction on one runner, fresh-runner static and SQL verification, and archive-bound evidence import.

The scoped push request uses the exact PostgreSQL minor in `target.json`. A manual dispatch accepts a PostgreSQL minor and optional HypoPG release; `extension_archive_plan.py` must select that target for `macos-arm64`, and the workflow must find its matching retained core pin before starting the macOS build.

After the selected target passes and the workflow can be dispatched normally, remove this experiment and its scoped push trigger. Retain useful results under `support/evidence/`.
