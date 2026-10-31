# Human review queue

## Local build environments for concurrent agents

The user selected Fusion for Windows, retaining Docker for Linux and Lume for Mac. The remaining environment decision is whether each active agent gets its own environment, with practical concurrency limits. Separate workspaces isolate build files, but agents sharing a container or VM can still interfere through installed system dependencies.

The Fusion Windows guest now provides authenticated CLI commands and file transfer, and x64 PostgreSQL passed database startup and SQL smoke checks. Local compilation needs two human setup steps: the **Set up C++ build tools** desktop shortcut opens Microsoft's normal administrator installer with the project components selected; the verified Git ARM installer at `C:/Users/Public/Git-2.56.0.4-arm64.exe` needs an interactive attempt after unattended initialisation failed. Computer use still fails to connect, so the agent cannot handle those screens. Details and evidence are in [packages/LOCAL_ITERATION.md](packages/LOCAL_ITERATION.md#fusion-local-setup).

Local macOS x86 translation is still waiting for the human's Rosetta licence decision. The two-guest macOS limit makes separate workspaces in a shared development VM a practical candidate while retaining a clean verifier. Linux container and Mac workspace concurrency trials are recorded in the local iteration guide; Windows concurrency remains unmeasured. The guide distinguishes successful trials from routes blocked before testing.

## Compiled dependency caching

The remaining question is whether compiled dependency caching on GitHub is worth its implementation and maintenance cost once local iteration works. Local persistent workspaces now retain successful dependency installations through a harness-owned dependency phase; the implementation and measurements are recorded in `packages/LOCAL_ITERATION.md`.

The local measurements show substantial savings: macOS PostGIS took 417 seconds with a fresh dependency installation, 49 seconds on repeat, then 30 seconds after fixing repeated configuration. pg_jsonschema's corrected repeat build takes about 8.5 seconds. On a native Windows GitHub runner, pg_jsonschema took 585 seconds including initial Rust tooling and 33 seconds on repeat in the same workspace. These measurements establish the benefit of retained state, but do not measure how often developers will need GitHub rebuilds after local iteration is established or the cost of restoring state on another runner.

A possible GitHub implementation would restore and save dependency installations using the same dependency phase and input keys. Packages would remain unaware of the storage backend. Hosted jobs would need stable workspace paths or relocatable cached installations, along with cache-size and restore-time measurements. Compiler caching is a smaller alternative where dependency prefixes are difficult to reuse.

The provisional recommendation is to defer hosted compiled-dependency caching until local Windows and macOS x86_64 trials establish how much hosted iteration remains necessary. Existing workflows already support retrying one package against an existing PostgreSQL archive. If hosted iteration remains common, PostGIS is the first candidate for a measured cache experiment. Hosted caching has not been implemented.
