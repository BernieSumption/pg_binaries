# Delivering declared support

Clients need the PostgreSQL and extension releases selected by [the functional specification](../specs/functional.md#determining-postgres-and-extension-versions-to-support). A support target identifies an exact PostgreSQL release, optional extension project and release, operating system and architecture. The support declaration records intended targets; `inventory.json` describes public downloads with applicable verification evidence.

## Declare and reconcile support

At each version refresh, consult upstream release sources for PostgreSQL and every included extension. Record the research date, sources, PostgreSQL support status, exact releases, and the first-release dates of extension majors needed for the two-year rule. Select the latest stable minor of each upstream-supported PostgreSQL major from 15 onward, and apply the specification's extension rule separately for each selected core. Include the latest patch within a selected extension minor. Interpret the two-year window using when the major was first released, not its latest patch date.

Record upstream PostgreSQL and platform restrictions and required extension versions. Resolve prerequisites before planning builds. The specification allows the closest practical selection when upstream PostgreSQL compatibility prevents the exact rule; document that constraint and the resulting choice. Do not add older versions solely because of suspected DDL breaks, annual minor cadence or the former release-date cutoff. Selection does not promise reproduction of every historical schema behaviour.

`support.json` and the retained discovery snapshot are the machine-readable inputs to target selection. Keep selection data in one place; workflows and tests must not maintain independent version lists. Represent selected extension/core combinations rather than multiplying every selected extension version across every core it could theoretically support. Existing OS subset declarations remain subject to upstream evidence; an unbuilt required target stays visibly unmet.

Reconciliation compares the selected targets, available candidates, public inventory and verification evidence. Report missing archives, missing or failed verification, and missing public downloads separately. Superseded releases and expired selections leave the intended set through an explicit recorded refresh, not by suppressing build failures. Existing evidence remains historical. A new inventory omits downloads no longer selected and preserves URLs for unchanged downloads still selected.

## Plan builds and checks

Plan native PostgreSQL extension builds against the selected core for each supported major and platform. A source project supporting multiple majors does not establish that one binary works on all of them. SQL-only packages may share unchanged files across selected cores when their scripts and dependencies support those cores. Any reused archive must pass the checks for every selected core it serves; no historical-minor range search or minimum-build optimization is required.

Show proposed work and prerequisite dependencies before expensive CI dispatch. Keep build recipes and tests usable for a bounded target so a platform-specific failure can be investigated without rebuilding every unrelated extension. Retain exact core artifacts and development files when needed by subsequent extension builds, with source, configuration and checksum identity. The workflow layout is not yet selected: a plan job followed by core builds and parallel extension jobs is one candidate, alongside simpler grouped jobs. Evaluate retry cost, setup overhead, prerequisite ordering and artifact retention before adopting it.

Use standard GitHub-hosted runners and record failed or skipped work. Retain compact build and verification records beyond temporary artifact expiry, sufficient to retrieve or rebuild the corresponding package. Reuse applicable archives and test evidence; rebuilding is acceptable where it is simpler than managing reuse. [The testing policy](testing.md) defines evidence eligibility independently of job grouping.

## Publish verified downloads

An archive becomes eligible only when its final bytes satisfy the testing, installation and redistribution policies. Generate the candidate inventory from the current selected targets and eligible archives. Preserve existing URLs only for entries that remain selected. Every referenced archive must be available before making the inventory current, following [releases.md](releases.md), then run anonymous public-download checks.

For example, when discovery selects PostgreSQL 18.7 instead of 18.6, its five platform targets replace the old core targets. Re-select compatible extension releases for 18.7, build or reuse their packages, and test them with the exact new core archives. Unchanged selected downloads retain their URLs. The new inventory no longer advertises 18.6 merely because it appeared in the previous inventory.

The first release must satisfy the revised full scope; no temporary Linux-only subset has been authorized. Permanent release publication still requires the user's authorization. Until then, candidate archives remain visibly unpublished and the public inventory must not contain temporary Actions URLs.

## Implementation transition

The current `support.json`, release snapshot and coverage selector apply the revised version rule, but the planners, verification profiles and publication checks still contain historical-minor range assumptions. The pilot scripts implement selected core/extension paths; there is no complete publication orchestrator. Candidate generation and preflight also need to allow policy-driven retirement of old inventory entries while preserving retained URLs and rejecting missing selected targets.

[The migration backlog](../GOAL_BACKLOG.md#version-policy-migration) names the required metadata, planner, verifier, publication and workflow updates. [Retained implementation history](../support/evidence/policy-transition-history-2026-10-17.md) records prior range and OS-endpoint experiments. Their success does not require continuing those experiments or prove current publication readiness.
