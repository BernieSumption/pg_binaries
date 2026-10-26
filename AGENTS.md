# Working instructions for this repository

This repository builds standalone PostgreSQL distributions with extensions for supported platforms. A distribution consists of PostgreSQL and independently downloadable extension archives that can be installed together and verified from their final archive bytes.

## Specifications

`design/` describes the distribution's intended behaviour and how it is built and verified. Each document covers one coherent subject and contains both product requirements and the design decisions needed to implement them.

Do not unilaterally edit designs, they should be changed only in response to a direct request in a conversation with a human. In the event that during implementation an element of the design turns out to be incorrect, add an item to the human review queue.

## Editing the design

Agents may propose design changes in conversation or `HUMAN_REVIEW_QUEUE.md`. Before implementing a new subject or a material change to an agreed design, explain the proposed behaviour and obtain the human's agreement. Record decisions needed for current work in `HUMAN_REVIEW_QUEUE.md`; do not present them as settled design. Once a design is agreed, agents may implement it and resolve routine details in code and tests without another review. Keep design and implementation consistent when either changes.

Create a design document when its subject is needed to build or review the current slice. Split documents only when the subjects have independent purposes. Give each rule one authoritative home and link to it where another document needs the rule. Describe intended behaviour in positive terms. When reviewing a file with the human, identify observations by a section heading or a short quote from the relevant passage.

## Human review queue

When an agent needs a human decision about current work, add a concise item to `HUMAN_REVIEW_QUEUE.md` stating the issue, the proposed resolution and the work affected. Check the queue at the start of an interactive session and tell the human about pending items. Update or remove an item when the human resolves it.

While an item is pending, the agreed design remains in force. Do not implement behaviour that conflicts with it. Continue work that does not depend on the decision. If requirements conflict or a requested change would alter the agreed design, record the issue and pause the affected work until the human decides.

## Cost and architecture

Optimize for low development cost, then speed. Delegate bounded tasks to agents suited to their difficulty. Run independent tasks in parallel only when their results will not cause one another to be redone.

Keep the architecture simple enough to understand and extend across the intended build targets. Do not build a framework merely to avoid a small amount of repetition. During long tasks, revisit whether implementation cost is justified by the benefit. Simplify within the agreed scope or surface a material change for human review before proceeding.

Add code comments only when they convey information that is genuinely hard to infer from the code. Trim comments that repeat the implementation.

## Building and testing

Iterate locally before porting a build to GitHub Actions. Run Linux builds and tests of compiled artifacts inside Docker. Run macOS builds and compiled tests inside a disposable macOS VM. Do not install build dependencies or compile on the host. Do not use a host package manager, host compiler, `sudo` or a machine-wide installation to work around a build problem. Control disposable VMs through their API or CLI. Keep generated outputs out of Git and leave unrelated local files, images and VMs intact.

Build and test final archives for each supported slice. Verify assembled archives outside their build environment. Keep PostgreSQL and extension build commands independently runnable so an agent can rerun only a failed part.

Use standard GitHub-hosted runners for production builds. Port to GitHub after local iteration has addressed issues the local environment can reveal. Keep expensive workflows scoped, set reasonable job timeouts and retain only useful temporary artifacts. Use the GitHub CLI or API to inspect runs and retrieve artifacts after runs finish. Space status checks rather than using rapid `gh run watch` polling. Back off on GitHub secondary rate limits even when the hourly quota remains available; continue independent work meanwhile.

## Repository operations

Keep commits reviewable and coordinate edits to shared files. Do not push to `main`, force push, merge, delete branches, alter repository settings, publish a permanent GitHub Release or change public release assets without the human's explicit authorization. Do not control the host browser or desktop for this project. Repository instructions do not bypass sandbox or GitHub permissions. If a required operation is blocked by those controls, continue unaffected work and report the specific blocker.

Explain verified results and remaining uncertainties without treating plans or inferences as evidence.

## Writing style

Write for a reader who knows programming and PostgreSQL but is otherwise unfamiliar with this system. Introduce the use case before the design and define project-specific terms before using them. Give each document one purpose and each rule one authoritative home. State the rule, its scope and its reason together. Use observable behaviour and put machine-actionable constraints in metadata where practical.

Distinguish requirements, open decisions, research findings and verified results. Use **must** for requirements, **may** for allowed choices and **candidate** for unverified approaches. Name versions and environments behind compatibility claims. Cite upstream facts and test evidence; date changing observations and label inferences. Keep generated version lists out of manually maintained explanations.

Use direct verbs and headings. Keep one main point per paragraph; remove repetition, obvious qualifications and empty conclusions. Avoid rhetorical questions, invented labels, promotional language and formulaic contrasts. Write comments and interactive messages to the same standard. Read the text in order and remove any sentence that adds no requirement, reason, fact or useful example.

Use Markdown that reads well as plain text and avoid tables. Do not hard-wrap Markdown prose: keep each paragraph or list item on one source line and rely on the editor's soft wrapping. Use newlines for structural Markdown such as headings, blank lines, list items and code fences.
