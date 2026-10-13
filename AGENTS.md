# Working instructions for this repository

## Project contract

Read [the specification](docs/specification.md) and [verification strategy](docs/verification.md) before implementing binaries. [The project plan](docs/project-plan.md) is provisional: change the implementation route when evidence supports doing so. Preserve the human-facing invariants, and surface product decisions with `REVIEW:` rather than silently weakening them.

## Authorization

Agents may:

- Edit this repository and create build and test scripts. **All compilation performed on the local computer must run inside Docker containers.** Run local tests that execute compiled artifacts inside Docker too. The host may run Git, the GitHub CLI, Docker commands, and non-compiling inspection or validation commands. Keep generated outputs out of Git; do not prune unrelated local images, containers, or files.
- Install build dependencies inside disposable Docker containers, not on the host. Do not use Homebrew, host package managers, host compilers, `sudo`, or machine-wide installation to work around a blocked local build. If Docker cannot support a target, use an appropriate GitHub Actions runner rather than attempting a host build.
- Delegate bounded tasks to subagents and run subagents in parallel when useful. Coordinate shared-file edits and integrate their work on `spike`; this authorization covers both delegation and parallel agent work.
- Use the GitHub CLI/API to inspect this public repository, run and inspect its GitHub Actions workflows, and iterate on CI failures.
- Commit work and push the `spike` branch to `origin` as needed for GitHub Actions iteration. Keep commits reviewable. Do not push to `main`, force-push, merge, delete branches, or change repository settings as part of this authorization.
- Use **standard GitHub-hosted runners** for this public repository. Do not use paid larger runners or services. Keep expensive workflows scoped, avoid accumulating large temporary Actions artifacts, and use reasonable job timeouts.

This authorization covers development and CI iteration for the pilot. It does **not** authorize publishing a permanent GitHub Release, changing public release assets, or choosing the project's source-code license. Ask for a decision only if one of those becomes necessary to proceed.

Repository instructions do not bypass tool sandbox, authentication, or GitHub permission checks. If a required operation is blocked by those controls, continue unaffected work and report the specific blocker.
