# Working instructions for this repository

Follow [style.md](style.md) whenever generating text.

## Specification boards

Everything under `specs/` belongs to a board with this format:

```text
specs/<area>/
  <area>-policy.md
  <area>-notes.md
  items/
    proposed/
    planned/
    implemented/
    rejected/
    deferred/
```

Use area-prefixed filenames for policy and notes so they remain identifiable in search results and editor tabs.

Create folders when required to add the first item and delete folders with no items in them.

### Policy

The policy states the human-reviewed rules, guarantees and selection criteria for an area, with the reasons they follow from the use case. It defines how to decide what to do. Concrete decisions, chosen mechanisms and implementation work belong in items.

Give policies stable identifiers with an area prefix: `FUNC001` (functional), `BUILD001` (build), `EXT001` (extensions) and `TEST01` (testing). Use three digits for FUNC, BUILD and EXT; testing retains its two-digit numbering. Do not renumber existing identifiers when inserting or moving rules. If an item is based on specific policies, it should cite them.

### Notes

Notes are AI-managed working context: research, investigations, open technical questions and findings shared by several items. Cite sources and distinguish evidence from inference. Move a settled decision into an item; bring a policy gap, conflict or proposed exception to human review. Notes do not change policy.

### Items

Each item describes one decision or piece of work: what it entails, why, its scope, supporting evidence and completion criteria where implementation is required. Include enough reasoning to continue the work without repeating the investigation. Keep exact build/test results in verification records and link them from the item.

The folder is the workflow status; do not duplicate it in a status field or separate implementation log.

- `proposed/` — A concrete recommendation awaiting human review; surface it to the user and wait for a decision.
- `planned/` — Approved work, or a direct consequence of policy, ready for an agent to implement.
- `implemented/` — Completed work with the required verification evidence.
- `rejected/` — A deliberate exclusion, with the reason preserved.
- `deferred/` — Postponed work, with the reason and conditions for reconsideration.

An agent takes an item from `planned/`, implements and verifies it, then moves it to `implemented/`. It stays in `planned/` while work is underway; there is no "implementing" state. A partial platform result does not complete the item's full scope. Direct consequences of policy may be recorded in `planned/` or `rejected/`; choices requiring human judgment go into `proposed/`. After review, move the item to the agreed folder and update affected policies or metadata.

When starting a new interactive conversation with a human, scan for items in `specs/*/items/proposed/*.md` and remind the user that these items are awaiting review. If you have added a proposed item, let the user know in conversation. Don't take silence as acknowledgement here - periodically remind the user until they acknowledge the items to review.

### Areas

- [functional](specs/functional/functional-policy.md) — Product guarantees; items describe the implementation decisions and work that satisfy them.
- [build](specs/build/build-policy.md) — PostgreSQL build configuration; items record feature selection, compiler settings, linking and layout.
- [extensions](specs/extensions/extensions-policy.md) — Extension selection, versions and packaging; items record each SQL extension's scope and research.
- [testing](specs/testing/testing-policy.md) — Evidence and acceptance rules; items describe executable verification work.

Keep supporting assets within their owning board. The functional board owns the architecture, inventory and metadata format; testing owns the evidence summary. Supporting assets do not create another workflow or override policy. [README.md](README.md) provides the reading order.

## Project contract

Before implementing binaries, read the functional policy, [inventory](specs/functional/functional-inventory.json), testing policy and the policies for affected areas. Follow the [architecture](specs/functional/functional-architecture.md), revising technical choices when evidence supports doing so. Preserve the human-facing invariants. Keep policy and inventory consistent; record unresolved scope choices in the appropriate `items/proposed/` folder and present a concrete recommendation before changing the agreed scope.

## The human review queue

When an agent needs to surface a decisions for a human, it should be added to `HUMAN_REVIEW_QUEUE.md`.

When starting interactive sessions with humans, check HUMAN_REVIEW_QUEUE.md and notify the user if there are pending items there.

Examples of things justifying requesting a human decision includes:

- It's not clear whether to include an extension or Postgres capability because some criteria argue for and others against
- The specified requirements are causing implementation issues or other problems and the project may benefit from altered requirements

While a request is in HUMAN_REVIEW_QUEUE.md, the old requirements remain in force. If an agent wants to proceed with a course of action that is against the specified behaviour, the appropriate response is to add a request to HUMAN_REVIEW_QUEUE.md and then stop the current work. It is always acceptable for agents to decide to stop in the face of inconsistent requirements, and never acceptable for them to implement behaviour that conflicts with a requirement.

## Authorization

Agents may:

- Edit this repository and create build and test scripts. **All compilation performed on the local computer must run inside Docker containers.** Run local tests that execute compiled artifacts inside Docker too. The host may run Git, the GitHub CLI, Docker commands, and non-compiling inspection or validation commands. Keep generated outputs out of Git; do not prune unrelated local images, containers, or files.
- Install build dependencies inside disposable Docker containers, not on the host. Do not use Homebrew, host package managers, host compilers, `sudo`, or machine-wide installation to work around a blocked local build. If Docker cannot support a target, use an appropriate GitHub Actions runner rather than attempting a host build.
- Delegate bounded tasks to subagents and run subagents in parallel when useful. Coordinate shared-file edits and integrate their work on `spike`; this authorization covers both delegation and parallel agent work.
- Use the GitHub CLI/API to inspect this public repository, run and inspect its GitHub Actions workflows, and iterate on CI failures.
- Commit work and push the `spike` branch to `origin` as needed for GitHub Actions iteration. Keep commits reviewable. Do not push to `main`, force-push, merge, delete branches, or change repository settings as part of this authorization.
- Use **standard GitHub-hosted runners** for this public repository. Do not use paid larger runners or services. Keep expensive workflows scoped, avoid accumulating large temporary Actions artifacts, and use reasonable job timeouts.

This authorization covers development and CI iteration for the pilot. It does **not** authorize publishing a permanent GitHub Release or changing public release assets. Ask for a decision only if one of those becomes necessary to proceed.

Repository instructions do not bypass tool sandbox, authentication, or GitHub permission checks. If a required operation is blocked by those controls, continue unaffected work and report the specific blocker.
