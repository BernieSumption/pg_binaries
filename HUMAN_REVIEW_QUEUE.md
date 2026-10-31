# Human review queue

## Local build environments for concurrent agents

The remaining decisions are which local environments to use, whether each active build agent gets its own environment, and practical concurrency limits. Separate workspaces isolate build files, but agents sharing a container or VM can still interfere through changes to installed system dependencies.

The Parallels assessment in `IMPLEMENTATION_STATUS.md` recommends a Pro trial starting with Windows 11 ARM. Whether to adopt it for Linux and Mac, retain Docker or Lume, and allocate one environment per agent remains undecided. The proposed experiment measures host memory pressure and useful build throughput before setting concurrency limits.

## Compiled dependency caching

The remaining question is whether compiled dependency caching on GitHub is worth its implementation and maintenance cost once local iteration works. Local persistent workspaces now retain successful dependency installations through a harness-owned dependency phase; the implementation and measurements are recorded in `packages/LOCAL_ITERATION.md`.

The local measurements show substantial savings: macOS PostGIS fell from 417 seconds with a fresh dependency installation to 49 seconds on repeat, and pg_jsonschema's corrected repeat build takes about 8.5 seconds. These measurements establish the benefit of local reuse, but do not measure how often developers will need GitHub rebuilds after local iteration is established.

A possible GitHub implementation would restore and save dependency installations using the same dependency phase and input keys. Packages would remain unaware of the storage backend. Hosted jobs would need stable workspace paths or relocatable cached installations, along with cache-size and restore-time measurements. Compiler caching is a smaller alternative where dependency prefixes are difficult to reuse.

The provisional recommendation is to defer hosted compiled-dependency caching until local Windows and macOS x86_64 trials establish how much hosted iteration remains necessary. Existing workflows already support retrying one package against an existing PostgreSQL archive. If hosted iteration remains common, PostGIS is the first candidate for a measured cache experiment. Hosted caching has not been implemented.
