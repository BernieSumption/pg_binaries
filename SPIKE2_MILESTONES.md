# Spike-2 milestones

Each milestone delivers working functionality or the structure needed to
build it. `design/` describes the current or imminent slice. Open questions
remain here until resolved; a design document does not claim future platform
support before its archives pass verification.

## 1. Establish the clean branch and first-slice design

Create the new branch structure and agent instructions. Inventory the old
specifications, decisions, implementation and test kinds without importing
them by default. Define the Mac ARM64 distribution and its build and test
process in `design/`. Stop for human review of those design documents before
implementing the slice.

## 2. Produce a usable Mac ARM64 installation locally

Use a disposable macOS VM to build the latest stable PostgreSQL release and
the latest compatible release of a first extension, provisionally pgvector.
Produce separate archives, install them together and verify PostgreSQL tools,
representative SQL behaviour, relocation and native dependencies from final
archive bytes in a clean VM. Make each build command independently rerunnable.

Lume is the assumed VM manager. Trial its creation, API or CLI control, source
transfer, selective rebuild, cloning, recovery and output retrieval during
this milestone. Its adoption remains provisional until the human explicitly
approves it. If Lume makes local iteration materially difficult, stop using
it and report the evidence and a candidate alternative.

Open questions: the minimum macOS version to claim, the exact PostgreSQL
build options, and the first extension selection after checking current
upstream compatibility.

## 3. Exercise different extension and packaging cases on Mac ARM64

Add a small, varied set covering SQL-only files, a Rust build, a substantial
native dependency tree and an extension prerequisite. PostGIS and TIGER are
candidates for the last two cases. Expand the coherent installation test to
assemble the selected set, detect file and library conflicts, and exercise
all selected extensions in one PostgreSQL instance and, where possible, one
backend session.

The human uses the installation and reviews the packaging and verification
approach. Manual bug hunting begins here as an occasional practice and is
repeated after material platform or packaging changes; it is not a task that
finishes after one run.

## 4. Build the Mac ARM64 slice on GitHub

Build PostgreSQL once in a release run. Fan out independently runnable
extension jobs using that run's PostgreSQL archive. Verify final archives in
a fresh environment and test their coherent installation. Record elapsed
build time and peak disk use. Do not search earlier releases or runs for
reusable build outputs.

Open question: the exact workflow structure and artifact lifetime. Define it
in a design document immediately before implementing this milestone.

## 5. Add Linux ARM64

Iterate in local Docker, then run the same slice on a standard GitHub ARM64
runner. Build platform-specific archives and verify the assembled release in
an isolated Linux environment. Reuse the package contract and SQL probes
where they apply; adapt runtime dependency and relocation checks to ELF.

## 6. Add Mac and Linux x86_64

Build and test both Intel targets on GitHub-hosted runners. Use local ARM64
results to narrow issues, and investigate architecture-specific failures on
the native runners. The distribution schema and directory structure already
accommodate these targets; inventory entries appear only for verified bytes.

## 7. Prepare a thin release candidate

Assemble and test the complete selected extension set on every platform in
the candidate. Review licence coverage, diagnostics, archive size, download
metadata and client installation. Generate an inventory from verified assets
and dry-run publication. Decide whether this slice is suitable for a public
release. Publication requires separate human authorization.

Open question: whether Windows is required before the first public release.

## 8. Expand the extension catalogue in batches

Decide which old and newly researched projects belong in the distribution.
Build each batch locally where possible, then on its GitHub targets, and add
it to coherent installation testing. Keep the selected release for each
project to the latest stable version compatible with the selected PostgreSQL
release. Grow toward the roughly 100-project ambition, adjusting batch size
using measured build time, disk use and porting effort.

## 9. Add Windows x86_64

Implement and verify Windows archives when the platform enters release
scope. Apply the package, installation and coherent-test contract to PE
binaries and the Windows runtime environment.

## 10. Refresh releases

Refresh the selected PostgreSQL and extension releases from upstream, build
fresh archives, verify the complete set and check public downloads after
publication. Continue occasional manual bug hunting and design review as the
distribution grows.
