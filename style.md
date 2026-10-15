# Writing guide

Write for a reader who knows programming and PostgreSQL and is deciding whether these binaries can load their schema. Minimize reading effort while preserving the reasoning needed to review a requirement.

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
