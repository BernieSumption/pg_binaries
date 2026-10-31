# Human review queue

## Local build environments for concurrent agents

The remaining decisions are which local environments to use, whether each active build agent gets its own environment, and practical concurrency limits. Separate workspaces isolate build files, but agents sharing a container or VM can still interfere through changes to installed system dependencies.

Parallels is installed and the Windows installation media has downloaded. Actual Windows startup and Linux/macOS guest creation commands are blocked by a Pro/Business edition requirement; computer control also fails to connect. Parallels activation needs resolving before those routes can be compared. Local macOS x86 translation is waiting for the human's Rosetta licence decision.

Docker and Lume build, cache and concurrency trials are recorded in [packages/LOCAL_ITERATION.md](packages/LOCAL_ITERATION.md). Whether to use Parallels for every OS, retain Docker or Lume, and allocate one environment per agent remains undecided. Both vendors document a two-guest macOS limit, making separate workspaces in a shared development VM a practical candidate while retaining a clean verifier. A headless Lume Linux/Rosetta trial also passed builds, clean SQL verification and restart/cache checks. Its timings were close to Docker Desktop's, with more setup troubleshooting; the provisional recommendation retains Docker Desktop for Linux until Parallels can be compared. The recommendation distinguishes measured results from routes blocked before testing.

## Compiled dependency caching

The remaining question is whether compiled dependency caching on GitHub is worth its implementation and maintenance cost once local iteration works. Local persistent workspaces now retain successful dependency installations through a harness-owned dependency phase; the implementation and measurements are recorded in `packages/LOCAL_ITERATION.md`.

The local measurements show substantial savings: macOS PostGIS took 417 seconds with a fresh dependency installation, 49 seconds on repeat, then 30 seconds after fixing repeated configuration. pg_jsonschema's corrected repeat build takes about 8.5 seconds. On a native Windows GitHub runner, pg_jsonschema took 585 seconds including initial Rust tooling and 33 seconds on repeat in the same workspace. These measurements establish the benefit of retained state, but do not measure how often developers will need GitHub rebuilds after local iteration is established or the cost of restoring state on another runner.

A possible GitHub implementation would restore and save dependency installations using the same dependency phase and input keys. Packages would remain unaware of the storage backend. Hosted jobs would need stable workspace paths or relocatable cached installations, along with cache-size and restore-time measurements. Compiler caching is a smaller alternative where dependency prefixes are difficult to reuse.

The provisional recommendation is to defer hosted compiled-dependency caching until local Windows and macOS x86_64 trials establish how much hosted iteration remains necessary. Existing workflows already support retrying one package against an existing PostgreSQL archive. If hosted iteration remains common, PostGIS is the first candidate for a measured cache experiment. Hosted caching has not been implemented.
