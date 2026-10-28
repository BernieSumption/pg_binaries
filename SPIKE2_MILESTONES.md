# Spike-2 milestones

Each milestone delivers working functionality or the structure needed to build it. `design/` describes the current or imminent slice. Open questions remain here until resolved; a design document does not claim future platform support before its archives pass verification.

The previous tree is preserved at `spike` commit `372a46debf49bf3e5c5ef4a23a86fde278e2344e` and in the local ignored `tmp-spike-1/` directory. Its requirements, decisions, scripts, tests and pending human review items are candidates for the new repository, not current rules. At each milestone, inspect the old material relevant to that slice before copying code or deciding what to retain. For each design document presented for review, report its scope and classify every in-scope old rule or test kind as carried across, altered or dropped; identify additions and assert that every in-scope item has a treatment. Do not silently drop an old test kind or pending human review item. Recompute the details from the old tree rather than maintaining a second inventory.

## 1. Define the distribution for Mac ARM64 and ten extension projects

Create the branch structure and agent instructions. Update `design/distribution.md` for an installation containing all ten selected projects. Define the public `inventory.json` format in `design/distribution.md`. Create `design/extensions.md` with inclusion criteria and one decision for each selected project and its package grouping. Create `design/postgresql-options.md` for the core capabilities and `design/dependency-licenses.md` for the central licence inventory and archive pointer. Expand `design/build-and-test.md` to cover the build sequence, independent extension jobs, assembly and every applicable test kind. Inspect the old functional and testing specifications, installation, extension, PostgreSQL option, licence and platform policies, `LICENSES.md`, `support.json` and the old review queue.

As a separate step after drafting, review and rewrite all five design documents against the `AGENTS.md` writing style. Read each document in order, define terms before use, remove repeated rules and hard-wrapped prose, and check that its scope is clear. This step includes both existing documents and all three new documents.

Present each document for human review with its scope and an accounting of old material carried across, altered, dropped or added. Stop before build implementation until the human agrees to the first-slice design.

## 2. Build PostgreSQL and the selected extension packages locally

Use a disposable macOS VM to build the latest stable PostgreSQL release and the latest compatible release of each project selected in `design/extensions.md`. Populate `LICENSES.md` from the selected projects and packaged dependency closure. Produce separately installable archives and run their individual archive and SQL checks in a clean VM. Make each extension build independently rerunnable.

Lume supplies the disposable macOS VM. Its CLI starts the VM without a viewer, and SSH runs build commands and transfers source and output files. Trial selective rebuild, cloning and recovery during this milestone. If the local loop fails materially, stop dependent build work and record the evidence in the human review queue.

Open questions: the minimum macOS version to claim, the exact PostgreSQL release and build flags for its selected capabilities, and the latest compatible release of each selected project after checking the projects’ current compatibility documentation.

Prior work to inspect: `scripts/macos/`, the selected package recipes and SQL probes, `tests/builtins/`, `tests/extensions/`, Mac archive and relocation tests, and Mac static-analysis and diagnostics tools.

## 3. Verify the coherent Mac ARM64 installation

Assemble the PostgreSQL archive and all the selected extension packages using the documented extraction process. Resolve prerequisites, file and library conflicts, and required server settings. Exercise every selected SQL extension against one PostgreSQL instance and, where possible, one backend session.

Prior work to inspect: the old queue's coherent-installation proposal and the selected project recipes and probes. Keep the queue's size review and adversarial review visible for the release-candidate milestone.

## 4. Build and verify Linux ARM64 locally

Use local Docker containers or Lume VMs to build PostgreSQL and every selected extension package for Linux ARM64. Produce separately installable archives and verify each package and the complete installation in a clean local environment. Reuse the package contract and SQL probes where they apply; adapt runtime dependency and relocation checks to ELF. Resolve local build and verification failures before moving either ARM64 target to GitHub.

Prior work to inspect: `scripts/linux/`, its Dockerfiles, ELF inspectors and Linux build, archive, isolation and SQL tests.

## 5. Build the Mac and Linux ARM64 slices on GitHub

Build PostgreSQL once per target in a release run. Fan out independently runnable extension jobs using that target's PostgreSQL archive. Verify final archives in a fresh environment and test their coherent installation. Record elapsed build time and peak disk use. Do not search earlier releases or runs for reusable build outputs.

