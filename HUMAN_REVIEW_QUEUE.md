# Human review queue

The Linux compatibility proposal below needs human review before adoption. Candidate builds can be tested while the decision is pending.

## Local build environments for concurrent agents

The remaining decisions are which local environments to use, whether each active build agent gets its own environment, and practical concurrency limits. Separate workspaces isolate build files, but agents sharing a container or VM can still interfere through changes to installed system dependencies.

The Parallels assessment in `IMPLEMENTATION_STATUS.md` recommends a Pro trial starting with Windows 11 ARM. Whether to adopt it for Linux and Mac, retain Docker or Lume, and allocate one environment per agent remains undecided. The proposed experiment measures host memory pressure and useful build throughput before setting concurrency limits.

## Compiled dependency caching

Whether to add compiled dependency caching remains undecided. Fresh workspaces currently rebuild source-built private dependencies. Dependency preparation needs separate timing before choosing a cache scope; the recorded whole-build timings do not establish the likely saving.

If the measurements justify caching, its first scope and build-harness contract need agreement. Package-specific relocation requirements and reliable invalidation affect the cost. This decision does not block milestone 6.6.

One proposal is for the harness to own the cache and prepare `build/dependencies/` before the extension build. A package would expose a separate dependency-build step with no cache logic. The harness would key successful dependency installations by their sources, dependency-build instructions, target, toolchain and settings, restoring a cached installation or running that step on a miss. Local environments would retain the cache directory; GitHub workflows would restore and save that same directory between runs. The package would use the same contract in both environments. Cached installations would still need to work at the new workspace path.

A smaller alternative is compiler caching configured by the harness, reusing object compilation while retaining configuration and installation steps. The choice between these approaches, or deferring both, remains open. No caching implementation is authorised as part of milestone 6.6.

## Proposed Linux libpq and GDAL symbol-binding fix

The new verifier found a pre-existing conflict beyond PCRE2: the PostgreSQL backend and libpq export different `lo_read` and `lo_write` functions with incompatible signatures. Actual ARM64 loader traces showed libpq's calls binding to the backend functions. GDAL also imports the client functions, so fixing libpq's internal calls alone is insufficient.

The candidate keeps libpq's internal calls local, adds `pg_binaries_libpq_lo_read` and `pg_binaries_libpq_lo_write` as aliases for its client functions, and changes GDAL's two undefined imports to those aliases. Both original public APIs remain exported; the aliases have the original client functions' addresses. The PostgreSQL loader and GDAL's features remain unchanged. Only a private GDAL copy is patched, using pinned PatchELF 0.18.0 built from a declared source archive.

The candidate is implemented on the review branch in commits `105de9ca` and `bdeb4ae7`. Both Linux targets pass PostgreSQL alone, each of nine extension packages and the complete installation. Fresh backend processes also pass the Address Standardizer/PostGIS load orders in both directions: loader traces confirm GDAL's aliases bind to libpq, and SQL probes and a backend large-object round trip succeed. Original failures and prototype evidence are retained under `out/milestone-6.6/verification-first/`; final reports and load-order evidence are under each Linux target in `out/milestone-6.6/`.

Please decide whether to adopt this compatibility fix. It avoids rebuilding GDAL from source or changing existing public function names, but adds two Linux-specific aliases, a pinned build tool and a GDAL import rewrite to maintain. Another dependency loaded into the backend and importing these client functions would need the same treatment. The static PCRE2 policy and fix are independent. Without this candidate, the new verifier continues to reject the existing Linux libpq/GDAL combination. Candidate validation does not constitute approval.
