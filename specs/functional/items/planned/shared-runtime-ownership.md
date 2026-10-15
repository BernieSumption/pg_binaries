# D06 — Shared runtime ownership

**F03 — packaging research.** Separate SQL downloads are required; shared-library ownership still needs implementation. Moving TIGER and address standardizer to standalone source projects changes intake and versioning while preserving their SQL identities.

A shared PostGIS runtime containing every optional library could erase the download savings from separate extensions. Measure dependency sets and sizes, then verify each package with only its required dependencies and explicit file ownership. See [extension items](../../../extensions/items/).

## Completion

Define file ownership and dependency manifests, then verify independently selected SQL modules with only their required runtime packages.
