# Planner to CI dispatch trial

Created 19 October 2026 to check that one exact planner request can select a declared work closure and dispatch its HypoPG Linux target through the reusable publication workflow. The trial addresses the integration between planner output and a CI entry point without adding a general queue runner.

The workflow reads `target.json`, runs `tools/dispatch_plan.py`, and dispatches only HypoPG targets on `linux-x86_64` or `linux-arm64` when the plan says work is needed. The selected workflow receives the exact PostgreSQL release, HypoPG release and Linux architecture from the plan. Its build and verification jobs remain responsible for the target execution.

The input is one exact project, extension version, PostgreSQL release and platform, with an optional retry flag. The first run requested a retry of HypoPG 1.4.3 on PostgreSQL 17.11 for `linux-x86_64`. The second request leaves retry false to test ordinary planning and checked retrieval from a coordinator run.

The second run passed but found an older standalone HypoPG artifact before checking the prior coordinator artifact. The resolver now checks coordinator artifacts first when called from this workflow. [The third run](../../support/evidence/planner-dispatch-linux-hypopg-39178721895.md) passed and reused the preceding coordinator's checksum-verified core artifact. It took 98 seconds and independently imported its final-archive evidence.

The trial's question is answered. Retire its workflow and request after moving the proved planner-to-CI behavior into the permanent entry point. General target routing and planner-level archive discovery remain separate work.
