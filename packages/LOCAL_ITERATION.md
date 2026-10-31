# Local build iteration

This document records the working development process, commands and measurements for package builds. Agents maintain it as the tooling changes. Product requirements and release verification remain in [build-and-test.md](../design/build-and-test.md).

Compilation, dependency installation and execution of built software happen inside a development VM or container. The Mac host manages environments and transfers source files and archives. Final archive verification uses a separate clean environment.

## Target environments

The environment comparison is in progress. The established routes are:

- Linux ARM64: the retained Docker development container runs ARM binaries directly.
- Linux x86_64: an amd64 Docker container runs through Rosetta inside Docker Desktop's ARM Linux VM. Both builds and final-archive verification have passed through this route.
- macOS ARM64: Lume development and clean verification VMs have passed the complete package set.
- macOS x86_64: native GitHub Intel runners have passed the complete package set. A viable local route still needs investigation.
- Windows x86_64: the Windows 11 ARM download has completed, but the Parallels VM has not started. ARM-hosted MSVC can target x64; running the resulting programs through Windows translation still needs to be demonstrated for this project.

Parallels will replace an established route only after equivalent builds and verification work and the measured turnaround or simpler operation justify the change. The comparison includes startup, source transfer, dependency preparation, compilation, packaging and verification, rather than compiler speed alone.

## Comparing the routes

Each plausible route receives an actual setup and build attempt. The comparison covers Parallels Linux and macOS guests as well as Windows, the existing Docker and Lume environments, local x86 translation or emulation, and hosted GitHub iteration. A documented limitation guides the experiment; it is not a substitute for trying a route when the required tools are available. A route that cannot be tried has its concrete blocker recorded.

For each route, the experiment record includes host and guest versions, CPU/RAM allocation, setup time, manual steps, failures and recovery work. Comparable workloads record cold and repeat build time, verification and transfer time, and which caches were warm. Representative workloads include a small native extension and a dependency-heavy package. Repeated timings are reported individually or with their range; parallel activity and network downloads are identified so they are not mistaken for compiler performance.

The recommendation distinguishes routes that were tested successfully, tested with poor results, blocked before a useful trial, and not yet attempted. Qualitative evidence about reliability and agent effort accompanies timings. Retaining Docker or Lume alongside Parallels requires evidence of a useful advantage, rather than familiarity alone.

A headless Ubuntu ARM64 cloud-image trial under Lume reached SSH without an interactive installer. Growing its disk, installing Docker and registering Lume's Rosetta share also succeeded; an amd64 container executed successfully. Comparable extension builds are still being measured. This route therefore has a working unattended setup, but no build-performance verdict yet.

UTM 4.7.5 is also installed, with metadata for an ARM64 Windows guest allocated 8 GiB RAM. Its CLI help worked, but version and inventory queries returned `OSStatus error -1712`; both exited with status zero despite the errors. Guest control and build performance could not be tested. No UTM desktop control or VM changes were attempted. VMware Fusion is not installed, and standalone QEMU system executables were absent from `PATH`.

## Development loop

Agents develop build scripts locally before running them on GitHub Actions. A local iteration produces an archive and resolves build failures quickly; inexpensive smoke checks can help diagnose a failure. GitHub jobs run the same package build commands after preparing their runner environments. A failure found on GitHub is fixed in the shared build script or runner setup and checked again where it occurred.

A development environment retains its installed tools and files across stops and starts. Agents may install tools and libraries as needed. Separate workspaces isolate build files; changes to system dependencies in a shared VM or container still require coordination. Another environment is appropriate when concurrent work needs incompatible system changes. The measured environment comparison will determine the default allocation and concurrency limits.

