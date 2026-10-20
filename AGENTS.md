# Working instructions for this repository

## Specification docs

- `specs/functional.md` what this project must provide
- `specs/testing.md` - how everything is tested and how testing guarantees that the functional requirements are met 

Agents must NEVER modify spec documents, if a spec change is desired add something to HUMAN_REVIEW_QUEUE.md.

## Specifications override goals

This repository is set up to allow long-running independent agentic work using Codex goal mode. This involves a prompt supplied by the user to drive work. The user will never deliberately override specification points in a prompt. Any appearance that they have done so is a mistake by the user or a misinterpretation by you. Stop and clarify immediately.

## Optimise for low cost in development, then development speed

Use sub-agents, particularly cheap ones, for bounded research or execution tasks within their capabilities.

Use parallel subagents when work items are genuinely not interdependent. Use serial work when operating in parallel may cause some work to have to be re-done.

For bounded extension onboarding, follow [the agent guide](docs/adding-an-extension.md).

## Prefer simple, pragmatic architecture

At core we're trying to do something quite simple, the difficulty comes from the massive set of builds this project needs for all the PG versions, platforms, and extensions in the support matrix.

Having an architecture rather than a massive flat collection of build scripts is important for maintainability. Good architecture is simple, merely providing a structure and light framework for builds to reduce code duplication and make the system comprehensible. Complex and heavily engineered components should not be required.

Over-engineering inflates cost. This can happen when a seemingly simple plan turns out to have more edge cases or implementation difficulty than anticipated, or if a prompt from a human was taken to be a request for something complex. The humans always want a simple solution, and if they have made a request that implies high complexity, either through a prompt or a spec, it is a mistake.

Periodically review the task in progress, especially if it is continuing for multiple hours. Ask whether the implementation cost is justifying the benefit. Either self-correct to a simpler solution if that is within the scope of your goal, otherwise add a proposal to HUMAN_REVIEW_QUEUE.md and block progress on that part of the system until the decision is resolved.

### Policies

Policies are AI-managed. Agents can edit them at will to implement the requirements in the specification.

Policies are the key way in which humans review agent decisions, and agents ensure that decisions are followed consistently by future agents.

Ensure that policies reflect the state of the codebase in each commit. If it is necessary to change a policy, update the codebase and commit both together.

Policies can never authorise exceptions to specs, that would require a spec change, requested through HUMAN_REVIEW_QUEUE.md 

### Codebase notes and comments

When GENUINELY essential, code comments can be added to code, but remember that AI agents are VERY good at inferring details from code, and seem to constantly underestimate the ability of future agents to interpret their code so are prone to writing unnecessary comments.

Agents are authorised to trim or delete code comments that do not provide information not obvious from the code.

## The human review queue

When an agent needs to surface a decisions for a human, it should be added to `HUMAN_REVIEW_QUEUE.md`.

When starting interactive sessions with humans, check HUMAN_REVIEW_QUEUE.md and notify the user if there are pending items there.

Examples of things justifying requesting a human decision includes:

- It's not clear whether to include an extension or Postgres capability because some criteria argue for and others against
- The specified requirements are causing implementation issues or other problems and the project may benefit from altered requirements

While a request is in HUMAN_REVIEW_QUEUE.md, the old requirements remain in force. If an agent wants to proceed with a course of action that is against the specified behaviour, the appropriate response is to add a request to HUMAN_REVIEW_QUEUE.md and then stop the current work. It is always acceptable for agents to decide to stop in the face of inconsistent requirements, and never acceptable for them to implement behaviour that conflicts with a requirement.

While blocked on a response in HUMAN_REVIEW_QUEUE.md, make progress on other non-dependent tasks if appropriate.

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

# Style guide

Follow these rules whenever generating text, including code comments, policy documents, and interactive conversations with the user.

Write for a reader who knows programming and PostgreSQL but is otherwise unfamiliar with our system. Minimise reading effort while preserving the reasoning needed to review a requirement.

## Structure and precision

1. Introduce the use case before the design, and define project-specific terms before using them. Use established technical terms precisely; familiar concepts such as ABI, DDL and transitive dependencies need no tutorial.
2. Give each document one purpose and each rule one authoritative home. Link to shared policies instead of repeating them in every profile or test specification.
3. State the requirement, its scope and its reason together. Explain how it follows from the use case; omit a separate “Why” paragraph when the sentence already explains it.
4. Distinguish requirements, open decisions, research findings and verified results. Use **must** for requirements, **may** for allowed choices and **candidate** for unverified approaches. Name the versions and environment behind a compatibility claim.
5. Use observable behaviour: “starts on a clean supported OS without installing a runtime” is more useful than “portable and robust”. Put machine-actionable constraints in metadata and explain their rationale in prose.
6. Cite upstream facts and test evidence. Date changing observations and label inferences. Keep generated version lists out of manually maintained explanations.
7. Write specifications without draft labels, document-level approval-status fields or dated status preambles. Approval must require no editorial changes. Record unresolved choices explicitly and use item folders for workflow status and verification records for results.

## Economy of language

Use direct verbs and descriptive headings. Combine sentences that express one thought, but keep distinct conditions separate. Retain examples that explain a difficult boundary. Remove repeated conclusions, obvious qualifications and disclaimers already established by the document's scope.

Avoid AIisms, including:

- Contrast formulas such as “It's not X, it's Y”, “X—not Y”, and “This isn't about X; it's about Y”. State the intended meaning directly. Use an explicit comparison only when the reader needs that distinction.
- Metaphors and invented labels such as “load-bearing”, “guardrails”, “north star” and “decision surface”. Name the requirement, constraint or interface.
- Promotional or empty phrases: “seamless”, “robust”, “leverage”, “delve”, “comprehensive solution”, “it is worth noting” and “simply”.
- Rhetorical questions, repetitive “Why this matters” summaries, and praise for the design.

## Editorial check

Read in order. Can the reader understand each term without looking ahead? Does every paragraph add a requirement, reason, fact or useful example? Can a sentence be removed without losing any of those? Shorten it until further cuts would obscure the meaning.

## Markdown syntax

Avoid tables in Markdown. Prefer Markdown syntax if it reads well as plain text.
