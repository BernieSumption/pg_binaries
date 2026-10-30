# Human review queue

No pending decision blocks the current local builds.

## Local build environments for concurrent agents

The remaining decisions are which local environments to use, whether each active build agent gets its own environment, and practical concurrency limits. Separate workspaces isolate build files, but agents sharing a container or VM can still interfere through changes to installed system dependencies.

Milestone 6.6's Parallels research will inform these decisions, including whether to retain Docker and Lume for some platforms. Limits need evidence about host memory pressure and useful build throughput with concurrent agents.

## Compiled dependency caching

Whether to add compiled dependency caching remains undecided. Fresh workspaces currently rebuild source-built private dependencies. Dependency preparation needs separate timing before choosing a cache scope; the recorded whole-build timings do not establish the likely saving.

If the measurements justify caching, its first scope and build-harness contract need agreement. Package-specific relocation requirements and reliable invalidation affect the cost. This decision does not block milestone 6.6.
