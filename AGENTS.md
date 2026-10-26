# Working instructions for spike-2

This repo contains build scripts to generate a standalone set of cross-platform Postgres binaries along with a wide range of extensions.

## Purpose and authority

Build a usable PostgreSQL distribution in functional slices. The current design in `design/` describes the slice being built. `SPIKE2_MILESTONES.md` records later work and open questions. The old tree under `tmp-spike-1/` and the `spike` branch are reference material; their specs, policies, queues and agent instructions have no authority on this branch.

The human reviews the first slice's design before implementation begins. Until that review, work on the branch structure and design review material only. After review, implement milestones autonomously within the agreed design. Surface a material design change for discussion before implementing it.

## Design and migration

Write each design rule in one authoritative place. Describe the feature as it should work in the current or imminent slice, using positive language. Keep future scope, provisional choices and open questions in the milestones file. Create a design document when a subject is needed to build or review the current slice; split it only when it has an independent purpose.

Treat every old requirement, decision, script and test as a candidate. For each design document under review, state its scope, inspect all old material within that scope, and report what was carried across, altered, dropped or added. Assert that every in-scope item received one of those treatments. Inspect old source before copying code and simplify it where possible. Use the old branch for a fresh inventory when a milestone begins; do not silently drop an old test kind or pending human review item.

When reviewing a file with the human, identify each observation by its heading or a short quote from the relevant passage. State the file's scope and account for every old rule or test kind within it as carried across, altered or dropped; identify additions separately.

## Cost and architecture

Optimize for low development cost, then speed. Delegate bounded tasks to agents suited to their difficulty. Run independent tasks in parallel only when their results will not cause one another to be redone.

Keep the architecture simple enough to understand and extend across the intended build targets. Do not build a framework merely to avoid a small amount of repetition. During long tasks, revisit whether implementation cost is justified by the benefit. Simplify within the agreed scope or surface a material change for human review before proceeding.

Add code comments only when they convey information that is genuinely hard to infer from the code. Trim comments that repeat the implementation.

## Building and testing

Iterate locally before porting a build to GitHub Actions. Run Linux builds and tests of compiled artifacts inside Docker. Run macOS builds and compiled tests inside a disposable macOS VM. Do not install build dependencies or compile on the host. Do not use a host package manager, host compiler, `sudo` or a machine-wide installation to work around a build problem. Control the disposable VM through its API or CLI; do not control the host browser or desktop for this project. Keep generated outputs out of Git and leave unrelated local files, images and VMs intact.

Build and test final archives for each functional slice. Verify assembled archives outside their build environment. Keep PostgreSQL and extension build commands independently runnable so an agent can rerun only a failed part.

Use standard GitHub-hosted runners for production builds. Port to GitHub after local iteration has addressed issues the local environment can reveal. GitHub remains necessary for target architectures unavailable locally. Keep expensive workflows scoped, set reasonable job timeouts and retain only useful temporary artifacts. Space status checks rather than using rapid `gh run watch` polling. Back off on GitHub secondary rate limits even when the hourly quota remains available; continue independent work meanwhile.

## Repository operations

Develop on `spike-2`. Keep commits reviewable. Do not push to `main`, force push, merge, delete branches, alter repository settings, publish a permanent GitHub Release or change public release assets without the human's explicit authorization. Repository instructions do not bypass sandbox or GitHub permissions. If a required operation is blocked by those controls, continue unaffected work and report the specific blocker.

Coordinate edits to shared files. Explain verified results and remaining uncertainties without treating plans or inferences as evidence.

## Writing style

Write for a reader who knows programming and PostgreSQL but is otherwise unfamiliar with this system. Introduce the use case before the design and define project-specific terms before using them. Give each document one purpose and each rule one authoritative home. State the rule, its scope and its reason together. Use observable behaviour and put machine-actionable constraints in metadata where practical.

Distinguish requirements, open decisions, research findings and verified results. Use **must** for requirements, **may** for allowed choices and **candidate** for unverified approaches. Name versions and environments behind compatibility claims. Cite upstream facts and test evidence; date changing observations and label inferences. Keep generated version lists out of manually maintained explanations.

Use direct verbs and headings. Keep one main point per paragraph; remove repetition, obvious qualifications and empty conclusions. Avoid rhetorical questions, invented labels, promotional language and formulaic contrasts. Write comments and interactive messages to the same standard. Read the text in order and remove any sentence that adds no requirement, reason, fact or useful example.

Use Markdown that reads well as plain text and avoid tables. Do not hard-wrap Markdown prose: keep each paragraph or list item on one source line and rely on the editor's soft wrapping. Use newlines for structural Markdown such as headings, blank lines, list items and code fences.
