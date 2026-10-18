# Windows HypoPG selected-target CI trial

Created 18 October 2026 to test the selected-target workflow on `spike`. The scoped push trigger runs when this request or its workflow changes. GitHub dispatches the workflow by filename after it exists on the branch; the `target.json` value selects the PostgreSQL release for push runs.

Change `postgresql_version` in `target.json` to request another selected release, or change `attempt` to rerun the same release. The selector ignores `attempt`. The workflow validates the target against `support.json` before starting a Windows runner. After the four currently selected PostgreSQL targets pass and the workflow can be dispatched normally, remove this experiment and its push trigger. Retain results under `support/evidence/`.
