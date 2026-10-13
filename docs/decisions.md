# Decisions for review

Status: open, 2026-10-13. A `REVIEW:` item asks for a human product choice. Implementation details such as compiler, CI provider, manifest syntax, or dependency packaging should normally be settled by the agent through evidence, not by the director in advance.

## Open now

**REVIEW: DISTRIBUTION-SERVICE** — Choose the primary free download service. **Proposal: GitHub Releases.** [Theseus](https://github.com/theseus-rs/postgresql-binaries/releases) publishes versioned archives there; [Zonky](https://github.com/zonkyio/embedded-postgres-binaries) uses Maven Central for Java artifacts. GitHub permits up to 1,000 assets per release, each under 2 GiB, with no stated total size or bandwidth quota ([GitHub documentation](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)). The user experience needed here is a direct download by PostgreSQL minor/platform/extension with licenses. An agent can run a GitHub Releases pilot before the final choice, and should report any size, reliability, or service limitation it encounters.

## Decide when implementation supplies evidence

**REVIEW: OS-RANGE-EXCEPTION** — The target is one binary per platform that works on today's OS and reaches roughly four years back where practical. If the pilot cannot cover that range with one binary, review the measured compatibility gap, number of likely affected users, and the cost of either shortening the range or adding a variant. Do not choose exact minimum OS versions without tests.

**REVIEW: POSTGIS-SCOPE-EXCEPTION** — Public PostGIS bundles include components beyond core geometry, such as raster, topology, and advanced 3D. Try a comparably useful set and present evidence if one component adds disproportionate portability or maintenance difficulty. Decide whether to include it, make it a separate optional download, or explicitly defer it.

**REVIEW: SCHEMA-CAPABILITY-EXCEPTION** — If a PostgreSQL build option or bundled component that realistic schema SQL uses proves hard to distribute, review the concrete SQL that would fail, the cost of supporting it, and alternatives. The goal is broad schema compatibility; implementation convenience alone does not justify silently dropping capability.

**REVIEW: EXTENSION-VERSION-LINES** — If an extension has application-significant major versions and more than one major supports a PostgreSQL minor, decide whether to offer parallel lines. Until that case arises, one selected latest compatible extension version per PostgreSQL minor is the rule.

**REVIEW: DISTRIBUTION-LIMITS** — Revisit the hosting decision only if actual archive size, asset count, reliability, or service terms obstruct the public download promise. Splitting downloads or adding a mirror may then be appropriate.
