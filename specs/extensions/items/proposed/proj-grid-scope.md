# PROJ grid scope

**Decision:** What offline coordinate-transformation coverage should PostGIS provide, and which optional PROJ grids does it require?

Bulk TIGER Census records are excluded application data. Some PROJ grids can instead be needed when DDL evaluates a transformation. Retain ordinary runtime resources; decide the grid scope using the [resource research](../../extensions-notes.md) and [F09](../../../functional/functional-policy.md#f09--resource-scope-follows-the-schema-task).

**Recommendation for review:** Retain ordinary PROJ resources and bundle grids needed for explicitly advertised offline transformations. Document affected operations and exclusions. Establish that operation set before changing the guarantee; this proposal does not authorize excluding arbitrary data-dependent DDL.

## Review context

FEEDBACK: is this just TIGER or are there other ones with big data inside?
