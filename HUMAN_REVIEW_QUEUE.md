# Human review queue

## Local build environments for concurrent agents

The user selected Fusion for Windows, retaining Docker for Linux and Lume for Mac. The remaining environment decision is whether each active agent gets its own environment, with practical concurrency limits. Separate workspaces isolate build files, but agents sharing a container or VM can still interfere through installed system dependencies.

Fusion now supports tested CLI template creation, rapid APFS template copies and independent headless guest operation. A deployed VM compiled an x64 program and used HTTPS while the development VM continued compiling. Two small builds in separate workspaces within one two-CPU, 4 GiB VM took 29.76 seconds serially and 20.47 seconds concurrently. The current proposal is to retain a prepared VM per active Windows agent, isolating system dependency changes and retaining its workspaces; coordinated workspaces in one VM remain an option for small builds. Multi-VM build throughput and practical resource limits remain to be measured. Details and evidence are in [packages/LOCAL_ITERATION.md](packages/LOCAL_ITERATION.md#fusion-local-setup).

Local macOS x86 translation is still waiting for the human's Rosetta licence decision. The two-guest macOS limit makes separate workspaces in a shared development VM a practical candidate while retaining a clean verifier. Linux container and Mac workspace concurrency trials are also recorded in the local iteration guide. The guide distinguishes successful trials from routes blocked before testing.

## Compiled dependency caching

The remaining question is whether compiled dependency caching on GitHub is worth its implementation and maintenance cost once local iteration works. Local persistent workspaces now retain successful dependency installations through a harness-owned dependency phase; the implementation and measurements are recorded in `packages/LOCAL_ITERATION.md`.

The local measurements show substantial savings: macOS PostGIS took 417 seconds with a fresh dependency installation, 49 seconds on repeat, then 30 seconds after fixing repeated configuration. pg_jsonschema's corrected repeat build takes about 8.5 seconds. On a native Windows GitHub runner, pg_jsonschema took 585 seconds including initial Rust tooling and 33 seconds on repeat in the same workspace. These measurements establish the benefit of retained state, but do not measure how often developers will need GitHub rebuilds after local iteration is established or the cost of restoring state on another runner.

A possible GitHub implementation would restore and save dependency installations using the same dependency phase and input keys. Packages would remain unaware of the storage backend. Hosted jobs would need stable workspace paths or relocatable cached installations, along with cache-size and restore-time measurements. Compiler caching is a smaller alternative where dependency prefixes are difficult to reuse.

The recommendation is to defer hosted compiled-dependency caching: all nine Windows extension packages now build locally, alongside the measured Linux and Mac ARM routes. Existing workflows already support retrying one package against an existing PostgreSQL archive. Local Mac x86 translation still needs licence approval; if hosted iteration remains common for that target, PostGIS is the first candidate for a measured cache experiment. The human decision is whether to accept deferral or prioritise that experiment. Hosted caching has not been implemented.