Implement the workflow sequence and selective retries defined in `design/build-and-test.md`, using ordinary retained GitHub artefacts and explicit input references. Start this milestone only after both ARM64 targets pass their local build and verification work.

Prior work to inspect: `policies/architecture.md`, `policies/delivery-process.md`, Mac and Linux selected-publication workflows and their verification tests. The old planner and artefact reuse code are candidates for removal, not implementation templates.

## 6. Add Mac and Linux x86_64

Build and test both Intel targets on GitHub-hosted runners. Use local ARM64 results to narrow issues, and investigate architecture-specific failures on the native runners. The distribution schema and directory structure already accommodate these targets; inventory entries appear only for verified bytes.

Prior work to inspect: Intel Mac and Linux pilots, platform build scripts, architecture checks and target-specific verification cases. Revisit the selected projects’ dated platform evidence in `tmp-spike-1/policies/extensions.md`, including pgrx’s tested architectures.

## 7. Prepare a thin release candidate

Assemble and test the complete selected extension set on every platform in the candidate. Review licence coverage, diagnostics, archive size, download metadata and client installation. Generate an inventory from verified assets and dry-run publication. Decide whether this slice is suitable for a public release. Publication requires separate human authorisation.

Open question: whether Windows is required before the first public release.

Prior work to inspect: `policies/releases.md`, `policies/licenses.md`, `policies/debugging.md`, `LICENSES.md`, publication tests, and the old queue's size and adversarial-review ideas. Recheck the applicability of each old test kind before calling the candidate verified.

## 7.5. Human-driven bug hunting

After milestone 7, the human uses a coherent installation and reviews its packaging and verification behaviour. The scope and timing of exploratory bug hunting are specified with the human when this milestone begins. This is separate from the automated build and verification work in earlier milestones.

Candidate activities to discuss include moving an installation after it has been used, then restarting with its existing database and configuration to find saved absolute software paths. Another candidate is running archive verification locally on the claimed minimum macOS version, or the closest available version, and recording the version tested and any gap. If exploratory work reveals a concrete failure, add a targeted regression test. Discuss whether to repeat these activities after material platform, packaging or release changes.

## 8. Expand the extension catalogue in batches

Decide which old and newly researched projects belong in the distribution. Record each accepted project's package grouping and inclusion decision in `design/extensions.md` before building it. Build each batch locally where possible, then on its GitHub targets, and add it to coherent installation testing. Keep the selected release for each project to the latest stable version compatible with the selected PostgreSQL release. Grow toward the roughly 100-project ambition, adjusting batch size using measured build time, disk use and porting effort.

Prior work to inspect: every project decision, exclusion, unreviewed candidate and dated hosting-provider catalogue in `tmp-spike-1/policies/extensions.md`, plus sources and applicable old tests. Those catalogue records are deferred to this milestone rather than discarded.

Open question: how to build and package native libraries shared by several extension packages, or handle file path clashes. As specified, we allow duplicate files if they're byte identical. If this works, great. But independently building the same library from one recipe does not guarantee identical bytes, while archives installing different bytes at the same path violate the current installation contract. If the byte-identical requirement doesn't work, consider building shared libraries once for the affected extension jobs, packaging private copies at separate paths, or another approach. Evaluate build orchestration, independent extension downloads and whether the libraries can coexist in one PostgreSQL process. Resolve this question and update the design when catalogue expansion requires it; if the initial extension set exposes the problem, bring the decision forward.

## 9. Add Windows x86_64

Implement and verify Windows archives when the platform enters release scope. Apply the package, installation and coherent-test contract to PE binaries and the Windows runtime environment.

Prior work to inspect: `scripts/windows/`, PE inspectors, Windows workflows, runtime and archive tests, and Windows-specific old policy decisions. Revisit the evidence in `tmp-spike-1/policies/extensions.md` for Address Standardizer build failures and the collection and pgaudit support exclusions before selecting Windows targets.

## 10. Refresh releases

Refresh the selected PostgreSQL and extension releases published by their projects, build fresh archives, verify the complete set and check public downloads after publication. Continue design review as the distribution grows.
