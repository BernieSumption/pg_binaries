# Functional notes

AI-maintained technical context for the functional board. Durable implementation choices and their evidence belong in items; unresolved scope choices belong in `items/proposed/`.

## Design overview

The [architecture](functional-architecture.md) describes shared component recipes, platform adapters, packaging and verification. The [metadata format](functional-inventory-format.md) defines policy inputs and generated records. Their implementation remains in the planned queue until its completion criteria are met.

The [pilot evidence](../testing/testing-evidence.md) records narrow passes and known gaps. It does not establish completion of the broader inventory or current policy.

## Further research

Exact OS baselines, runtime closure and complete contrib coverage remain unresolved. Keep evidence in the corresponding items so later agents can continue without repeating work. Changes to policy require a proposal; routine choices that preserve the guarantees can be resolved from sources and tests.
