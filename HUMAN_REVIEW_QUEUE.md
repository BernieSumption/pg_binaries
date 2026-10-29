# Human review queue

No pending decision blocks the current local builds.

## Local build environments for concurrent agents

Linux currently reuses one retained development container with a broad set of installed dependencies. Builds now use separate workspaces and private PostgreSQL installations. macOS uses retained Lume build VMs and a separate clean verification VM. Package dependency preparation is callable per component on GitHub runners and locally. Agents sharing an environment can still interfere through changes to installed system tools and dependencies.

The proposed default is one development environment per active build agent. On Linux, each agent creates a container from the prepared image. On macOS, each agent clones the Lume base VM, then prepares the dependencies for the packages it builds. The agent retains installed tools and download/compiler caches across iterations; each build starts with a clean workspace. A separate clean environment verifies final archive bytes. This isolates changes to the build environment without repeating dependency installation on every attempt.

Please review this default and set a practical limit on concurrent Lume VMs and containers after measuring clone or container startup, dependency preparation, a repeated build and host memory use with two builds running. The existing shared Linux container remains useful for serial work until this decision is made. This decision does not block the Mac and Linux script refactor.
