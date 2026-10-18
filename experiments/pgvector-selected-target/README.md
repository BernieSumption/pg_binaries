# Selected Linux pgvector retry

Created 18 October 2026 to verify that a bounded retry of one selected PostgreSQL/pgvector target reuses a checked PostgreSQL core from a previous successful run. The new workflow exists on `spike` but cannot yet be dispatched by filename through GitHub Actions, so changing `target.json` triggers this trial through a narrow push path.

`target.json` supplies the exact PostgreSQL release and a positive attempt number. The workflow resolves the pgvector release from the support declaration and verifies the resulting archives. Increment `attempt` to repeat the same target without changing selection. Retire this experiment when planner-driven one-target dispatch and checked reuse work without a push request file; retain the trial results under `support/evidence/`.
