# Working instructions for this repository

## Project contract

Read [the specification](docs/specification.md) and [verification strategy](docs/verification.md) before implementing binaries. [The project plan](docs/project-plan.md) is provisional: change the implementation route when evidence supports doing so. Preserve the human-facing invariants, and surface product decisions with `REVIEW:` rather than silently weakening them.

## Authorization for the `spike` branch

The repository owner has authorized agents working on the PostgreSQL binary pilot to:

- Edit this repository, create build and test scripts, and run local compilation and tests. Use Docker or other locally available build tools when helpful. Keep generated outputs out of Git; do not prune unrelated local images, containers, or files.
- Install task-specific build dependencies in the workspace, temporary directories, or disposable containers as needed. Do not make unrelated machine-wide changes.
- Use the GitHub CLI/API to inspect this public repository, run and inspect its GitHub Actions workflows, and iterate on CI failures.
- Commit work and push the `spike` branch to `origin` as needed for GitHub Actions iteration. Keep commits reviewable. Do not push to `main`, force-push, merge, delete branches, or change repository settings as part of this authorization.
- Use **standard GitHub-hosted runners** for this public repository. Do not use paid larger runners or services. Keep expensive workflows scoped, avoid accumulating large temporary Actions artifacts, and use reasonable job timeouts.

This authorization covers development and CI iteration for the pilot. It does **not** authorize publishing a permanent GitHub Release, changing public release assets, or choosing the project's source-code license. Ask for a decision only if one of those becomes necessary to proceed.

Repository instructions do not bypass tool sandbox, authentication, or GitHub permission checks. If a required operation is blocked by those controls, continue unaffected work and report the specific blocker.
