# Testing notes

This file maps guarantees to observations and records gaps affecting several test items. The [testing policy](testing-policy.md) defines acceptance; individual procedures live in items.

## Requirement map

| Requirement | Main observations |
| --- | --- |
| FUNC001 — Version coverage | Discover every eligible release; retain failed and unresolved targets. |
| FUNC002 — Exact choices | Preserve requested source, PostgreSQL and SQL versions; report absence or ambiguity. |
| FUNC003 — Independent modules | Install each module with its required closure; check ownership and omit unrelated downloads. |
| FUNC004 — Relocation | Audit CPU flags; run as an ordinary user in two locations on required OS environments. |
| FUNC005 — Tools and schemas | Initialize UTF-8, apply DDL, inspect catalogues, dump/restore schema and stop cleanly. |
| FUNC006 — Collations | Exercise ICU and available libc locales; record provider and locale availability. |
| FUNC007 — Capabilities | Audit options and test every included capability, including applicable compression operations. |
| FUNC008 — Extension combinations | Verify SQL/library identity and operations on every advertised PostgreSQL minor with required dependencies. |
| FUNC009 — Resources | Run offline with bundled resources; document exclusions and affected operations. |
| FUNC010 — Inspectable archives | Compare manifests; reject corruption, unsafe paths, file conflicts and missing dependencies. |
| FUNC011 — Corrected builds | Resolve the current build, detect stale caches and check consistent publication. |
| FUNC012 — Redistribution | Audit component obligations, retain required texts and download without payment or authentication. |
| FUNC013 — Metadata completeness | Check structured constraints, scoped notes and dated discovery/coverage records. |

## Pilot evidence and gaps

The [evidence summary](testing-evidence.md) records the pilot's passes and limits.
Outstanding work includes release coverage, independent PostGIS module downloads,
OS baselines and complete capability checks. In particular, the Windows server
runner supplied a Visual C++ runtime, and older GEOS/SFCGAL dependencies limited
the PostGIS pilot. Neither result establishes the full new contract.
