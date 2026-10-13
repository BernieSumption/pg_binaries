# Specification: outcomes and invariants

Status: draft, 2026-10-13. This document states what a user should be able to rely on. It does not prescribe compilers, build systems, archive internals, CI jobs, or repository code layout.

## Purpose

A developer tool must be able to download an exact PostgreSQL minor release for its platform, run it locally, and apply realistic schema and migration SQL with the extensions that schema needs. The project supplies binaries and a curated extension catalogue. A Rust API for consuming them is outside this repository.

## Version and platform coverage

1. Every **released minor version** of PostgreSQL majors **15, 16, 17, and 18** is available, including historical minors. An older minor remains available after a newer one is released. New minors join the collection after they are released.
2. Each offered PostgreSQL minor works on **x86-64 Linux, Intel macOS, and x86-64 Windows**. A user can identify and download the correct artifact without knowing the implementation of the build system.
3. There is one binary distribution per PostgreSQL minor and platform, rather than a separate distribution for every OS vintage. It must work on the current version of that OS. Support extends back roughly four years, perhaps five, while the same binary remains compatible and the older OS has meaningful developer use. The published support range must state what was actually verified. Linux support must name a meaningful compatibility baseline, since “Linux version” alone is ambiguous.
4. Published artifacts remain identifiable and retrievable. If the project rebuilds the same PostgreSQL minor because of a dependency or catalogue update, consumers can distinguish the rebuild from the earlier artifact; an existing published download never silently changes bytes.

## PostgreSQL capability

5. The binary behaves like a useful PostgreSQL installation for creating and examining schemas. Size reduction is subordinate to this goal. The project must not omit a capability that commonly changes whether schema or migration SQL can be accepted without documenting and reviewing that loss.
6. Both ICU and libc collation providers are usable. Schema SQL can create ICU collations, including supported ICU options and variations, and can create libc collations using locales available on the host. Exact sorting results and identical locale inventories across different operating systems or ICU versions are outside the guarantee.
7. Capabilities that a schema can request through ordinary PostgreSQL SQL or configuration, including relevant optional compression methods and bundled PostgreSQL extensions, are available or explicitly listed as unsupported. The project does not promise every upstream optional integration merely because it exists; the initial feature inventory is discovered and justified during implementation, with any material exclusion surfaced for review.
8. A download runs without relying on the builder's Homebrew installation, package manager, or other accidental local dependency. It includes whatever redistributable runtime files are necessary, or clearly states a normal OS prerequisite. Moving the extracted installation to another path does not break it.

## Extension catalogue

9. The catalogue starts with **pgvector and PostGIS** and grows over time. It is curated: each advertised combination of extension, exact PostgreSQL minor, and platform is built and verified. Unsupported combinations are shown as unavailable, never implied to work.
10. Treat each PostgreSQL minor as a separate extension compatibility target. For each extension and PostgreSQL minor, offer one selected extension release: the most recent upstream release that this project has verified to support that minor. Record the exact selection and make it visible to downloaders. Do not silently use different extension releases for the three platforms.
11. A user can combine the PostgreSQL distribution with each advertised extension download and use `CREATE EXTENSION` and representative extension features. Any extra required files or services are supplied or documented. A mismatch between an extension and the PostgreSQL distribution is detectable before it produces a misleading working installation.
12. Aim for PostGIS completeness comparable with established public bundles. The actual component set is determined by building and testing the candidate components, including core spatial types and likely raster, topology, advanced 3D, and related extensions. Any component left out is named with its user impact and reason. The [PostGIS Windows bundle](https://postgis.net/documentation/getting_started/install_windows/enabling_postgis/) is one comparison point, not a mandated recipe.
13. If a future extension has major versions with important application-visible differences, and more than one major supports the same PostgreSQL minor, consider publishing multiple extension lines. This is a deliberate future [review trigger](decisions.md), not part of the current one-version promise.

## Access, licensing, and project boundary

14. Downloads are publicly available without charge. Each PostgreSQL or extension binary download includes the applicable PostgreSQL/extension license text and the license texts for redistributed dependencies. Do not add an extension whose license does not permit free public redistribution.
15. The downloadable inventory exposes exact PostgreSQL minor, platform, selected extension version, available PostGIS components, support range, and known capability omissions. A future consumer project can discover those facts without scraping prose or guessing from a filename. The format and hosting service are implementation choices, subject to the [distribution decision](decisions.md).
16. The project delivers and maintains the binaries, extension catalogue, build utilities, and tests. It does not need to implement database lifecycle management or a Rust embedding API.
