# Migration ledger

The previous tree is preserved at `spike` commit
`372a46debf49bf3e5c5ef4a23a86fde278e2344e` and in the local ignored
`tmp-spike-1/` directory. The branch is the durable reference; the ignored
directory is a convenience on this machine. Every previous requirement,
decision and implementation is a candidate, not an instruction for spike-2.

For each candidate, record **adopt**, **adapt**, **defer** or **retire** and the
reason when its subject enters a milestone. An unreviewed item remains
visible here. A milestone cannot claim a capability while its relevant
requirements or test kinds are unreviewed. The old branch contains the exact
file-level inventory, including 11,977 tracked files; 8,914 are under
`support/evidence/`. Generated evidence is historical and cannot prove new
archive bytes.

## Product and process documents

- `specs/functional.md`: review OS and architecture scope, portability,
  extension inclusion, upstream compatibility, source patching, version
  selection, installation, PostgreSQL options, archive size, inventory,
  licensing, diagnostics and architecture. The previous multiple-major and
  recent-extension-major rules change to one latest PostgreSQL release and
  the latest compatible release per selected extension. Platform scope grows
  through milestones.
- `specs/testing.md`: review each test obligation through
  `SPIKE2_TEST_INVENTORY.md`. Final-archive verification, ordinary-user SQL
  behaviour, relocation and coherent installation enter the first slice.
- `policies/architecture.md`: retain independently runnable project build
  commands as a candidate. Retire cross-release artifact lookup and the
  previous support-versus-inventory work planner.
- `policies/delivery-process.md`: adapt source selection, prerequisites and
  release preparation to a fresh build run. Review support refresh and
  publication decisions when those milestones start.
- `policies/install-process.md`: review separate archives, copy-and-merge
  installation, metadata, dependency bundling and relocation in the first
  slice. `design/distribution.md` defines the imminent package contract.
- `policies/os-support.md`: defer the old minimum OS floors and platform
  implementation details until each platform is built and checked.
- `policies/postgres-options.md`: review each capability against the first
  Mac build rather than copying its compiler flags or dependency set.
- `policies/extensions.md`: retain all inclusion, exclusion and unreviewed
  project findings as research candidates. Recheck current upstream releases,
  compatibility, licences and dependencies when selecting each project.
  The current `support.json` contains 11 selected projects; `collection` has
  two release lines, of which latest-only selects at most one.
- `policies/testing.md`: review evidence, environment isolation, static
  inspection, SQL probes, relocation and diagnostic checks. Retire the
  cross-run verification-profile invalidation scheme; retain exact final
  archive identity and observable test outcomes.
- `policies/releases.md`: defer public tag and URL decisions until a release
  candidate. Review immutable assets, inventory and anonymous downloads.
- `policies/licenses.md`: review previous third-party licence findings as
  each dependency enters an archive. Recheck redistribution terms before
  publishing.
- `policies/debugging.md`: review logs, native symbols and crash evidence
  while hardening the Mac slice and before a release candidate.
- `README.md`: public marketing copy is not imported into the new design.
  Write a new public README when there is a verified distribution to describe.
- `GOAL_BACKLOG.md`: preserve as historical work and evidence, not an active
  task list. Its candidate-staging and cross-run reuse work is retired by the
  fresh-build decision.

## Pending human review from the previous branch

- Built-in extension inventory varied by platform. The new inventory shape
  places built-in names in each PostgreSQL target download; verify this from
  final archive control files before publication.
- Archive size review remains deferred until the first usable installation
  gives measured size contributors.
- Adversarial correctness review remains deferred until the first release
  candidate has implementation and tests to inspect.
- Manual post-release-style bug hunting becomes an occasional practice
  beginning with the Mac slice; record observations and resulting fixes or
  test additions. It is not a routine release gate.
- Coherent installation testing enters the first slice and expands with the
  selected extension set. Resolve prerequisites, configuration and shared
  library conflicts in the slice that introduces them.

## Implementation candidates

- `support.json`, `support/postgresql-releases.json` and project target
  files: adapt to one current PostgreSQL release, one compatible release per
  selected extension, and only the targets in the active slice. Keep exact
  upstream source identities and prerequisite relationships.
- `scripts/macos/`, `scripts/linux/`, `scripts/windows/` and
  `scripts/<project>/`: inspect recipes and probes when their platform or
  project enters a milestone. Copy only commands that implement the new
  package and test design. The old Linux Docker pilot already builds
  PostgreSQL and pgvector together; the Mac scripts contain native packaging
  and verifier experience.
- `tools/`: review archive input checks, dependency inspectors, package
  assembly and source identity helpers at the point of use. Retire the
  planner, core-pin resolvers, candidate cache and cross-release reuse tools.
- `.github/workflows/`: port native runner setup and checked build commands
  after local iteration. Replace the one-target manual dispatcher with a
  release-run dependency graph when GitHub orchestration enters scope.
- `tests/`: inspect each kind in `SPIKE2_TEST_INVENTORY.md`; port a test only
  when its behaviour remains required. Do not import tests whose sole purpose
  is maintaining retired state machinery.
- `support/verification-profiles.json`, `support/verification/` and
  `support/evidence/`: historical results remain in `spike`. New archive
  verification records are generated for new bytes; old records do not
  qualify a new release.
- `experiments/`, old temporary pins and `dist/`: local historical material
  and generated output, not active source for the new branch. Inspect an
  experiment only when it answers a current build question.

Before the first public release, review every old document topic above and
every test kind in the companion inventory for applicability. Deferred
platform-specific items remain visible until their platform milestone.
