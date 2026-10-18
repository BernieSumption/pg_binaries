# Windows pgTAP selected-target CI trial

Created 18 October 2026 to test the new selected-target workflow on `spike`. GitHub cannot dispatch a workflow by filename while it exists only on this branch, so a commit changing `target.json` requests one selected PostgreSQL target through the workflow's scoped push trigger. The workflow validates the request against `support.json` before starting a Windows runner.

The input is the exact `postgresql_version` in `target.json`. After all four current PostgreSQL targets pass and the workflow can be dispatched normally, remove this experiment and its push trigger. Retain the results under `support/evidence/`.
