# Planner to CI dispatch trial

Created 19 October 2026 to check that one exact planner request can select a declared work closure and dispatch its HypoPG Linux target through the reusable publication workflow. The trial addresses the integration between planner output and a CI entry point without adding a general queue runner.

The workflow reads `target.json`, runs `tools/dispatch_plan.py`, and dispatches only HypoPG targets on `linux-x86_64` or `linux-arm64` when the plan says work is needed. The selected workflow receives the exact PostgreSQL release, HypoPG release and Linux architecture from the plan. Its build and verification jobs remain responsible for the target execution.

The input is one exact project, extension version, PostgreSQL release and platform, with an optional retry flag. The first run requested a retry of HypoPG 1.4.3 on PostgreSQL 17.11 for `linux-x86_64`. The second request leaves retry false to test ordinary planning and checked retrieval from a coordinator run.

Finish the trial when a scoped push produces a valid plan and dispatches only the declared selected workflow target, or when the integration proves unsafe. Then remove the experiment workflow and request, and move any retained planner-to-CI behavior into its owning workflow or tool.
