# Build and verification architecture

Maintainers need to add PostgreSQL and extension releases, build them for the supported platforms, and investigate failures in individual builds. These tasks must have a clear place in the codebase. Adding a release must not require copying workflows or updating separate lists of builds and tests. Investigating one failure must not require rebuilding unrelated extensions.

The system separates the declaration of what to support from the code that builds and tests it. Shared tools select the required work, run project-specific build procedures, verify the resulting archives and retain the results. GitHub Actions supplies the execution environments.

## Support declaration and planning

A build target identifies a PostgreSQL release, an extension project and release where applicable, an operating system, and an architecture. `support.json` and the retained upstream release snapshot determine the selected targets under [the delivery policy](delivery-process.md). Build and test code must consume this selection rather than maintain independent version or platform lists.

The planner compares selected targets with available archives and retained test results. It produces tasks to build missing archives and perform missing or outdated verification. Each task must identify its target and required inputs. Dependencies between tasks must be explicit: an extension build may need PostgreSQL development files, and verification needs the exact PostgreSQL and extension archives to assemble and test together.

The plan must be inspectable before expensive CI work starts. It must support selecting one target and its prerequisites so a failed build or test can be repeated independently. Independent tasks may run in parallel. Tasks may share a job when the setup savings justify the cost of repeating that job after a failure.

## Project build recipes

A recipe is the code and configuration needed to build and package one upstream project. PostgreSQL and each extension project have their own recipes. A recipe supplies the upstream-specific build steps, dependencies and packaging exceptions. It may select different procedures for different operating systems or PostgreSQL majors, with each difference scoped to the affected targets.

Share code for operations whose behaviour is common across projects, such as source retrieval, identity checks, packaging, component metadata and diagnostic collection. Where project or platform differences make sharing cumbersome, separate implementations may use common inputs and output formats. Prefer straightforward scripts and functions; introduce abstractions when they reduce demonstrated duplication or maintenance work. Recipes must accept a selected target without requiring a workflow edit and follow [the specification's source-modification rule](../specs/functional.md#do-not-devleop-our-own-patches-or-modifications-to-extensions-or-dependencies).

## Archive verification and results

The verifier assembles an installation from the final PostgreSQL, extension and prerequisite archives using [the installation procedure](install-process.md). Shared code must manage assembly, relocation, test execution and result collection. Operating-system-specific code must handle differences such as ELF, Mach-O and PE dependency inspection. [The testing policy](testing.md) defines the required checks and separation from the build environment.

Each project supplies SQL probes that create its advertised extensions and check representative DDL and behaviour. Reuse those probes across platforms and PostgreSQL versions. Add distinct cases only when a documented upstream interface or selected build capability requires them; platform differences must not silently reduce required coverage.

A verification profile defines the cases required for a particular claim. A verification record stores their outcomes and identifies the archive hashes, exact PostgreSQL and prerequisite archives, environment and test revision. Profiles and records must use shared formats. Common tools must write and validate records; project-specific code may supply additional checks and data. Failed and skipped cases must remain visible. Changes to a profile must invalidate affected evidence. Prefer invalidation by project and platform profile; rerunning a small suite is acceptable when finer dependency tracking would cost more to maintain. Refine this grouping where repeated checks become materially expensive.

## Archive and evidence reuse

The planner must recognise archives and verification records that remain applicable under [the delivery](delivery-process.md) and [testing](testing.md) policies. Matching a target's version and platform is insufficient: reuse must also account for relevant source, dependency, build-configuration and recipe changes. Retain enough build-input information to determine whether an archive still represents the intended build; rebuild when that cannot be established. Editorial changes need not invalidate a build.

Reuse also requires checking archive identity and availability; a retained record alone does not establish that its archive can still be retrieved. When the selected PostgreSQL minor changes, an existing extension archive may remain usable, but it requires verification with the new PostgreSQL archive.

Temporary Actions artifacts may supply inputs while available. If an artifact expires, retrieve the same checked bytes from another source or schedule a rebuild. Store run IDs and artifact locations as retrieval and provenance data, rather than embedding them in permanent target configuration.

## GitHub Actions workflows

Workflows must be parameterized entry points to the shared build and verification tools. A workflow accepts or derives selected targets, arranges their execution and retains outputs. Adding a project release or target must not require another copy of a publication workflow.

Use a small set of workflows organized by execution requirements. Separate jobs or workflows where operating systems, isolation requirements or task lifecycles differ. They must use standard GitHub-hosted runners, preserve the plan's prerequisite ordering and allow targeted retries. Choose job grouping and parallelism using measured setup, execution, transfer and retry costs.

## Code and data locations

Each kind of material has an owning location:

- `support.json` and the release snapshot hold support-selection data; policies explain the decisions behind it.
- `scripts/<project>/` holds a project's recipes and SQL probes.
- `scripts/<os>/` holds shared operating-system build, packaging and verification code.
- `tools/` holds planning, orchestration and shared archive and evidence tools.
- `.github/workflows/` holds GitHub Actions entry points.
- `support/evidence/` holds retained verification results.

Generated archives, local caches and transient CI artifacts stay out of source control. [The release policy](releases.md) governs publication and the use of verification evidence to establish eligibility.

Place temporary investigation scripts and workflows in `experiments/<name>/`, including investigations of supported targets. Each experiment must record when it was created, the question it addresses, why code is needed to answer it, its inputs, and the condition for finishing or retiring it.

Review an experiment when its question is answered, its related work ends, or its target changes; also review open experiments at least every three months. Move code still used by builds or tests into its owning recipe or shared tool. Remove experiment code and workflows when they have no concrete next use, and retain useful results under `support/evidence/`. Historical results may remain after their producing code is retired.

Reassess the architecture when extension onboarding, CI cost or verification maintenance reveals recurring problems. Follow [the functional specification](../specs/functional.md#use-a-coherent-architecture) when deciding whether a change requires human review.
