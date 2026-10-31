# Human review queue

## Local build environments for concurrent agents

The proposal is one retained Docker container per Linux agent, one prepared Fusion VM per Windows agent, and separate workspaces in the shared Lume Mac development VM. The second permitted Mac guest remains a clean verifier. This isolates system dependency changes where separate environments are practical. The human decision is whether to adopt these defaults and whether measuring higher concurrency is worth further work.

A prepared Windows image copied and deployed in 0.02 seconds, excluding boot; its first Address Standardizer, Rust and PostGIS builds took 21, 46 and 168 seconds without rebuilding dependencies. Cached Windows iteration worked with two CPUs and 4 GiB. A four-worker cold PostGIS build needed nearly all of an 8 GiB guest. Two simultaneous heavy builds are the proposed starting point, not a measured maximum. Commands, resource evidence and the small-build concurrency trials are in [the local iteration guide](packages/LOCAL_ITERATION.md#development-loop).

## Compiled dependency caching

The recommendation is to defer hosted compiled-dependency caching. All five targets have a demonstrated retained local iteration route. Mac x86 trials include Address Standardizer, PostGIS and Rust, with unchanged repeats taking about 14, 114 and 19 seconds respectively; their final archives passed together in a clean VM. Hosted workflows can reuse PostgreSQL archives and unchanged packages. The human decision is whether to accept deferral or prioritise a measured hosted cache experiment.

A possible GitHub implementation would restore and save dependency installations using the same dependency phase and input keys. Packages would remain unaware of the storage backend. Hosted jobs would need stable workspace paths or relocatable cached installations, along with cache-size and restore-time measurements. Compiler caching is a smaller alternative where dependency prefixes are difficult to reuse.

Preserving Windows PostgreSQL's existing vcpkg binary cache is a smaller experiment: a fresh local install prefix restored all 12 packages in 2.7 seconds. PostGIS is the candidate for a broader dependency-prefix experiment if hosted iteration remains common. Neither cache is configured across GitHub jobs; restore cost and hit rate remain unmeasured.
