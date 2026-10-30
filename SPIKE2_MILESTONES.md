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

## 6.5 Review structure of build scripts

In cooperation with human, look at build scripts, see if we need to deduplicate or add structure over how dependencies are fetched and how compilation works. How much abstraction is the right amount?

Specifically to review:

1. should packages declare dependenncies that are installed/checked centrally rather than each script being respnsible for fetching its own deps?
2. should we parameterise both os (linux/mac) as well as arch in the build scripts?
3. Do scripts have any fully common setup that can be pulled out?
4. How are we handling the relocation of library dependencies and is/should this be abstracted?
5. I'm told that Postgres needs a shim to load a bundled libc then delegate to the real binary, because Postgres expects an absolute path to libc. Fine if that's the best way but is static linking an alternative, or is there a way to get relative paths in more simply?
6. Should we do Windows now before we add the remaining 100 extensions? Assume that we can find a product that gives as good local iteration DX as Lume.
7. Open question: how to build and package native libraries shared by several extension packages, or handle file path clashes. As specified, we allow duplicate files if they're byte identical. If this works, great. But independently building the same library from one recipe does not guarantee identical bytes, while archives installing different bytes at the same path violate the current installation contract. If the byte-identical requirement doesn't work, consider building shared libraries once for the affected extension jobs, packaging private copies at separate paths, or another approach. Evaluate build orchestration, independent extension downloads and whether the libraries can coexist in one PostgreSQL process. Resolve this question and update the design when catalogue expansion requires it; if the initial extension set exposes the problem, bring the decision forward.

## 6.6 Verify dependency isolation and assess Parallels for local builds

This milestone establishes whether the static-linking default in `packages/README.md` works across the current extension set, then researches Parallels as a local build environment. The policy is the working assumption during implementation; the final report recommends retaining, adjusting or abandoning it based on actual results. Parallels research ends with a recommendation and an experiment plan before any download or installation.

### 1. Detect dependency clashes before changing packages

The final-archive verifier checks whether PostgreSQL and the selected extensions can load conflicting dependency implementations into one backend process. It examines dependency identities and exported and imported symbols, including dependency symbols exposed by statically linked code. Renamed library files do not count as symbol isolation. The check distinguishes the server's dependency closure from unrelated command-line programs, expected PostgreSQL extension entry points, and platform symbol-binding rules. Unresolved conflicts fail verification with the affected packages, libraries and symbols identified. Any exception to conflict detection requires evidence for the affected binaries.

The first acceptance test uses the existing archives, before rebuilding Address Standardizer or PostGIS: the new check itself must identify PCRE2 as a conflict on both Linux targets. A failure from stale build records or another check does not satisfy this test. An ARM64 runtime check in both load orders reproduces the cross-binding already observed in `out/dependency-overlap-research/`. Failure detection does not depend on a crash or a SQL probe failing. A regression test preserves the original conflict. The existing Mac duplicates are assessed using Mach-O binding rules; the Linux finding alone does not establish that Mac has the same conflict. The new check becomes part of ordinary release verification and its reports, so publication cannot accept a required failed check.

### 2. Apply the static-linking default one package at a time

Each extension package is reviewed against the README policy, starting with Address Standardizer's PCRE2. Package-private dependencies are statically linked with their symbols hidden where that is practical. PostgreSQL entry points remain exported. Packages with no applicable dependencies need no build changes. Existing libc and compiler-support arrangements are preserved; build, plugin and licence constraints are assessed before changing other dependencies.

Each changed package passes individual archive and SQL verification before the next dependent change. The verifier confirms that static dependencies no longer appear as dynamic requirements or exposed dependency symbols. Dynamic-linking exceptions retain a concrete reason with their package implementation and pass the dependency-clash check. The complete installation is then verified on all four existing targets, including both Linux PCRE2 load orders. Package-local implementation and build-error iteration default to Luna, with harness commands supplied and model upgrades recorded as required by `AGENTS.md`.

Reviewable commits separate the verifier from package changes so the policy can be reconsidered without losing detection. Significant build complexity, unsupported features, licence questions or runtime failures go into the human review queue with evidence. A blocked package does not prevent independent package work or Parallels research. The final report records each package's treatment, dynamic exceptions, verification gaps and material changes in build time or archive size. It explicitly judges whether the policy proved useful in practice; the milestone does not require forcing every dependency into a static build.

### 3. Research Parallels before downloading it

The research uses current official documentation to assess whether Parallels can provide a simple, unattended local build environment for Windows, Linux and macOS on the host Mac. It identifies the required edition, licence costs and restrictions, guest OS and architecture support, and available CLI, SDK or API operations. The required operations are headless creation or cloning, start and stop, resource configuration, command execution with exit status and logs, file transfer, snapshots or recovery, and cleanup. Differences between guest operating systems and any required GUI or human setup are recorded.

ARM guest virtualisation, x86/x64 application translation inside Windows ARM, and full x86 guest emulation are assessed separately. Research covers whether each can build and execute the intended PostgreSQL architecture and extension toolchains, supported guest versions, concurrency limits and known emulation restrictions. Existing Docker, Lume and GitHub build loops provide the comparison. Emulation is judged by useful build-and-test turnaround, including GitHub queue and transfer time, rather than by assuming either a modest slowdown or unusable performance.

The resource assessment records the host's available RAM, CPU and disk, documented guest requirements, memory-allocation controls and any host memory overhead. It proposes practical configurations for one build agent, concurrent agents and a separate clean verifier. Documented limits, estimates and measurements are distinguished. Unmeasured build throughput, idle memory, memory pressure, clone cost and disk growth remain explicit experiment questions.

The report recommends whether to download or trial Parallels, which platforms and architectures look suitable, and where Docker, Lume or GitHub should remain in use. If recommending that Docker and Loom should remain, then the reason why this justifies the additional complexity cost should be stated. It includes official source links and a bounded post-installation experiment plan: automate the VM lifecycle; prepare a compiler and package dependencies; build PostgreSQL, a small extension and a dependency-heavy extension; verify final archives in a clean environment; and measure startup, repeated-build turnaround, host memory pressure, disk use and useful concurrency. The experiment plan defines what would justify keeping Parallels or returning to the existing tools. No purchase, download, installation or Windows package implementation occurs in this milestone.

Prior work to inspect: the milestone 6.5 dependency-clash question, current bundlers and final-archive checks, Linux PCRE2 loader traces, macOS dependency locks, the static musl launcher and bundled glibc arrangement, and retained Docker/Lume build and clean-verification environments. Starting points for Parallels research are the [developer guide](https://docs.parallels.com/landing/parallels-desktop-developers-guide), [macOS ARM VM automation and limitations](https://kb.parallels.com/en/128867), and [x86 guest emulation limitations](https://kb.parallels.com/en/130217); their current applicability is checked during research.

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

## 9. Add Windows x86_64

Implement and verify Windows archives when the platform enters release scope. Apply the package, installation and coherent-test contract to PE binaries and the Windows runtime environment.

Prior work to inspect: `scripts/windows/`, PE inspectors, Windows workflows, runtime and archive tests, and Windows-specific old policy decisions. Revisit the evidence in `tmp-spike-1/policies/extensions.md` for Address Standardizer build failures and the collection and pgaudit support exclusions before selecting Windows targets.

## 10. Refresh releases

Refresh the selected PostgreSQL and extension releases published by their projects, build fresh archives, verify the complete set and check public downloads after publication. Continue design review as the distribution grows.
