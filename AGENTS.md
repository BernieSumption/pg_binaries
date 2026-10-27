# Working instructions for this repository

This repository builds standalone PostgreSQL distributions with extensions for supported platforms. A distribution consists of PostgreSQL and independently downloadable extension archives that can be installed together and verified from their final archive bytes.

## Keep things simple, stop and report when things get complex

The intention of this repository is that we are doing something fairly simple. There is a lot of work to do because Postgres has many extensions, but fundamentally, this is supposed to be a collection of build scripts for build Postgres extensions for different platforms and packaging them together. If anything in the design implies a difficult challenge that goes beyond straightforward creation of build scripts and test scripts, it is quite likely unintentional. Most requirements are flexible to an extent - agents should not unilaterally change them, but they can be changed by agreement if they cause issues. If an implementation agent finds itself stuck in a loop trying to get past a difficult implementation challenge, then stop and add an item to the human review queue to revisit the.

## Specifications

`design/` describes the distribution's intended behaviour and how it is built and verified. Each document covers one coherent subject and contains both product requirements and the design decisions needed to implement them.

Do not unilaterally edit designs, they should be changed only in response to a direct request in a conversation with a human. In the event that during implementation an element of the design turns out to be incorrect, add an item to the human review queue.

## The human review queue

When an agent needs to surface a decisions for a human, it should be added to `HUMAN_REVIEW_QUEUE.md`.

When starting interactive sessions with humans, check HUMAN_REVIEW_QUEUE.md and notify the user if there are pending items there.

Examples of things justifying requesting a human decision includes:

- It's not clear whether to include an extension or Postgres capability because some criteria argue for and others against
- The specified requirements are causing implementation issues or other problems and the project may benefit from altered requirements

While a request is in HUMAN_REVIEW_QUEUE.md, the current design remains in force. If an agent wants to proceed with a course of action that is against the specified behaviour, the appropriate response is to add a request to HUMAN_REVIEW_QUEUE.md and then stop the current work. It is always acceptable for agents to decide to stop in the face of inconsistent requirements, and never acceptable for them to implement behaviour that conflicts with a requirement.

While blocked on a response in HUMAN_REVIEW_QUEUE.md, make progress on other non-dependent tasks if appropriate.

## Cost and architecture

Optimize for low development cost, then speed. Delegate bounded tasks to agents suited to their difficulty. Run independent tasks in parallel only when their results will not cause one another to be redone.

Keep the architecture simple enough to understand and extend across the intended build targets. Do not build a framework merely to avoid a small amount of repetition. During long tasks, revisit whether implementation cost is justified by the benefit. Simplify within the agreed scope or surface a material change for human review before proceeding.

Add code comments only when they convey information that is genuinely hard to infer from the code. Trim comments that repeat the implementation.

## Code organisation

Organise implementation around PostgreSQL and individual extension packages. Keep each package’s recipes, dependency declarations, probes, fixtures and platform-specific code together so someone adding or debugging a package can find its implementation in one place. A package can supply several SQL extensions. Do not scatter package-specific code across repository-wide directories organised by technical function, such as builds, tests and fixtures.

Keep shared orchestration, platform support and verification machinery separate where they serve multiple packages. Use folders within those shared areas to group related responsibilities. Avoid large flat folder structures containing large numbers of unrelated files. Choose directory names and depth to make related code easy to find; no exact directory layout is prescribed.

## Repository operations

Keep commits reviewable and coordinate edits to shared files. Do not push to `main`, force push, merge, delete branches, alter repository settings, publish a permanent GitHub Release or change public release assets without the human's explicit authorization. Do not control the host browser or desktop for this project. Repository instructions do not bypass sandbox or GitHub permissions. If a required operation is blocked by those controls, continue unaffected work and report the specific blocker.

## Writing guide

Follow these rules when creating specifications and other documents in this repository and when talking with the user.

The purpose of writing is to transfer a concept faithfully into the mind of a human with minimal effort on behalf of the human.

Two most important rules:

1. Ensure that you understand the concept first. If you find yourself using vague or general terms then stop and clarify the concept. If you have enough requirements supplied by the user, reason through the concept to define it in sufficient detail. If the requirements are unclear, seek clarification from the user. 
2. Always explicitly review after writing. One pass is not enough for modern LLMs to generate clear writing following these rules. Write first then explicitly review the prose against these rules and update it as required. It is OK to re-read some writing, decide that it is unclear because the concept is not well understood, and stop to ask questions instead of declaring it done.

Further guidance:

- Describe the happy path in sequence, then list edge cases if necessary. LLMs are good at ingesting 20 sentences of arbitrarily ordered requirements and caveats, humans need a well defined narrative order.
- Write as a specification describing a system, not as instructions
- Use clear terminology that identifies the actual elements of the system, eg if we run a job on a GitHub Runner, say so, don't say eg "build device".
- Challenge the utility of every sentence and remove ones that add no or little value.
- Identify unclear writing yourself and proactively fix it, don't wait for the user to read it and express confusion.
- Write for a reader who knows programming and PostgreSQL but is otherwise unfamiliar with this system.
- Construct a series of sentences/paragraphs that brings the reader along from zero to partial to full understanding. Introduce the use case before the design and define project-specific terms before using them.
- When referring back to a concept mentioned previously repeat the same term to establish the connection, don't invent a clever label for it and assume a reader will understand. Good: "Search the project's website for platform support status. If the project's website does not not state support do not take this as evidence of lack of support" Bad: "Search the project's website for platform support status. Do not treat silence as evidence of non-support"
- Use direct verbs and headings. Keep one main point per paragraph; remove repetition, obvious qualifications and empty conclusions.
- By default, describe what _is_ the case, avoid "It's not X, it's Y" language unless thinking it might be X is a genuine pitfall you want to guard against.
- Avoid rhetorical questions, invented labels or promotional language
- Use British English eg artefact over artifact and realise over realize

Use Markdown that reads well as plain text and avoid tables. Do not hard-wrap Markdown paragraphs, rely on editor soft wrapping.