Adding or updating a package includes the [dependency and licence review](../design/dependency-licenses.md#dependency-review-during-development).

### Docker commands

From the host repository, a Linux package build uses the development archive for its target:

```sh
bash platforms/linux/build-extension-local.sh \
  address_standardizer /path/to/postgresql-development.tar.gz \
  out/local-iteration/build-output linux-x86_64 agent-1-linux-x86
```

The helper creates or starts the named retained container, caches the supplied development archive by checksum and builds in `/work/local-iteration/<target>/<package>/workspace`. Different container names give agents separate writable environments. The repository is mounted read-only, so host edits become visible without a source-transfer step. `linux-arm64` selects the native ARM route.

Clean verification runs separately:

```sh
bash verification/linux/run-local.sh --target linux-x86_64 \
  /path/to/postgresql.tar.gz out/local-iteration/verification \
  address_standardizer=/path/to/address_standardizer.tar.gz
```

The verifier creates and removes a disposable container; the development container and its workspace remain available. Named development containers retain their installed tools across `docker stop` and `docker start`. New containers keep `/work` in the ignored repository directory `out/local-environments/<container-name>/`; `PG_BINARIES_LINUX_WORK` can select another host location at creation. Existing containers retain their original mounts, reported by `docker inspect`. Older development containers use host temporary directories; deleting those directories loses their build caches.

### Lume commands

The measured Mac setup uses `spike2-macos-arm64-build` for compilation and `spike2-macos-arm64-clean` for verification. Both guests have four vCPUs and 8 GiB RAM. Lume 0.6.1 provides headless lifecycle and address discovery:

```sh
lume run --no-display --detach spike2-macos-arm64-build
lume get spike2-macos-arm64-build --format json
```

Guest access uses SSH as user `lume`, with the project key `~/.ssh/pg_binaries_lume_id_ed25519` and host fingerprints in `~/.ssh/pg_binaries_lume_known_hosts`. Both files have owner-only permissions and are stored outside temporary directories. Authentication with these files has been checked against the retained build VM. Guest IP addresses can change and come from `lume get`.

Source transfers go into a guest-local checkout; compilation runs against the guest filesystem. The measurements used `~/local-iteration-src`, with workspaces kept separately for each package. Editing a host build script therefore requires transferring that file before invoking the shared `build.py` command over SSH. The clean VM receives the verifier source and final archives, without the development toolchain or dependency prefixes.

The clean guest can be shut down through its enabled SSH service with `sudo shutdown -h now`; `lume get` confirms that it has stopped. During this trial, Lume's own shutdown helper could not use guest SSH even though direct SSH worked. Preserve a working access key and address-discovery command rather than relying on an untested guest-control helper.

Two measured starts reached SSH readiness in 9.74 and 10.39 seconds. A 54,071,920-byte PostgreSQL development archive transferred from host to guest in 0.264 seconds with matching SHA-256; the host file was already warm in the filesystem cache. Graceful shutdown took 11.23 seconds from supplying the sudo credential to confirmed stopped state. These are retained-VM timings, excluding initial macOS installation and guest setup.

Lume and Parallels both document a limit of two concurrent macOS guests on Apple Silicon. Budget two across both products: a separate allowance for each has not been demonstrated. Two Lume guests have run together; a mixed-product trial has not run. This makes a shared development VM with separate workspaces more practical than one Mac VM per agent while retaining a clean verification VM. The limit does not apply to Linux or Windows guests. [Lume](https://cua.ai/docs/lume), [Parallels](https://kb.parallels.com/en/128867).

### Windows commands

These scripts run inside Windows, from its local repository checkout. Native GitHub trials have passed PostgreSQL and eight extension packages; PostGIS remains under investigation. The local Parallels guest has not reached this stage.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File platforms/windows/bootstrap.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File platforms/windows/build-postgresql-local.ps1 `
  -Workspace C:/pg-work/postgresql -OutputDirectory C:/pg-output/postgresql
powershell.exe -NoProfile -ExecutionPolicy Bypass -File platforms/windows/build-extension-local.ps1 `
  -Package pgvector `
  -DevelopmentArchive C:/pg-output/postgresql/postgresql-development-18.6-windows-x86_64.tar.gz `
  -Workspace C:/pg-work/agent-1/pgvector -OutputDirectory C:/pg-output/pgvector
```

Bootstrap prepares tools under `C:/pg-binaries-tools` by default; `PG_WINDOWS_TOOLS` selects that root for subsequent scripts. PostGIS additionally uses `bootstrap.ps1 -Package postgis` to prepare MSYS2. The PostgreSQL build needs an empty workspace and produces separate runtime and development archives. Extension builds reuse their named workspace and cache sources beneath the tools root. The archive filename comes from `postgresql-build.json` in the PostgreSQL output directory; the example uses the current selected version.

Windows verification extracts archives with Python's `data` filter so directories inherit normal Windows permissions. Python 3.13's unfiltered extraction creates protected directory permissions that prevent PostgreSQL's restricted child process from loading DLLs, producing `0xc0000135` even when all required DLLs are present. The controlled trial reproduced the failure with identical archive bytes and paths. Probe scratch folders also inherit Windows permissions; Linux and macOS retain private temporary directories. [Python directory permissions](https://docs.python.org/3.13/library/os.html#os.mkdir), [PostgreSQL restricted processes](https://github.com/postgres/postgres/blob/REL_18_6/src/common/restricted_token.c).

The hosted trial lives in `.github/workflows/local-iteration-windows.yml`. Its phases are `core`, `small`, `postgis`, `rust`, `all`, `package` and `bootstrap-postgis`. Manual dispatch selects the phase; `small` covers PostgreSQL and seven extension packages. Completed PostgreSQL archives and their build record are retained before runtime verification, so a later checker failure does not lose the SDK. Extension builds still require the runtime checkpoint to pass.

A manual run can supply `postgresql_run` to reuse that run's recorded PostgreSQL runtime and development archives; selection checks current build inputs and archive hashes, and the checkpoint still runs runtime verification. This requires the component artefact `spike2-windows-x86_64-postgresql`; the first two trial runs predate that artefact and cannot be selected.

The optional `repeat_builds` input runs each selected extension build twice in the same workspace. `package-summary.json` records first and repeat build times separately from the total including verification, and checks that the recorded workspace keys remain unchanged. The first build can use installed tools and download caches; its timing is not necessarily a cold-machine measurement.

The `package` phase accepts one package name through the `package` input. The separate `bootstrap-postgis` phase diagnoses tool preparation without building PostgreSQL or extensions. Bootstrap logs timestamp each external operation; downloads have a five-minute timeout. The focused diagnostic located a stall in MSYS2 archive extraction after download and checksum verification completed; extraction did not finish before its 20-minute job limit. The earlier two-hour PostGIS failure therefore cannot establish a need for compiled-dependency caching.

Build records use forward-slash paths and checkout files use LF line endings on every host. A cross-host SDK audit found that Windows path separators and Git's CRLF conversion otherwise made identical source revisions appear different. Fresh Windows SDK run `41175933237` passed the native record tests and PostgreSQL runtime checkpoint with this correction. Earlier records remain historical evidence and are not rewritten to bypass current input checks.

A native x64 hosted success does not establish that Windows ARM can build and run the same software through x64 translation.

## Persistent build state

The source-download cache contains checksum-verified archives. It is separate from compiled dependency installations, Cargo's compiled output and installed toolchains. Keeping downloaded archives alone does not make a repeat build incremental.

Local extension iteration uses one stable workspace per agent, package and target. Dependency prefixes can contain absolute paths, so the workspace stays at the same path between runs. The harness owns reuse and invalidation; package scripts consume the prepared state without implementing a local or GitHub cache backend.

Inside the development environment, the shared command is:

```sh
python3 build.py --target linux-arm64 extension-build \
  address_standardizer /work/postgresql-development.tar.gz /work/output \
  --workspace /work/agents/agent-1/address_standardizer \
  --source-cache /work/source-cache --reuse-workspace
```

The target, package and development archive select the build. The output directory receives the finished archive. The workspace is an absolute path without whitespace, retained between runs; the source cache may be shared because archives are checksum-verified. Each simultaneous build needs its own workspace. Outputs stay outside the workspace.

Before each invocation, the harness replaces the private PostgreSQL copy and empties `payload/` and `build/stage/`. With unchanged inputs, it retains prepared sources, build intermediates and successful dependency installations. Changing the main build script refreshes sources and main intermediates while retaining `build/dependencies/`, Cargo's `build/target/` and pgrx state. Changing a source checksum, dependency-build implementation, PostgreSQL development archive, or recorded toolchain/settings refreshes source and build state. A failed dependency phase is retried.

The optional `build-dependencies.sh` or `build-dependencies.ps1` entry point prepares dependencies without implementing caching itself. Its helpers live in `internal/dependencies/`; changes there invalidate the dependency installation. Installed Debian and MSYS2 package versions also form part of the build context, so updating a system dependency invalidates retained build state. The entry-point contract is documented in [README.md](README.md).

The harness rejects simultaneous use of a workspace. A crash can leave `.pg-binaries-extension-workspace.lock`; its error names the owning PID. Remove the lock only after confirming that process has exited. Fresh-workspace builds remain available by omitting `--reuse-workspace`.

Upgrading the harness's cache-key definition can invalidate existing workspaces. During these trials, adding empty Windows environment fields changed a Mac workspace's context fingerprint and cleared its compiled dependencies. The sources, compiler, SDK and dependency script were unchanged. Recovery took 208 seconds using the retained package-download cache; the next identical run skipped dependencies and took 47 seconds. This was a one-time harness upgrade, separate from the original cold/warm results.

## Measured iteration time

These measurements used verified source-download caches. “Cold” means a new compiled dependency prefix or Cargo target directory, rather than a machine without installed tools. Times include the extension-build command through archive production; clean runtime verification is timed separately.

- Docker Linux ARM64, Address Standardizer, four allocated CPUs: 9.76 seconds cold, 3.00 seconds warm, 4.13 seconds after a main-script comment edit. Three further warm runs took 2.98–2.99 seconds.
- Docker Linux x86_64 through Rosetta, Address Standardizer, four allocated CPUs: 51.51 seconds cold, 7.58 seconds warm, 10.04 seconds after the comment edit. Three further warm runs took 7.44–7.47 seconds. Both SQL extensions passed clean runtime checks.
- Docker Linux x86_64 through Rosetta, PostGIS, four allocated CPUs: verified source downloads took 56.22 seconds separately; the cold build took 188.18 seconds. A main-script edit rebuilt PostGIS in 176.78 seconds while retaining its private dependencies. After avoiding repeated configuration, an unchanged repeat took 72.50 seconds with no C recompilation. The archive and all five supplied SQL extension probes passed; clean verification took 64.17 seconds. System geospatial libraries were already installed.
- Lume macOS ARM64, four vCPUs and 8 GiB RAM: Address Standardizer took 19.61 seconds cold, 3.22 warm and 7.01 after the edit. PostGIS took 417.41, 48.71 and 51.61 seconds respectively. PostGIS used an existing conda package-download cache but prepared a fresh installed environment and SFCGAL build.
- In the same Mac VM, pg_jsonschema took 68.72 seconds with an empty Cargo target directory, 8.45 warm and 9.54 after the edit. Rust and the Cargo registry were already installed. Before fixing repeated pgrx initialisation and identical-file rewrites, warm iterations took about 45 seconds. A small SQL-generation helper still recompiles each time.

The PostGIS trial found that retaining dependencies alone did not make its own build incremental: configuration rewrote a shared header and `make` treated the revision header as phony. An unchanged Linux x86 repeat took 161.18 seconds and recompiled 344 C files. The Linux and Mac build scripts now retain successful configuration within the harness-managed source tree and use upstream's `--without-phony-revision` option. Input changes still refresh that source tree. Installation, staging and archive production account for the remaining warm-build time.

Applying that fix in the Mac VM took 50.34 seconds for the first build after the script change and 30.02 seconds for an unchanged repeat, versus the earlier 48.71-second warm baseline. The dependency key and SFCGAL library checksum and modification time stayed unchanged. The warm archive passed clean-VM runtime and SQL verification. Only the Mac build script was transferred into the earlier isolated source snapshot; this measures iteration rather than current release-candidate consistency.

The Mac archives passed SQL probes together in a separate clean VM: 201 Mach-O files checked, no findings, 29.22 seconds for the final verification run. These results establish that retained dependency state helps iteration; they do not yet compare Parallels against Docker or Lume. PostGIS validation on Windows and local macOS x86_64 trials remain incomplete.

On native Windows GitHub runners, six small packages passed first and repeat builds with stable workspace keys and SQL verification. Their repeat builds took 10.00–14.68 seconds. Address Standardizer subsequently passed in 40.40 seconds initially and 13.73 seconds on repeat, including both supplied SQL probes and unchanged workspace keys. pg_jsonschema took 585.19 seconds initially and 33.33 seconds on repeat, including first-time Rust and cargo-pgrx preparation in the initial build. Its archive and combined SQL verification passed. These results prove Windows cache reuse; they do not measure local Windows translation. PostGIS remains under investigation.

PowerShell 7.4.2 syntax-check processes in an amd64 container repeatedly crashed with a Rosetta assertion after reporting successful parses; isolated checks also passed. These checks do not establish compatibility with Windows PowerShell 5.1, which runs the native Windows trials. The measured Linux C builds did not encounter this translation failure.

### Starting another Linux agent

A fresh ARM64 container took 0.61 seconds to provision from the existing Docker image and cached APT layer, with no manual steps. Its initially empty source cache was populated during an Address Standardizer build taking 13.60 seconds. Repeat and post-restart builds took 3.39 and 3.42 seconds. This measures another agent joining an established installation, rather than fresh-machine setup.

Recreating that trial container against its retained host work directory preserved the complete cache manifest. A subsequent build took 3.43 seconds and passed archive checks; the PCRE2 library's checksum, modification time and dependency key were unchanged. The retained work directory occupied 268 MiB. New development containers use Docker's `--init`: stopping the trial then took 0.08 seconds with SIGTERM, compared with 3.12 seconds and a forced kill without it. Existing containers retain their creation settings.

### Concurrent builds

One Linux ARM64 trial built HypoPG and pgvector in separate workspaces. Serial execution took 6.57 seconds using 16 allocated CPUs; two concurrent containers with eight CPUs each took 4.35 seconds, about 34% less wall time. Both scenarios passed archive checks. The serial container peaked at 528 MiB; the concurrent containers peaked individually at 299 and 252 MiB. Their peaks were not necessarily simultaneous and exclude the Docker VM's overhead.

This demonstrates useful two-package concurrency for small native builds. It does not establish a safe limit for PostGIS, Rust or whole VMs. Docker's VM had 16 CPUs and about 47 GiB available, with no per-container memory limit; actual CPU affinity constrained concurrent jobs even though the guest CPU-count query still reported 16.

The separate x86 PostGIS container peaked at 906 MiB across its cold, repeat, edit and diagnostic runs. This cgroup measurement includes charged file cache and excludes Docker's VM overhead. It used preinstalled geospatial libraries and does not measure the memory needed to compile that dependency stack from source.

A host snapshot attributed an 8.01 GiB memory footprint to the running Lume Mac VM and 30.07 GiB to Docker Desktop's Linux VM. The Docker VM had a larger allocation and retained state; these were not matched fresh environments. The figures describe this machine at that moment, rather than minimum requirements or an intrinsic Docker overhead. The host has 128 GiB RAM and 18 logical CPUs.

In the four-vCPU, 8 GiB Mac VM, warm PostGIS and pg_jsonschema builds took 51.88 seconds serially and 49.54 seconds together in separate workspaces. Both succeeded and retained their dependency keys; their archives passed checks together with PostgreSQL. Guest memory pressure reported 79% free before and after, with no swap. The single trial's 2.34-second difference does not establish a reliable throughput improvement. It shows that these two warm builds can share a VM without needing separate environments. The trial used the earlier isolated Mac recipe snapshot, excluding subsequent Windows metadata and helper additions.

The x86_64 clean-verification helper passed the Address Standardizer SQL checks in 39.77 seconds, including a cached verifier-image build and container setup. The development container remained stopped afterwards and retained its cache.

## GitHub dependency caching

The provisional recommendation is to defer a separate hosted compiled-dependency cache until local Windows and macOS x86_64 iteration have been assessed. The current workflows can retry one extension using an existing PostgreSQL archive, and archive selection can reuse unchanged packages. This already avoids rebuilding the whole distribution for one package edit.

The expensive remaining case is rebuilding a changed dependency-heavy package. A previous native Intel macOS run spent 1,945 seconds in the PostGIS job and 1,077 seconds in pg_jsonschema; the complete run took 4,559 seconds. Those are whole-job timings from an earlier revision, including setup and downloads, rather than measured dependency-compilation savings. Local repeat-build results suggest useful savings are possible, but do not establish hosted cache transfer cost or expected hit rate.

During the Windows CLI trial, GitHub exposed step states while the job ran but withheld the full job log until completion. The first bootstrap failure took 109 seconds overall to report. The retry passed bootstrap in 121 seconds and spent 30 minutes 7 seconds building and checking PostgreSQL archives before runtime verification failed. A later fresh runner produced the runtime and development archives in 18 minutes 24 seconds. These timings include dependency preparation, compilation and packaging; they are not compiler-only measurements or a controlled comparison.

Reusing those PostgreSQL archives took six seconds for selection and three seconds for staging and input checks in one subsequent run. The runtime checkpoint still ran. This avoided another PostgreSQL build while diagnosing Windows verification problems, although each hosted retry still needed runner startup and tool preparation. Local Windows iteration must be measured before deciding whether that remaining delay warrants a compiled-dependency cache.

If hosted iteration remains necessary, PostGIS is the first candidate for a measured cache experiment. The dependency phase gives the harness a reusable boundary without adding cache logic to individual build scripts. Hosted reuse would still need a stable installation path or verified relocation, complete invalidation and a timed cache restore. No hosted compiled-dependency cache is currently configured.

## Initial Parallels setup

The existing `Windows 11` VM has its downloaded installation ISO and unattended setup image ready. Starting it, creating a Linux VM and listing snapshots have each failed with “available only in Parallels Desktop for Mac Pro or Business Edition.” Activation needs resolving before command-line provisioning can be evaluated. Computer use briefly connected after permission approval, but subsequent attempts failed with a native-pipe startup error. These are setup blockers, not performance results.

Separate macOS and full-x86 Linux guest-creation attempts returned the same edition error. The latter used the vendor's documented `prlctl create NAME -d ubuntu --cpu-type x86` command. No comparison guest was created. Parallels documents a one-vCPU, 8 GiB limit for full-x86 emulation; its actual project performance remains unmeasured. [Full-x86 guest setup and limitations](https://kb.parallels.com/en/130217).

Routine lifecycle and guest work use `prlctl`; computer use is authorised for Parallels and its Windows guests when a command-line operation is unavailable. Other Mac applications and the host browser remain outside that authorisation.

The command-line client is `/Applications/Parallels Desktop.app/Contents/MacOS/prlctl`. In this agent's sandbox, service queries require an approved execution outside the sandbox. A sandbox-only “Unable to connect to Parallels Service” error does not establish that Parallels needs restarting.

Linux builds in a Parallels guest must use the guest's own filesystem: Parallels documents limitations on `mmap()` in Linux shared folders. Source and archive transfer must be tested separately from build execution. [Shared-folder limitations](https://kb.parallels.com/en/128914).

## Evidence

The earlier four-target package validation is recorded in [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md). New local-iteration timings and machine-readable evidence belong under `out/local-iteration/`; this document records their interpretation and the commands needed to reproduce them.
