# Working instructions for spike-2

## Purpose and authority

Build a usable PostgreSQL distribution in functional slices. The current
design in `design/` describes the slice being built. `SPIKE2_MILESTONES.md`
records later work and open questions. The old tree under `tmp-spike-1/` and
the `spike` branch are reference material; their specs, policies, queues and
agent instructions have no authority on this branch.

The human reviews the first slice's design before implementation begins.
Until that review, work on the branch structure and design review material
only. After review, implement milestones autonomously
within the agreed design. Surface a material design change for discussion
before implementing it.

## Design and migration

Write each design rule in one authoritative place. Describe the feature as it
should work in the current or imminent slice, using positive language. Keep
future scope, provisional choices and open questions in the milestones file.
Create a design document when a subject is needed to build or review the
current slice; split it only when it has an independent purpose.

Treat every old requirement, decision, script and test as a candidate. For
each design document under review, state its scope, inspect all old material
within that scope, and report what was carried across, altered, dropped or
added. Assert that every in-scope item received one of those treatments.
Inspect old source before copying code and simplify it where possible. Use
the old branch for a fresh inventory when a milestone begins; do not silently
drop an old test kind or pending human review item.

## Building and testing

Iterate locally before porting a build to GitHub Actions. Run Linux builds and
tests of compiled artifacts inside Docker. Run macOS builds and compiled tests
inside a disposable macOS VM. Do not install build dependencies or compile on
the host. Keep generated outputs out of Git and leave unrelated local files,
images and VMs intact.

Build and test final archives for each functional slice. Verify assembled
archives outside their build environment. Keep PostgreSQL and extension build
commands independently runnable so an agent can rerun only a failed part.

Use standard GitHub-hosted runners for production builds. Port to GitHub after
local iteration has addressed issues the local environment can reveal. GitHub
remains necessary for target architectures unavailable locally. Avoid rapid
polling and retain only useful temporary artifacts.

## Repository operations

Develop on `spike-2`. Keep commits reviewable. Do not push to `main`, force
push, merge, delete branches, alter repository settings, publish a permanent
GitHub Release or change public release assets without the human's explicit
authorization. Repository instructions do not bypass sandbox or GitHub
permissions.

Use subagents for bounded independent tasks when they save cost or time.
Coordinate edits to shared files. Explain verified results and remaining
uncertainties without treating plans or inferences as evidence.
