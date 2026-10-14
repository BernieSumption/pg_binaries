# Specification

## Purpose and boundary

This repository supplies PostgreSQL binaries, extension binaries and download metadata for schema migration tools. A tool reads its SQL files upfront, identifies required extensions, and asks a separate client library to obtain an installation, start PostgreSQL and return a connection.

We provide standard binaries runnable through ordinary shell and process tools. SQL parsing, version-selection defaults, process lifecycle and connection APIs belong to the client. The database's short lifetime motivates small downloads; schema and DDL compatibility determine what those downloads must contain.

## Scope

- Every stable PostgreSQL release in majors **15 and later** published on or after **25 September 2025**. Apply the same inclusive, fixed cutoff to selected extension projects, including compatible maintenance releases of older lines.
- x86-64 Linux, Intel macOS and x86-64 Windows. Prioritize current OS support, preferably reaching back four years. Ignore older systems; narrow the window when older support compromises current support.
- Each selected SQL extension is independently downloadable with its required dependencies. For example, selecting PostGIS does not require its optional raster or TIGER modules.
- Relocatable binaries with bundled non-OS dependencies and resources needed for schema initialization and DDL. Exclude large external application/admin datasets; normally retain small upstream defaults.
- The client chooses PostgreSQL and extension versions. The catalogue supplies compatibility information without choosing defaults or silently substituting versions.

## Inventory, coverage and downloads

The **inventory** is the authored coverage policy: version ranges, platforms and capabilities we intend to offer. **Release discovery** expands that policy into exact upstream releases at a dated snapshot. A generated **coverage report** records progress, including failed builds and unresolved research. The **download catalogue** lists currently verified, publicly downloadable artefacts.

This separation keeps the definition of success stable while builds catch up. A missing download remains missing coverage.

## Versions and builds

Three decisions determine which archive a client downloads:

1. **Which releases we offer:** the inventory's cutoff and compatibility rules select upstream releases. See [release selection](inventory-format.md#1-release-selection).
2. **Which versions a client requests:** the client supplies its PostgreSQL and extension versions, using catalogue metadata to apply its own selection policy.
3. **Which build serves that request:** one extension archive may serve several PostgreSQL minors after verification on each. Metadata records its exact build target separately from its verified runtime range. See [artifact records](inventory-format.md#7-artifact-records-and-download-catalogue).

A packaging correction can replace the current archive without changing its upstream versions. New downloads receive the corrected build under a new checksum-bearing filename. See [corrected builds](functional.md#f11--corrected-builds-are-the-normal-download).

## Reading order

Review these three assets together:

1. [Functional specification](functional.md): guarantees and their reasons.
2. [Inventory JSON](inventory.json): intended scope, with [format reference](inventory-format.md) for field semantics.
3. [Testing specifications](testing/README.md): evidence required for each guarantee.

Then consult the documents relevant to a question:

| Document | Purpose |
| --- | --- |
| [Extension profiles](extensions/README.md) | Compatibility research, version transitions, dependencies and data |
| [Architecture](architecture.md) | Build, packaging, verification and publication responsibilities |
| [Product decisions](product-decisions.md) | Human review queue for scope and guarantees |
| [Implementation decisions](implementation-decisions.md) | AI-maintained technical rationale and research |
| [Pilot evidence](evidence.md) | Existing passes and their limits |
| [Capabilities](capabilities.md) | Optional PostgreSQL features, decisions, reasons and verification |
| [Writing guide](style.md) | Editorial rules |

## Authority and open work

The functional specification and inventory must agree. Architecture may change without weakening those requirements. [Product decisions](product-decisions.md) list unresolved scope choices for human review. Research findings and recommendations belong beside the relevant technical reasoning.

Unresolved OS baselines and compatibility ranges are recorded as `research_required` and block coverage completion. [Verification evidence](evidence.md) records implementation results and gaps.
