# Validate recipe and packaging boundaries

Before fixing recipe interfaces, build an older selected PostgreSQL major, an older eligible extension line and the standalone source projects. Demonstrate extension reuse, separate PostGIS packages, operation without preinstalled non-OS runtimes, and measured download sizes. These experiments can refine adapters and file ownership while preserving the functional guarantees.

## Completion

Record the tested source versions, platforms, package ownership and runtime dependencies. Use the results to revise the [architecture](../../functional-architecture.md) without weakening the functional guarantees. Keep exact results in verification records.
