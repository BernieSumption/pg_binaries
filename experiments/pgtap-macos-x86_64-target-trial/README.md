# pgTAP macOS Intel selected-target trial

Created 19 October 2026 to check whether one selected-target workflow can replace the four PostgreSQL-specific macOS Intel pgTAP workflows. A push request file is needed because a new workflow on `spike` cannot yet be dispatched by filename through the GitHub API while it is absent from the default branch.

`target.json` selects one PostgreSQL release for the next trial. The workflow validates it against the declared support set and pins, builds the selected archive, then verifies its final bytes on a fresh Intel runner. Retire this request and the workflow's experiment-only push trigger after each selected target has a passing imported record and normal planner dispatch is available.
